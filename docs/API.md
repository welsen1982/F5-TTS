# F5-TTS API 接口文档

本文档详细说明了 F5-TTS FastAPI 服务提供的 HTTP 接口规范。

## 基础信息
- **默认端口**：`8008`（Docker 部署时默认暴露端口）
- **生产环境**：`https://tts.duomi365.work:91`
- **基础路径**：`/`
- **认证方式**：API Key 认证
  - Header 字段：`X-API-Key`
  - 环境变量配置：`F5_TTS_API_KEY`

## 部署配置 (环境变量)
| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `F5_TTS_API_KEY` | - | **必填**。API 认证密钥，用于保护敏感接口。 |
| `ALLOWED_ORIGINS` | `*` | 允许的 CORS 来源，多个域名用逗号分隔。 |
| `ENABLE_TEXT_NORMALIZATION` | `true` | 是否启用文本标准化。支持自动处理：数字、日期、时间、货币、车牌号（如“京A88888”）、详细地址（如“北京市朝阳区...”）等。 |
| `MAX_CONCURRENCY` | `1` | 最大并发请求数，超出限制的请求将排队等待。 |
| `F5TTS_MODEL` | `F5TTS_v1_Base` | 模型名称。 |
| `F5TTS_DEVICE` | 自动检测 | 指定推理设备 (`cuda`, `cpu`, `mps`, `xpu`)。 |
| `HF_CACHE_DIR` | - | Hugging Face 模型缓存目录。 |

---

## 1. 系统管理接口

### 1.1 健康检查 (Health Check)
用于 Kubernetes 存活探针（Liveness Probe）或服务监控。

- **URL**: `/health`
- **Method**: `GET`
- **Auth**: 不需要

**响应示例 (200 OK)**:
```json
{
  "status": "ok",
  "loaded": true,           // 模型是否已加载
  "device": "cuda",         // 当前运行设备
  "mel_spec_type": "vocos", // 频谱类型
  "model_name": "F5TTS_v1_Base"
}
```

### 1.2 版本信息 (Version Info)
获取当前服务的版本信息。

- **URL**: `/version`
- **Method**: `GET`
- **Auth**: 不需要

**响应示例 (200 OK)**:
```json
{
  "name": "f5-tts",
  "version": "1.1.15"
}
```

### 1.3 模型预热 (Warmup)
显式触发一次短音频生成（8步推理），用于冷启动优化或验证推理能力。

- **URL**: `/warmup`
- **Method**: `POST`
- **Auth**: 需要 (`X-API-Key`)

**响应示例 (200 OK)**:
```json
{
  "status": "ok",
  "sample_rate": 24000,
  "duration_sec": 1.5
}
```

---

## 2. 语音合成接口 (TTS)

### 通用数据结构

#### InferenceParams (推理参数)
用于控制生成效果的参数对象，所有 TTS 接口均通用。

| 参数名 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `nfe_step` | int | 32 | 推理步数。值越大画质/音质越高，但速度越慢。建议范围 16-64。 |
| `cfg_strength` | float | 2.0 | Classifier-Free Guidance 强度。控制对参考音频风格的保真度。 |
| `speed` | float | 1.0 | 语速倍率。`1.0` 为原速，`>1.0` 变快，`<1.0` 变慢。 |
| `fix_duration` | float | null | 强制输出时长（秒）。若设置，将忽略 `speed` 参数。 |
| `target_rms` | float | 0.1 | 目标音频的均方根振幅（音量控制）。 |
| `cross_fade_duration` | float | 0.15 | 拼接片段时的淡入淡出时长（秒）。 |
| `sway_sampling_coef` | float | -1.0 | 采样系数。通常保持默认值 `-1.0`。 |
| `seed` | int | null | 随机种子。若指定，可复现生成结果。 |

---

### 2.1 单次合成 (Single TTS)
核心接口，支持多种方式传入参考音频（文件上传或 URL）。

- **URL**: `/tts`
- **Method**: `POST`
- **Auth**: 需要 (`X-API-Key`)
- **Content-Type**: `application/json` 或 `multipart/form-data`

#### 请求方式 A: JSON Body
适用于参考音频为 URL 或使用默认参考音频的场景。

**Request Body**:
```json
{
  "gen_text": "需要生成的文本内容",
  "ref_text": "参考音频对应的文本（可选，为空则自动识别）",
  "ref_audio_url": "http://example.com/ref.wav",
  "params": {
    "nfe_step": 32,
    "speed": 1.0,
    "seed": 42
  }
}
```

#### 请求方式 B: Multipart Form
适用于直接上传参考音频文件的场景。

**Form Fields**:
- `gen_text`: (string) 待生成文本
- `ref_text`: (string, 可选) 参考文本
- `ref_audio`: (file, 可选) 参考音频文件 (.wav, .mp3 等)
- `request`: (string, 可选) 包含复杂参数的 JSON 字符串，例如 `{"params": {"nfe_step": 64}}`

#### 响应 (200 OK)
```json
{
  "audio_base64": "UklGRi...",  // WAV 格式音频的 Base64 编码
  "sample_rate": 24000,         // 采样率
  "duration_sec": 3.5,          // 音频时长（秒）
  "seed": 123456,               // 本次生成使用的种子
  "info": {
    "request_id": "a1b2c3d4",
    "model": "F5TTS_v1_Base",
    "device": "cuda",
    "params": { ... }           // 实际使用的推理参数
  }
}
```

#### 调用示例 (Python)
```python
import requests
import json

# 生产环境地址
url = "https://tts.duomi365.work:91/tts"
headers = {"X-API-Key": "YOUR_API_KEY"}

# 方式 1: 上传音频文件
files = {'ref_audio': open('ref.wav', 'rb')}
data = {
    'gen_text': "你好，世界",
    'ref_text': "这是参考音频的文本",
    'request': json.dumps({"params": {"speed": 1.2}}) # 额外参数
}
response = requests.post(url, headers=headers, files=files, data=data)

# 方式 2: 使用 URL
json_payload = {
    "gen_text": "测试文本",
    "ref_audio_url": "http://example.com/ref.wav",
    "params": {"nfe_step": 16}
}
response = requests.post(url, headers=headers, json=json_payload)

result = response.json()
print(f"Generated audio length: {result['duration_sec']}s")
```

---

### 2.2 批量合成 (Batch TTS)
用于一次性提交多个合成任务。任务将在服务端按顺序或并发（取决于 `MAX_CONCURRENCY`）执行。

- **URL**: `/tts/batch`
- **Method**: `POST`
- **Auth**: 需要 (`X-API-Key`)
- **Content-Type**: `application/json`

#### 请求参数
接收一个数组，每个元素为一个 TTS 请求对象（不支持文件上传，仅支持 URL 或默认参考音频）。

**Request Body**:
```json
[
  {
    "gen_text": "第一句话",
    "ref_audio_url": "http://example.com/ref1.wav",
    "params": { "speed": 1.0 }
  },
  {
    "gen_text": "第二句话",
    "ref_text": "参考文本",
    "params": { "speed": 1.2 }
  }
]
```

#### 响应 (200 OK)
```json
{
  "request_id": "batch_123456",
  "results": [
    {
      "audio_base64": "...",
      "sample_rate": 24000,
      "duration_sec": 2.1,
      "seed": 111
    },
    {
      "audio_base64": "...",
      "sample_rate": 24000,
      "duration_sec": 3.4,
      "seed": 222
    }
  ]
}
```

## 错误码
| 状态码 | 含义 | 说明 |
| :--- | :--- | :--- |
| **200** | OK | 请求成功 |
| **401** | Unauthorized | 未提供 `X-API-Key` |
| **403** | Forbidden | 提供的 `X-API-Key` 无效 |
| **422** | Unprocessable Entity | 参数校验错误（如缺少 `gen_text`） |
| **500** | Internal Server Error | 服务端内部错误（如模型加载失败、显存不足） |
