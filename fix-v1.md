# fix-v1 — 排障记录

## 问题一：OCR 超时

**现象**：上传图片后等待约 30 秒，前端显示"OCR 处理超时"。

**排查过程**：

1. 直接命令行调 `mineru` 对测试图片做 OCR：
   - `--backend pipeline` → 超时（缺 pipeline 模型）
   - `--backend vlm-auto-engine` → 首次 90s，之后每次 88s（模型都重新加载）

2. 发现 `mineru.json` 配置中 `models-dir.pipeline` 为空，只下了 VLM 模型。
   但 VLM 模式其实够用，不需要 pipeline 模型。

3. 根因：`config.py` 中 `OCR_TIMEOUT = 30`，而 MinerU 加载 2.3GB 模型到 Apple Silicon MLX 引擎需要约 **77 秒**，加上推理时间共约 **90 秒**。

**临时修复**：`OCR_TIMEOUT = 30` → `300`，并将每张图片单独调 `mineru` 改为 batch 调用（所有图一次 `mineru` 调用，模型只加载一次）。

---

## 问题二：局域网 IP 获取错误

**现象**：启动横幅显示 `http://172.18.0.1:5001`，这是 Docker 隧道地址，手机无法访问。

**排查过程**：

1. `ifconfig` 发现 `en0`（Wi-Fi）实际 IP 是 `192.168.0.216`，`utun84`（Docker）占了 `172.18.0.1`。
2. 原代码用 UDP connect 到 `10.254.254.254:1` 获取默认路由 IP，但 Docker 改了路由表导致返回隧道地址。
3. 改用 `8.8.8.8:53` 也一样（Docker 拦截了默认路由）。

**修复**：改为优先查询 Mac 的 `en0` / `en1` 网卡（`ipconfig getifaddr en0`），兜底扫 `ifconfig` 跳过 `lo0` 和 `utun` 等虚拟接口。

---

## 问题三：模型每次调用都重复加载

**现象**：每次上传都要等 90 秒，即使多次连续上传。

**排查过程**：

1. `mineru` CLI 每次执行都会启动一个临时 FastAPI 服务，处理完立刻销毁。模型在内存中只存活一次调用。
2. `mineru.cli.fast_api` 支持 `--enable-vlm-preload` 参数，可以在服务启动时预加载模型到 MLX 引擎。
3. 验证：预加载后通过 API 提交任务，单张图片 OCR 只需 **~6 秒**（推理时间）。

**修复方案**：改为常驻服务架构

- Flask 启动时用 `subprocess.Popen` 拉起 mineru-api 服务：
  ```
  /opt/anaconda3/bin/python -m mineru.cli.fast_api \
    --enable-vlm-preload true \
    --host 127.0.0.1 --port 52999
  ```
- `ocr_images()` 不再 `subprocess.run(["mineru", ...])`，改为 HTTP 请求：
  1. `POST /tasks` 上传图片（`backend=vlm-auto-engine`）
  2. 轮询 `GET /tasks/{id}` 直到 status 为 completed
  3. `GET /tasks/{id}/result` 获取 md_content
- Flask 退出时 `finally` 块关闭 mineru 服务进程

**踩坑记录**：

1. `fast_api` 不接受 `--backend` 参数（不像 `mineru` CLI）。但 `POST /tasks` 时必须显式传 `data={"backend": "vlm-auto-engine"}`，否则服务端用默认的 `hybrid-auto-engine` 会卡在 processing 状态。
2. `mineru --api-url` 客户端和服务端之间通信有 bug（`dict() got multiple values for keyword argument 'backend'`），需绕过 CLI 直接调 HTTP API。
3. MinerU 装在 conda 环境（`/opt/anaconda3/bin/python`），Flask 在 venv 环境。`_start_mineru_server()` 必须用 conda 的 Python 路径启动。

---

## 最终性能对比

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| 应用启动 | 无提示，首次调用 90s 超时 | 显示"正在加载模型"，约 85s 后可用 |
| 单张图片 OCR | 90s（含模型加载） | **~6s**（模型已在内存） |
| 多张图片 | 每张 90s | 每张 ~6s（共享模型） |
| 局域网 IP 检测 | 返回 Docker 地址 | 正确返回 `192.168.0.x` |
