# 错题本助手（跨平台版）

写在最前：这是一个Vibe Coding项目，不做任何可用性保证，但是我尽量去优化了使用体验

also这是在Mac上开发的，Win/Linux的硬件加速可用性不确定，请参考下面的内容去装依赖

如果有任何问题欢迎提issue，若有更好的实现欢迎Push

:> 

把手机拍的错题照片，变成一份带答案和手写空白的 Word 文档，方便打印出来做订正。

**工作流程**：手机拍照上传 → 自动识别题目文字 → AI 自动解题 → 生成 Word 文档（题目 + 答案 + 错因分析 + 手写订正区）

---

## 你需要准备什么

| 项目               | 说明                         |
| ---------------- | -------------------------- |
| 一台电脑             | macOS / Windows / Linux 均可 |
| 一部手机             | 与电脑同局域网                    |
| DeepSeek API Key | 免费注册获取，记得充值，每次解题约 1 分钱（大概） |

---

## 安装步骤

### 第 1 步：安装 Pandoc（Word 文档生成引擎）

Pandoc 用于将 Markdown 转换为 Word 文档并保留数学公式。

**macOS：**

```bash
brew install pandoc
```

**Linux（Ubuntu/Debian）：**

```bash
sudo apt install pandoc
```

**Windows：**

```bash
winget install pandoc
```

或从 https://pandoc.org/installing.html 下载安装包。

### 第 2 步：填写 API Key

打开 `api-key.txt`，把你的 DeepSeek API Key 粘贴进去，像这样：

```
将你的 DeepSeek API Key 粘贴在此处，一行一个。
sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> 没有 API Key？去 https://platform.deepseek.com/ 注册（账号密码和你的DS登录密码相同，在"API 密钥"页面创建一个，复制过来就行。

### 第 3 步：创建运行环境（只需做一次）

**macOS / Linux：**

```bash
# 进入项目文件夹
cd cuoti-multi-platform

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖库
pip install -r requirements.txt
```

**Windows（CMD 或 PowerShell）：**

```cmd
cd multi-platform
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 第 4 步：下载 OCR 模型（我选的MinerU）

```bash
# 激活虚拟环境后执行
mineru-models-download -s modelscope
```

> 下载时间取决于网速，可能需要十几分钟。

### 第 5 步：配置 MinerU Python 路径（高级用户）

***如果你不知道什么是MinerU路径，那么你就用不到这一步***

如果 MinerU 安装在非默认的 Python 环境中，可以通过环境变量指定：

**macOS / Linux：**

```bash
export MINERU_PYTHON=/path/to/your/python
```

**Windows（CMD）：**

```cmd
set MINERU_PYTHON=C:\path\to\python.exe
```

**Windows（PowerShell）：**

```powershell
$env:MINERU_PYTHON = "C:\path\to\python.exe"
```

如果不设置，程序会自动使用当前虚拟环境中的 Python。

---

## 启动

**macOS / Linux：**

```bash
cd multi-platform
source venv/bin/activate
python app.py
```

**Windows（CMD 或 PowerShell）：**

```cmd
cd multi-platform
venv\Scripts\activate
python app.py
```

**Windows 快捷方式：** 双击 `run.bat` 即可一键启动。（未验证）

首次启动会加载 OCR 模型（约 **85 秒**），终端会显示进度：

```
正在启动 OCR 模型（首次约 90 秒）...
OCR 模型加载完成 ✓

━━━ 错题本助手 已启动 ━━━

  ➜ 手机访问（同一 Wi-Fi）
     http://192.168.x.xxx:5001

  ➜ 本机访问
     http://127.0.0.1:5001

  Ctrl+C 停止服务
```

在手机浏览器输入显示的地址（`http://192.168.x.xxx:5001`），就能看到上传页面了。

> 手机和电脑必须在**同一个 局域网** 下才能访问。

---

## 如何使用

1. 手机浏览器打开终端显示的地址
2. 拍要处理的错题照片（可以一次拍多张）
3. 调整纸张、留白等参数（一般保持默认即可）
4. 点击"生成错题本 Word"
5. 等待约 **10 秒**，Word 文档会自动下载
6. 用打印机打出来，在手写区订正

### Word 文档里有什么

- **原图**（可选）— 你拍的错题照片
- **题目原文**— OCR 识别出的文字
- **解题答案**— AI 给出的详细步骤和结果（LaTeX 公式会转为 Word 原生公式**所以你看到的公式是不变形的！！！**）
- **错因分析**— 你标记的错误类型和备注
- **手写订正区**— 每道题末尾的虚线表格，打印出来在上面订正

---

## 常见问题

**Q: 终端显示 "Address already in use"？**
A: macOS 的 AirPlay 占用了 5000 端口，已默认改为 5001。如果 5001 也被占用，可以设置环境变量 `PORT=5002`。

**Q: AI 解题不准怎么办？**
A: 拍照时尽量拍正、光线充足。OCR 识别的文字越准确，AI 解题效果越好。

**Q: 上传的文件会一直保留吗？**
A: 不会。超过 1 小时的图片会自动清理，保护隐私。

**Q: 每次启动都要等 85 秒吗？**
A: 只有第一次启动需要加载模型。启动后服务常驻后台，之后每次 OCR 只需约 **6 秒**。

**Q: 生成的 Word 文档里公式显示不正常？**
A: 确保已安装 Pandoc。Word 桌面版对 LaTeX 公式转换支持最好。

---

## 硬件加速

程序启动时会自动检测你的硬件并选择最优 OCR 后端：

| 硬件                   | 后端               | 加速引擎                 |
| -------------------- | ---------------- | -------------------- |
| NVIDIA GPU (CUDA)    | VLM（最高精度）        | vLLM（推荐）或 LMDeploy   |
| AMD GPU (ROCm)       | VLM（最高精度）        | vLLM-ROCm 或 LMDeploy |
| Apple Silicon (M 系列) | VLM（最高精度）        | MLX（推荐）或 MPS         |
| 无 GPU（仅 CPU）         | Pipeline（传统 OCR） | PaddleOCR            |

### macOS (Apple Silicon)

MLX 会自动生效，**无需额外配置**（用Mac的就偷着乐吧）。

### Linux + NVIDIA GPU (CUDA)

```bash
# 先确认 PyTorch 有 CUDA 支持
pip install torch --index-url https://download.pytorch.org/whl/cu124

# 安装 vLLM（推荐，速度最快，仅 Linux）
pip install vllm

# 或安装 LMDeploy（备选）
pip install lmdeploy
```

### Linux + AMD GPU (ROCm)

```bash
# 安装 ROCm 版 PyTorch（根据你的 ROCm 版本选择）
pip install torch --index-url https://download.pytorch.org/whl/rocm6.2

# 安装 ROCm 版 vLLM
pip install vllm-rocm

# 或安装 LMDeploy（原生支持 ROCm）
pip install lmdeploy
```

### Windows + NVIDIA GPU (CUDA)

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install lmdeploy
```

> Windows 不支持 vLLM（Linux 独占），LMDeploy 是推荐选项。

### 无 GPU（or你的GPU不支持加速）

完全不需要额外配置，程序自动使用不依赖 GPU 的传统 OCR pipeline。

---

## 文件说明

| 文件              | 作用                   |
| --------------- | -------------------- |
| `api-key.txt`   | 存放你的 API Key         |
| `app.py`        | 主程序                  |
| `config.py`     | 配置项                  |
| `run.sh`        | macOS / Linux 一键启动脚本 |
| `run.bat`       | Windows 一键启动脚本       |
| `uploads/`      | 临时存放上传的图片            |
| `outputs/`      | 生成的 Word 文档存放在这里     |
| `mineru_cache/` | MinerU 临时文件          |
