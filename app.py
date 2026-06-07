import os
import time
import random
import string
import logging
import subprocess
import json
import shutil
from pathlib import Path

from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image
import requests

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logging.getLogger("werkzeug").setLevel(logging.ERROR)

# 关掉 Flask 自带的 "Serving Flask app" 提示
import flask.cli as _flask_cli
_flask_cli.show_server_banner = lambda *_, **__: None

for folder in [Config.UPLOAD_FOLDER, Config.OUTPUT_FOLDER, Config.MINERU_CACHE]:
    Path(folder).mkdir(exist_ok=True)


def random_filename(ext: str) -> str:
    ts = int(time.time() * 1000)
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{ts}_{rand}{ext}"


def clean_old_files(folder: str, max_age_sec: int = 3600):
    now = time.time()
    for f in Path(folder).iterdir():
        if f.is_file() and now - f.stat().st_mtime > max_age_sec:
            f.unlink()


def compress_image(image_path: str, quality: int) -> str:
    img = Image.open(image_path)
    max_side = Config.MAX_IMAGE_LONG_SIDE
    w, h = img.size
    if max(w, h) > max_side:
        ratio = max_side / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    ext = os.path.splitext(image_path)[1] or ".jpg"
    compressed_path = image_path.replace(ext, "_compressed.jpg")
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(compressed_path, "JPEG", quality=quality)
    return compressed_path


# MinerU 常驻服务
_mineru_api_url = None
_mineru_server_proc = None


def _start_mineru_server():
    global _mineru_api_url, _mineru_server_proc
    port = 52999
    _mineru_api_url = f"http://127.0.0.1:{port}"

    proc = subprocess.Popen(
        ["/opt/anaconda3/bin/python", "-m", "mineru.cli.fast_api",
         "--enable-vlm-preload", "true",
         "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _mineru_server_proc = proc

    # 等它启动完毕
    for _ in range(120):
        import socket
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=1)
            s.close()
            return
        except (ConnectionRefusedError, OSError):
            time.sleep(1)

    # 超时了，放弃
    proc.kill()
    _mineru_server_proc = None
    _mineru_api_url = None


def _stop_mineru_server():
    global _mineru_server_proc, _mineru_api_url
    if _mineru_server_proc:
        _mineru_server_proc.kill()
        _mineru_server_proc.wait(timeout=5)
        _mineru_server_proc = None
        _mineru_api_url = None


def ocr_images(image_paths: list) -> dict:
    """Send images to the persistent MinerU API server."""
    if not image_paths or _mineru_api_url is None:
        return {}

    api = _mineru_api_url

    # POST /tasks with all files
    files = [("files", (os.path.basename(p), open(p, "rb"))) for p in image_paths]
    try:
        resp = requests.post(f"{api}/tasks", files=files,
                             data={"backend": "vlm-auto-engine"}, timeout=30)
    except requests.exceptions.ConnectionError:
        raise RuntimeError("OCR 服务未启动，请重启应用")
    finally:
        for _, fobj in files:
            fobj[1].close()

    if resp.status_code not in (200, 202):
        raise RuntimeError(f"OCR 提交失败: HTTP {resp.status_code}")

    task = resp.json()
    task_id = task.get("task_id")
    if not task_id:
        raise RuntimeError("OCR 服务返回异常")

    # 轮询直到完成
    poll_interval = 1
    for _ in range(Config.OCR_TIMEOUT):
        time.sleep(poll_interval)
        status_resp = requests.get(f"{api}/tasks/{task_id}", timeout=10)
        if status_resp.status_code != 200:
            continue
        status = status_resp.json().get("status")
        if status == "completed":
            break
        if status == "failed":
            err = status_resp.json().get("error", "未知错误")
            raise RuntimeError(f"OCR 处理失败: {err}")
    else:
        raise RuntimeError(f"OCR 处理超时（{Config.OCR_TIMEOUT}秒）")

    # 获取结果
    result_resp = requests.get(f"{api}/tasks/{task_id}/result", timeout=10)
    if result_resp.status_code != 200:
        raise RuntimeError("OCR 结果获取失败")

    results = result_resp.json().get("results", {})
    texts = {}
    for p in image_paths:
        base = os.path.splitext(os.path.basename(p))[0]
        md = results.get(base, {}).get("md_content", "")
        texts[p] = md.strip()
    return texts


def ask_deepseek(question: str) -> str:
    headers = {
        "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": Config.DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是一位解题老师。请给出详细解题步骤和最终答案，用Markdown格式输出。数学公式必须用标准LaTeX格式：行内公式用单个$包裹（如$x^2$），独立公式用双$包裹（如$$x=\\frac{-b}{2a}$$）。不要使用\\(和\\)或\\[和\\]。确保所有数学符号和表达式都用正确的LaTeX语法。",
            },
            {"role": "user", "content": f"请解答以下题目：\n\n{question}"},
        ],
        "max_tokens": 4096,
        "temperature": 0.2,
    }

    last_error = ""
    models_to_try = [Config.DEEPSEEK_MODEL, Config.DEEPSEEK_FALLBACK_MODEL]
    for model in models_to_try:
        payload["model"] = model
        for attempt in range(Config.DEEPSEEK_RETRIES):
            try:
                resp = requests.post(
                    Config.DEEPSEEK_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=Config.DEEPSEEK_TIMEOUT,
                )
                if resp.status_code == 200:
                    msg = resp.json()["choices"][0]["message"]
                    content = msg.get("content", "") or msg.get("reasoning_content", "")
                    if content:
                        return content
                    last_error = "模型返回空内容"
                    break  # try next model
                elif resp.status_code == 401:
                    return "*AI 解答失败：API Key 无效，请检查 api-key.txt 中的密钥是否正确*"
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except requests.exceptions.Timeout:
                last_error = "请求超时"
            except requests.exceptions.ConnectionError:
                last_error = "网络连接失败"
            time.sleep(1)

    return f"*AI 解答失败：{last_error}*"


def generate_docx(results: list, paper_size: str, margin_mm: int,
                 compress_quality: int, include_image: bool) -> str:
    """生成 .docx 文件。Markdown+LaTeX → pandoc → docx（含 Word 原生公式）"""
    from docx import Document
    from docx.shared import Pt, Cm, RGBColor
    from docx.oxml import OxmlElement

    _w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    qn = lambda tag: f"{{{_w}}}{tag}"

    timestamp = int(time.time())
    prefix = f"错题本_{timestamp}"
    md_path = os.path.join(Config.OUTPUT_FOLDER, f"{prefix}.md")
    docx_path = os.path.join(Config.OUTPUT_FOLDER, f"{prefix}.docx")

    # 构建 Markdown
    lines = []
    for i, item in enumerate(results):
        q_text = item.get("question") or "（未能识别到题目文字）"
        a_text = item.get("answer") or "（无答案）"

        lines.append(f"## 第 {i+1} 题\n\n")
        if include_image and os.path.exists(item.get("compressed_path", "")):
            lines.append(f"![题目图片]({os.path.abspath(item['compressed_path'])})\n\n")

        lines.append("### 题目原文\n\n")
        lines.append(f"{q_text}\n\n")
        lines.append("### 解题答案\n\n")
        lines.append(f"{a_text}\n\n")

        tags = item.get("error_tags", [])
        note = item.get("error_note", "")
        if tags or note:
            lines.append("### 错因分析\n\n")
            if tags:
                lines.append(f"**错误标签：** {'、'.join(tags)}\n\n")
            if note:
                lines.append(f"**备注：** {note}\n\n")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("".join(lines))

    try:
        subprocess.run(
            ["pandoc", md_path, "-o", docx_path,
             "-f", "markdown+tex_math_dollars",
             "-t", "docx"],
            check=True, capture_output=True, text=True, timeout=30,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"文档生成失败：{e.stderr}")
    except FileNotFoundError:
        raise RuntimeError("未找到 pandoc，请执行: brew install pandoc")
    finally:
        if os.path.exists(md_path):
            os.unlink(md_path)

    # Post-process: 每题末尾加手写区 + 分页
    doc = Document(docx_path)
    body = doc.element.body

    def _make_p_elem(text="", font_size=None, color=None, bold=False):
        """Create a w:p element with optional formatting."""
        p = OxmlElement("w:p")
        r = OxmlElement("w:r")
        t = OxmlElement("w:t")
        t.text = text
        r.append(t)

        if font_size or color or bold:
            rPr = OxmlElement("w:rPr")
            if font_size:
                sz = OxmlElement("w:sz")
                sz.set(qn("val"), str(font_size * 2))  # half-pt units
                rPr.append(sz)
            if color:
                clr = OxmlElement("w:color")
                clr.set(qn("val"), color.replace("#", ""))
                rPr.append(clr)
            if bold:
                b = OxmlElement("w:b")
                rPr.append(b)
            r.insert(0, rPr)

        p.append(r)
        return p

    def _make_handwriting_table():
        """Create a w:tbl with 4 rows, each with dashed bottom border."""
        tbl = OxmlElement("w:tbl")

        # Table grid (1 column)
        tblGrid = OxmlElement("w:tblGrid")
        gridCol = OxmlElement("w:gridCol")
        gridCol.set(qn("w"), "9072")
        tblGrid.append(gridCol)
        tbl.append(tblGrid)

        for _ in range(4):
            tr = OxmlElement("w:tr")
            trPr = OxmlElement("w:trPr")
            trHeight = OxmlElement("w:trHeight")
            trHeight.set(qn("val"), "680")
            trPr.append(trHeight)
            tr.append(trPr)

            tc = OxmlElement("w:tc")
            tcPr = OxmlElement("w:tcPr")
            tcW = OxmlElement("w:tcW")
            tcW.set(qn("w"), "9072")
            tcW.set(qn("type"), "dxa")
            tcPr.append(tcW)

            # Bottom border: dashed
            tcBorders = OxmlElement("w:tcBorders")
            bottom = OxmlElement("w:bottom")
            for attr, val in [("val", "dashed"), ("color", "CCCCCC"),
                              ("sz", "4"), ("space", "1")]:
                bottom.set(qn(attr), val)
            tcBorders.append(bottom)
            tcPr.append(tcBorders)
            tc.append(tcPr)

            # Empty paragraph inside cell
            tc.append(_make_p_elem())
            tr.append(tc)
            tbl.append(tr)

        return tbl

    # 找到所有 Heading 2（"## 第 N 题"）段落
    heading2_paras = []
    for para in doc.paragraphs:
        if para.style.name == "Heading 2":
            heading2_paras.append(para)

    num_questions = len(heading2_paras)

    # 从后往前处理（避免索引漂移）
    for idx, para in enumerate(reversed(heading2_paras)):
        actual_idx = num_questions - 1 - idx  # original index

        # 除第一题外，在前一题末尾加手写区 → 再分页
        if actual_idx > 0:
            # 在当前 heading 前插入：手写区 table + label
            tbl = _make_handwriting_table()
            para._p.addprevious(tbl)
            label_p = _make_p_elem("✏️ 手写订正区", font_size=10, color="AAAAAA")
            para._p.addprevious(label_p)
            para._p.addprevious(_make_p_elem(""))

            # 分页 (set pageBreak on an empty paragraph)
            pb_para = OxmlElement("w:p")
            pb_r = OxmlElement("w:r")
            pb_br = OxmlElement("w:br")
            pb_br.set(qn("type"), "page")
            pb_r.append(pb_br)
            pb_para.append(pb_r)
            para._p.addprevious(pb_para)

    doc.save(docx_path)
    return docx_path


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    start_time = time.time()
    ip = request.remote_addr or "unknown"

    clean_old_files(Config.UPLOAD_FOLDER)
    clean_old_files(Config.OUTPUT_FOLDER)

    if "images" not in request.files:
        return jsonify({"error": "未选择图片"}), 400

    files = request.files.getlist("images")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "未选择图片"}), 400

    paper_size = request.form.get("paper_size", Config.DEFAULT_PAPER_SIZE)
    compress_quality = int(request.form.get("compress_quality", Config.DEFAULT_COMPRESS_QUALITY))
    margin_mm = int(request.form.get("margin_mm", Config.DEFAULT_MARGIN_MM))
    include_image = request.form.get("include_original_image", "true") == "true"

    compress_quality = max(30, min(100, compress_quality))
    margin_mm = max(0, min(50, margin_mm))

    if paper_size not in Config.PAPER_SIZES:
        paper_size = Config.DEFAULT_PAPER_SIZE

    saved_paths = []
    compressed_paths = []

    try:
        for f in files:
            ext = os.path.splitext(f.filename or ".jpg")[1] or ".jpg"
            save_name = random_filename(ext)
            save_path = os.path.join(Config.UPLOAD_FOLDER, save_name)
            f.save(save_path)
            saved_paths.append(save_path)

        # 压缩所有图片（先）
        for sp in saved_paths:
            compressed_paths.append(compress_image(sp, compress_quality))

        # OCR 所有图片（一次 batch 调用，模型只加载一次）
        ocr_results = ocr_images(compressed_paths)

        error_data_raw = request.form.get("error_data", "{}")
        try:
            error_data = json.loads(error_data_raw)
        except json.JSONDecodeError:
            error_data = {}
        all_tags = error_data.get("tags", [])
        all_notes = error_data.get("notes", [])

        results = []
        for i, cp in enumerate(compressed_paths):
            question_text = ocr_results.get(cp, "") or "（未能识别到题目文字）"
            answer = ask_deepseek(question_text)
            results.append({
                "question": question_text,
                "answer": answer,
                "compressed_path": cp,
                "error_tags": all_tags[i] if i < len(all_tags) else [],
                "error_note": all_notes[i] if i < len(all_notes) else "",
            })

        docx_path = generate_docx(
            results, paper_size, margin_mm, compress_quality, include_image,
        )

        elapsed = time.time() - start_time
        logging.info(f"OK | {ip} | {len(files)} images | {elapsed:.1f}s | {docx_path}")

        return send_file(docx_path, as_attachment=True, download_name=os.path.basename(docx_path))

    except RuntimeError as e:
        logging.error(f"ERR | {ip} | {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logging.error(f"ERR | {ip} | {e}")
        return jsonify({"error": f"处理失败：{str(e)}"}), 500


def _get_local_ip() -> str:
    import subprocess
    # 优先扫 Mac 常见的 Wi-Fi / 有线网卡（en0, en1）
    for iface in ("en0", "en1"):
        try:
            ip = subprocess.run(
                ["ipconfig", "getifaddr", iface],
                capture_output=True, text=True, timeout=2,
            ).stdout.strip()
            if ip:
                return ip
        except Exception:
            continue

    # 兜底：扫所有网卡，跳过 lo0 和 Docker 隧道
    try:
        out = subprocess.run(
            ["ifconfig"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        cur = ""
        for line in out.splitlines():
            if line and line[0].isalpha():
                cur = line.split(":")[0]
            if "inet " in line and cur not in ("lo0", "lo", "utun84", "utun"):
                parts = line.strip().split()
                idx = parts.index("inet") + 1
                if idx < len(parts):
                    ip = parts[idx]
                    if not ip.startswith("127."):
                        return ip
    except Exception:
        pass

    return "127.0.0.1"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    ip = _get_local_ip()

    print("正在启动 OCR 模型（首次约 90 秒）...")
    _start_mineru_server()
    print("OCR 模型加载完成 ✓")

    print(f"""
━━━ 错题本助手 已启动 🚀 ━━━

  ➜ 手机访问（同一 Wi-Fi）
     http://{ip}:{port}

  ➜ 本机访问
     http://127.0.0.1:{port}

  Ctrl+C 停止服务
""")
    try:
        app.run(host="0.0.0.0", port=port)
    finally:
        _stop_mineru_server()
