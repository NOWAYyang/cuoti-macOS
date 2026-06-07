import os
import time
import random
import string
import logging
import subprocess
from pathlib import Path

from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image
from weasyprint import HTML
import markdown
import requests

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

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


def ocr_image(image_path: str) -> str:
    cmd = [
        "mineru",
        "-p", image_path,
        "-o", Config.MINERU_CACHE,
        "--method", "auto",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=Config.OCR_TIMEOUT,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "MinerU 未安装或未找到。请运行: uv pip install -U 'mineru[core]'"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"OCR 处理超时（{Config.OCR_TIMEOUT}秒）")

    if result.returncode != 0:
        raise RuntimeError(f"MinerU 执行失败: {result.stderr.strip()}")

    base = os.path.splitext(os.path.basename(image_path))[0]
    md_path = os.path.join(Config.MINERU_CACHE, f"{base}.md")
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


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
                "content": "你是一位解题老师。请给出详细解题步骤和最终答案，用Markdown格式输出。",
            },
            {"role": "user", "content": f"请解答以下题目：\n\n{question}"},
        ],
        "max_tokens": 2048,
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
                    return resp.json()["choices"][0]["message"]["content"]
                elif resp.status_code == 401:
                    return "*AI 解答失败：API Key 无效，请检查 DEEPSEEK_API_KEY*"
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except requests.exceptions.Timeout:
                last_error = "请求超时"
            except requests.exceptions.ConnectionError:
                last_error = "网络连接失败"
            time.sleep(1)

    return f"*AI 解答失败：{last_error}*"


def generate_pdf(results: list, paper_size: str, margin_mm: int,
                 compress_quality: int, include_image: bool) -> str:
    size = Config.PAPER_SIZES.get(paper_size, Config.PAPER_SIZES["A4"])
    pages_html = ""
    md = markdown.Markdown(extensions=["extra", "codehilite"])

    for i, item in enumerate(results):
        question_html = md.convert(item["question"]) if item["question"] else "<p>（未能识别到题目文字）</p>"
        answer_html = md.convert(item["answer"]) if item["answer"] else "<p>（无答案）</p>"

        img_tag = ""
        if include_image and os.path.exists(item["compressed_path"]):
            img_tag = f'<img src="file://{os.path.abspath(item["compressed_path"])}" class="problem-image" />'

        pages_html += f"""
        <div class="page">
            <div class="page-header">错题本助手 - 第{i+1}题</div>
            {img_tag}
            <div class="section">
                <h2>📖 题目原文</h2>
                <div class="question-text">{question_html}</div>
            </div>
            <div class="section">
                <h2>✅ 解题答案</h2>
                <div class="answer-text">{answer_html}</div>
            </div>
            <div class="handwriting-area">
                <div class="handwriting-label">✏️ 手写订正区</div>
            </div>
        </div>
        """

    html_template = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: {size[0]}mm {size[1]}mm;
    margin: {margin_mm}mm;
  }}
  body {{
    font-family: -apple-system, "PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
    font-size: 12pt;
    line-height: 1.6;
    color: #222;
  }}
  .page {{
    page-break-after: always;
  }}
  .page-header {{
    font-size: 10pt;
    color: #999;
    text-align: center;
    margin-bottom: 8mm;
    border-bottom: 1px solid #ddd;
    padding-bottom: 4mm;
  }}
  .problem-image {{
    display: block;
    max-width: 100%;
    height: auto;
    margin: 0 auto 6mm auto;
  }}
  .section {{
    margin-bottom: 6mm;
  }}
  .section h2 {{
    font-size: 13pt;
    border-left: 4px solid #4a90d9;
    padding-left: 4mm;
    margin: 0 0 3mm 0;
  }}
  .question-text {{
    background: #f8f9fa;
    padding: 4mm;
    border-radius: 2mm;
    white-space: pre-wrap;
  }}
  .answer-text {{
    padding: 4mm;
  }}
  .answer-text p {{
    margin: 2mm 0;
  }}
  .handwriting-area {{
    margin-top: 4mm;
    min-height: 80mm;
    background-image: repeating-linear-gradient(
      transparent,
      transparent 7.8mm,
      #e0e0e0 7.8mm,
      #e0e0e0 8mm
    );
    border-top: 2px dashed #ccc;
    padding-top: 2mm;
  }}
  .handwriting-label {{
    font-size: 10pt;
    color: #aaa;
    margin-bottom: 2mm;
  }}
</style>
</head>
<body>
  {pages_html}
</body>
</html>"""

    output_path = os.path.join(
        Config.OUTPUT_FOLDER,
        f"错题本_{int(time.time())}.pdf",
    )
    HTML(string=html_template).write_pdf(output_path)
    return output_path


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

    results = []

    try:
        for f in files:
            ext = os.path.splitext(f.filename or ".jpg")[1] or ".jpg"
            save_name = random_filename(ext)
            save_path = os.path.join(Config.UPLOAD_FOLDER, save_name)
            f.save(save_path)

            compressed_path = compress_image(save_path, compress_quality)

            question_text = ocr_image(save_path) or "（未能识别到题目文字）"

            answer = ask_deepseek(question_text)

            results.append({
                "question": question_text,
                "answer": answer,
                "compressed_path": compressed_path,
            })

            if compressed_path != save_path:
                os.remove(save_path)

        pdf_path = generate_pdf(
            results, paper_size, margin_mm, compress_quality, include_image,
        )

        elapsed = time.time() - start_time
        logging.info(f"OK | {ip} | {len(files)} images | {elapsed:.1f}s | {pdf_path}")

        return send_file(pdf_path, as_attachment=True, download_name=os.path.basename(pdf_path))

    except RuntimeError as e:
        logging.error(f"ERR | {ip} | {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logging.error(f"ERR | {ip} | {e}")
        return jsonify({"error": f"处理失败：{str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
