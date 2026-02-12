## 项目概览
- 目标：将当前以 Gradio/CLI 为主的 F5‑TTS 推理能力，封装为稳定、可观测、可扩展的 FastAPI 生产服务。
- 复用点：核心推理流程与分块拼接在 [infer/utils_infer.py](file:///home/zju/projects/F5-TTS/src/f5_tts/infer/utils_infer.py)，模型封装在 [api.py](file:///home/zju/projects/F5-TTS/src/f5_tts/api.py)，vocoder 加载与缓存逻辑现成可用。
- 运行环境：沿用现有 Docker 基础镜像 [Dockerfile](file:///home/zju/projects/F5-TTS/Dockerfile)，增加 FastAPI/uvicorn 依赖与启动命令。

## 服务架构
- 进程模型：单进程 FastAPI + 同步推理；可选引入队列/工作线程以控制 GPU 并发。
- 设备管理：首次启动完成模型与 vocoder 预热并驻留 GPU；通过环境变量选择模型与设备（如 CUDA/ROCm/CPU fallback）。
- 配置管理：使用环境变量或 .toml 统一管理推理参数（采样步数、CFG、Sway、分块长度等），复用 [infer/examples/basic/basic.toml](file:///home/zju/projects/F5-TTS/src/f5_tts/infer/examples/basic/basic.toml)。

## API 设计
- POST /tts：执行 TTS 推理
  - 请求：JSON 或 multipart/form-data，包含 gen_text；可选 ref_audio（文件上传或 URL）、ref_text、说话人/风格参数、语言标记。
  - 响应：返回 WAV base64 或二进制流，同时返回采样率、时长、使用参数、日志信息。
- POST /tts/batch：批量生成（受队列保护），返回批处理结果列表。
- GET /health：健康检查（模型是否已加载、显存预算）。
- POST /warmup：显式预热指定参数（可用于滚动部署）。
- GET /version：返回模型与代码版本；暴露 [pyproject.toml](file:///home/zju/projects/F5-TTS/pyproject.toml) 内版本号。

## 推理流程映射
- 文本与参考处理：沿用 [utils_infer.convert_char_to_pinyin / get_tokenizer](file:///home/zju/projects/F5-TTS/src/f5_tts/infer/utils_infer.py#L31-L66)。
- 分块与拼接：复用 [infer_batch_process](file:///home/zju/projects/F5-TTS/src/f5_tts/infer/utils_infer.py#L433-L577) 与交叉淡入淡出策略。
- vocoder：使用 [load_vocoder](file:///home/zju/projects/F5-TTS/src/f5_tts/infer/utils_infer.py#L103-L143) 选择 Vocos/BigVGAN；支持 Hugging Face 缓存卷挂载。
- API 封装：用 [api.F5TTS](file:///home/zju/projects/F5-TTS/src/f5_tts/api.py#L23-L85) 管理模型生命周期，统一调用 [infer](file:///home/zju/projects/F5-TTS/src/f5_tts/api.py#L98-L149)。

## 并发与队列
- 策略：限流 + 队列（如 asyncio.Queue），最大并发 1–N（依据显存与 batch 策略）；大文本自动分块并行在单请求内完成。
- 超时：为每个任务设定总/分块超时；提供取消与清理（释放上下文）。

## 观测与可靠性
- 日志：结构化日志（请求 ID、耗时、显存峰值、参数摘要）。
- 指标：集成 Prometheus 指标（请求数、RTF、失败率、GPU 使用率可选）。
- 健康：/health 与 /warmup；就绪探针在预热完成后返回成功。
- 错误处理：统一异常中间件，用户输入校验（pydantic 模型），安全限制（文件大小、文本长度）。

## 部署与容器
- 依赖：在镜像中添加 fastapi、uvicorn、prometheus-client（可选）；保留 ffmpeg、torch 版本与 CUDA 对齐。
- 启动：uvicorn app:app --host 0.0.0.0 --port 8000；K8s/Compose 通过 GPU 设备暴露与 HF 缓存卷挂载（参考 README 的 compose 示例）。
- 资源：环境变量控制显存水位与 batch 参数；支持滚动升级（先 warmup 再切流量）。

## 安全与配额
- 输入限制：最大音频/文本大小；禁止任意路径访问，仅支持上传/URL 白名单。
- 配额：基于令牌桶或简单计数器限制每 IP 请求速率与并发。

## 交付物
- 新增模块：src/f5_tts/runtime/fastapi/app.py（服务入口）
- 配置：examples/fastapi.toml（默认推理参数）；.env（环境变量样例）。
- Docker：扩展 Dockerfile 或新建 dockerfiles/Dockerfile.fastapi；提供 Compose 示例。
- 文档：README 小节“FastAPI 部署与使用”。

## 验证与基准
- 正确性：对照现有 CLI/Gradio 在同参数下的生成一致性（RTF 与音质）。
- 性能：单请求与批处理的延迟、RTF；并发压力测试。

## 可选增强
- 流式输出：支持 chunk 生成的分段流式传输（Server‑Sent Events 或分块下载）。
- 多语言/多风格：暴露 tokenizer/语言参数与风格权重配置。
- Triton/TRT‑LLM：与现有 [runtime/triton_trtllm](file:///home/zju/projects/F5-TTS/src/f5_tts/runtime/triton_trtllm) 对接，作为后端替换以提升吞吐。

——请确认以上方案；确认后我将按该结构落地代码、容器与文档。