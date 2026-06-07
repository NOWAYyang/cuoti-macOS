# 错题本助手

局域网 Web 应用：手机上传错题图片 → MinerU OCR 提取文字 → DeepSeek API 解答 → 生成可打印 PDF。

## 前提条件

- macOS（Intel 或 Apple Silicon）
- Python 3.9+
- 已安装 MinerU（见下方安装步骤）
- DeepSeek API Key（免费注册获取）

## 快速开始

### 1. 创建虚拟环境并安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 安装 MinerU

```bash
pip install -U "mineru[core]"
mineru-download-models
```

### 3. 配置 API Key

```bash
echo "DEEPSEEK_API_KEY=你的密钥" > .env
```

### 4. 启动

```bash
source venv/bin/activate
python app.py
```

手机与 Mac 连接同一 Wi-Fi，访问 `http://<Mac的IP>:5001`。

> 注意：如果 5000 端口被 macOS AirPlay Receiver 占用，默认改用 5001 端口。可通过 `PORT=5000 python app.py` 自定义端口。

## 功能说明

- 支持多张图片同时上传
- 可选纸张尺寸：A4 / B5 / Letter
- 可调节图片压缩质量 30%~100%
- 可调节留白边距（手写空间）
- 可选择是否在 PDF 中包含原图
- 每道题单独一页，含题目原文、解题答案、手写区域

## 注意事项

- 第一次运行 MinerU 会自动下载模型（约 2GB），请耐心等待
- 如果 PDF 中文乱码，请安装系统字体
- API 调用费用极低（约 ¥0.01/题）
- 上传文件超过 1 小时自动清理
