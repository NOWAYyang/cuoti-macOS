# 错题本助手（macOS专版）

写在最前：这是一个Vibe Coding项目，不做任何可用性保证，但是我尽量去优化了使用体验

also这是在Mac上开发的，算是一个emm半重造轮子的项目啦。

把手机拍的错题照片，变成一份带答案和手写空白的 Word 文档，方便打印出来做订正。

**工作流程**：手机拍照上传 → 自动识别题目文字 → AI 自动解题 → 生成 Word 文档（原图 + 答案 + 错因分析 + 手写订正区）

## 你需要准备什么

| 项目               | 说明                                 |
| ---------------- | ---------------------------------- |
| 一台 Mac           | Intel 芯片（未验证）或 Apple Silicon （已验证） |
| 一部手机             | 与Mac同局域网                           |
| DeepSeek API Key | 免费注册获取，记得充值，每次解题约 1 分钱（大概）         |

---

## 安装步骤

### 第 1 步：安装 Pandoc（Word 文档生成引擎）

Pandoc 用于将 Markdown 转换为 Word 文档并保留数学公式。

```bash
brew install pandoc
```

### 第 2 步：填写 API Key

打开 `api-key.txt`，把你的 DeepSeek API Key 粘贴进去，像这样：

```
将你的 DeepSeek API Key 粘贴在此处，一行一个。
sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> 没有 API Key？去 https://platform.deepseek.com/ 注册，在"API 密钥"页面创建一个，复制过来就行。

### 第 3 步：创建运行环境（只需做一次）

打开 Mac 的"终端"（Terminal）应用（，执行以下命令：

```bash
# 进入项目文件夹
cd /Users/danler/cuoti

# 创建虚拟环境（相当于给这个项目一个独立的工作空间）
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖库
pip install -r requirements.txt
```

### 第 4 步：下载 OCR 模型（此处用的MinerU）

```bash
# 从 ModelScope 下载 OCR 模型
mineru-models-download -s modelscope
```

> 下载时间取决于网速，可能需要十几分钟。

---

## 启动

每次使用时，打开终端，执行：

```bash
cd /Users/danler/cuoti
source venv/bin/activate
python app.py
```

首次启动会加载 OCR 模型（约 **85 秒**），终端会显示进度：

```
━━━ 错题本助手 已启动 🚀 ━━━

  ➜ 手机访问（同一 Wi-Fi）
     http://192.168.x.xxx:5001

  ➜ 本机访问
     http://127.0.0.1:5001

  Ctrl+C 停止服务
```

在手机浏览器输入显示的地址（`http://192.168.x.xxx:5001`），就能看到上传页面了。

> Mac 和手机必须在**同一个 Wi-Fi** 下才能访问。
> 
> 哦你的Mac没有Wi-Fi网卡？——局域网也行（但真的会有Mac没有Wi-Fi吗）

---

## 如何使用

1. 手机浏览器打开终端显示的地址
2. 选择要处理的错题照片（可以一次选多张）
3. 调整纸张、留白等参数（一般保持默认即可）
4. 点击"生成错题本 Word"
5. 等待约 **10 秒**，Word 文档会自动下载
6. 用打印机打出来，在手写区订正

### Word 文档里有什么

- **原图**（可选）— 你拍的错题照片
- **题目原文**— OCR 识别出的文字
- **解题答案**— AI 给出的详细步骤和结果（LaTeX 公式会转为 Word 原生公式）
- **错因分析**— 你标记的错误类型和备注
- **手写订正区**— 每道题末尾的虚线表格，打印出来在上面订正

---

## 常见问题

**Q: 终端显示 "Address already in use"？**
A: macOS 的 AirPlay 占用了 5000 端口，已默认改为 5001。

**Q: AI 解题不准怎么办？**
A: 拍照时尽量拍正、光线充足。OCR 识别的文字越准确，AI 解题效果越好。

**Q: 上传的文件会一直保留吗？**
A: 不会。超过 1 小时的图片会自动清理，保护隐私。

**Q: 每次启动都要等 85 秒吗？**
A: 只有第一次启动需要加载模型。启动后服务常驻后台，之后每次 OCR 只需约 **6 秒**。

**Q: 生成的 Word 文档里公式显示不正常？**
A: 确保已安装 Pandoc（`brew install pandoc`）。Word 桌面版对 LaTeX 公式转换支持最好，Web 版可能显示不佳。

---

## 文件说明

| 文件              | 作用                                       |
| --------------- | ---------------------------------------- |
| `api-key.txt`   | 存放你的 API Key（已加入 .gitignore，不会传到 GitHub） |
| `app.py`        | 主程序                                      |
| `config.py`     | 配置项                                      |
| `uploads/`      | 临时存放上传的图片                                |
| `outputs/`      | 生成的 Word 文档存放在这里                         |
| `mineru_cache/` | MinerU 临时文件                              |

## 附：Mac上的硬件加速

我在设计的时候使用的是搭载Apple Silicon的Mac，so加速计算用的MLX的后端

我没有测试Intel的Mac但是设置了下载模型是两个后段都能用的ver

如果你的显卡支持Metal API加速那么应该能用MPS，如果你用的Apple Silicon那非常抱歉浪费你时间了这段话可以不用看，自动会用MLX后段加速（基于MinerU的鉴别脚本）
