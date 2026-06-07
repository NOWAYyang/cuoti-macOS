```markdown
# 错题本助手 - 完整开发任务（Claude Code）

> 目标：实现一个局域网 Web 应用，手机上传错题图片 → Mac 端用 MinerU 提取题目文字 → DeepSeek API 解答 → 生成可打印 PDF（含原图、答案区、手写空白）。全流程本地优先，API 成本极低。

## 1. 项目结构（请按此创建）

```
mistake_book/
├── app.py                 # Flask 主程序
├── config.py              # 配置（API Key，上传路径等）
├── requirements.txt       # 依赖列表
├── templates/
│   └── index.html         # 手机端上传界面
├── static/
│   ├── style.css          # 可选样式
│   └── script.js          # 前端交互
├── uploads/               # 临时存放上传图片（自动创建）
├── outputs/               # 生成的 PDF（自动创建）
├── mineru_cache/          # MinerU 临时文件（自动创建）
└── README.md              # 用户使用说明
```

## 2. 功能需求

### 2.1 Web 前端（手机适配）
- [ ] 页面标题：“错题本助手”
- [ ] 多文件选择控件（`<input type="file" multiple accept="image/*" capture="environment">`）
- [ ] 参数选择：
  - **纸张尺寸**：A4（默认）、B5、Letter 三种
  - **图片压缩质量**：滑块 30%~100%，默认 80%（影响 PDF 内图片清晰度）
  - **留白边距**：数字输入框，单位毫米，默认 10mm（用于手写）
  - **是否包含原图**：开关，默认开启
- [ ] 提交按钮：“生成错题本 PDF”
- [ ] 加载提示：转圈 + “正在 OCR 提取...”“正在调用 AI 解题...”“正在生成 PDF...”
- [ ] 成功：自动下载 PDF 文件
- [ ] 错误：弹出具体错误信息（如 API 密钥失效、MinerU 未安装）

### 2.2 后端（Flask）

#### 路由：
- `GET /` → 返回 `index.html`
- `POST /upload` → 处理图片和参数，返回 PDF 文件

#### 处理流程：
1. 接收表单数据：
   - `images`（文件列表）
   - `paper_size`（字符串）
   - `compress_quality`（整数 30-100）
   - `margin_mm`（整数）
   - `include_original_image`（布尔，默认 true）
2. 保存每张图片到 `uploads/`，使用时间戳+随机数命名。
3. 对每张图片：
   - 用 Pillow 压缩：长边最大 1600px，保存质量 = `compress_quality`
   - 调用 MinerU 命令行提取文本：
     ```bash
     mineru -p <图片路径> -o <mineru_cache> --method auto
     ```
     - 解析 MinerU 输出的 Markdown 文件（与图片同名的 `.md`）
     - 读取其中文字内容作为 `question_text`
   - 调用 DeepSeek API：
     - 模型：`deepseek-reasoner` 或 `deepseek-chat`
     - System prompt: 你是一位解题老师，给出详细解题步骤和最终答案，用 Markdown 格式输出。
     - User prompt: `请解答以下题目：\n\n{question_text}`
     - 获取 `answer`
   - 将结果存入列表：`{"image_path": 压缩后路径, "question": question_text, "answer": answer}`
4. 生成 PDF：
   - 使用 `weasyprint` 或 `pdfkit`（优先 weasyprint，因 CSS 支持更好）
   - 根据 `paper_size` 和 `margin_mm` 设置页面边距
   - 每张图占用一页（可分页），布局：
     - 顶部（可选）显示原图（若 `include_original_image` 为 true）
     - 中间显示“📖 题目原文”（OCR 结果）
     - 显示“✅ 解题答案”（DeepSeek 返回的 Markdown）
     - 底部留出手写空白行（可加虚线或浅色底纹，提示手写区域）
   - 将所有页面合并为一个 PDF 文件
5. 返回 PDF 文件（Content-Disposition 为附件）

### 2.3 OCR 集成细节（MinerU）
- 使用 Python 的 `subprocess` 调用 MinerU。
- 需要处理可能的错误：MinerU 未安装、模型未下载、图片无法识别等。
- 超时设置：每张图片 OCR 限制 30 秒。
- 清理 `mineru_cache` 中的临时文件（可选，保留最近 10 个）。

### 2.4 DeepSeek API 集成
- 从环境变量 `DEEPSEEK_API_KEY` 读取密钥。
- 请求 URL：`https://api.deepseek.com/v1/chat/completions`
- 请求参数：
```json
{
  "model": "deepseek-reasoner",
  "messages": [
    {"role": "system", "content": "你是一位解题老师。请给出详细解题步骤和最终答案，用Markdown格式输出。"},
    {"role": "user", "content": "请解答以下题目：\n\n" + question_text}
  ],
  "max_tokens": 2048,
  "temperature": 0.2
}
```
- 超时 20 秒，重试 2 次。
- 错误处理：返回错误文本，PDF 中标注“AI 解答失败”。

### 2.5 PDF 样式要求
- 页面边距：使用 CSS `@page` 规则。
- 原图：最大宽度 100%，高度自适应，居中。
- 答案区域：白色背景，黑色文字，支持 Markdown 转 HTML（需先转换，如用 `markdown` 库）。
- 手写区域：高度至少 80mm，背景可以有浅灰色虚线行（模拟笔记本）。
- 分页：每道题单独一页，`page-break-after: always`。
- 字体：中英文使用系统默认无衬线字体（如 PingFang SC, Roboto）。

## 3. 依赖与安装（requirements.txt）

```
flask==3.0.0
pillow==10.1.0
weasyprint==60.1
requests==2.31.0
markdown==3.5.1
python-dotenv==1.0.0
```

**额外系统依赖（用户手动安装）**：
- MinerU：`uv pip install -U "mineru[core]"` 并下载模型（提供命令）
- wkhtmltopdf（若使用 pdfkit 替代 weasyprint，可选）

## 4. 环境配置（.env 文件）

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
MINERU_MODEL_DIR=~/.cache/mineru/models  # 可选
UPLOAD_FOLDER=uploads
OUTPUT_FOLDER=outputs
```

## 5. 启动与使用说明（README.md 内容）

```markdown
# 错题本助手 - 本地部署指南

## 前提条件
- MacOS（Intel 或 Apple Silicon）
- Python 3.9+
- 已安装 MinerU（见下方安装步骤）
- DeepSeek API Key（免费注册获取）

## 安装步骤
1. 克隆或下载本项目
2. 创建虚拟环境：`python3 -m venv venv && source venv/bin/activate`
3. 安装 Python 依赖：`pip install -r requirements.txt`
4. 安装 MinerU：
   ```bash
   uv pip install -U "mineru[core]"
   mineru-download-models
   ```
5. 设置 API Key：`echo "DEEPSEEK_API_KEY=你的密钥" > .env`
6. 运行：`python app.py`
7. 手机与 Mac 连接同一 Wi-Fi，访问 `http://<Mac的IP>:5000`

## 注意事项
- 第一次运行 MinerU 会自动下载模型（约 2GB），请耐心等待。
- 如果 PDF 中文乱码，请安装系统字体或修改 weasyprint 的字体配置。
- API 调用会产生极少费用（约 0.01 元/题）。
```

## 6. 非功能性要求

- **并发**：暂不考虑多用户，单用户顺序处理即可。
- **安全性**：局域网内使用，不需要用户认证。上传的文件名随机化，定期清理上传文件夹（每天或每次启动时清理超过 1 小时的文件）。
- **日志**：记录每次请求的 IP、处理时间、错误信息到 `app.log`。
- **代码风格**：PEP 8，添加必要的注释。

## 7. 测试清单

- [ ] 上传单张清晰印刷体数学题图片 → 能正确 OCR 并输出正确答案 PDF。
- [ ] 上传多张图片 → PDF 包含多页，每页对应一道题。
- [ ] 修改纸张尺寸和留白 → PDF 页面大小和边距符合预期。
- [ ] 关闭“包含原图” → PDF 中不显示原图，只显示文本和答案。
- [ ] 压缩质量调到 30% → PDF 内图片模糊但文件变小。
- [ ] 上传不含文字的纯图形 → OCR 返回空或少量文字，API 能给出合理回应（如“无法识别题目”）。
- [ ] API Key 错误 → 前端显示友好的错误提示。
- [ ] MinerU 未安装 → 程序给出明确指引。

## 8. 交付物要求

- 完整可运行的 `app.py` 及相关文件。
- 代码中不得有硬编码的敏感信息（API Key 必须从环境变量读取）。
- 提供一键启动脚本 `run.sh`（可选）。
- 确保在干净的 Mac 环境上能够按 README 成功运行。

## 9. 扩展建议（非必须，但加分）

- 增加错题数据库（SQLite）：保存每道题的图片路径、题目文本、答案、生成时间，可检索。
- 增加“重新生成答案”按钮（针对某道题单独调用 API）。
- 支持 PDF 中添加页码。
- 前端显示处理进度条（每张图一个状态）。

---

**请 Claude Code 严格按照此任务文件生成所有代码和文档。**
```
