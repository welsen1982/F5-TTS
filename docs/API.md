# F5-TTS API 接口文档

本文档详细说明了 F5-TTS FastAPI 服务提供的 HTTP 接口。

## 基础信息
- **默认端口**：`8000`（Docker 部署时建议映射）
- **基础路径**：`/`
- **认证**：暂无（建议在网关层配置）

## 1. 系统接口

### 1.1 健康检查
用于 Kubernetes 存活探针（Liveness Probe）或服务监控。

- **URL**: `/health`
- **Method**: `GET`
- **响应示例**:
  ```json
  {
    "status": "ok",
    "loaded": true,
    "device": "cuda",
    "mel_spec_type": "vocos",
    "model_name": "F5TTS_v1_Base"
  }
  ```

### 1.2 版本信息
返回当前服务的版本信息。

- **URL**: `/version`
- **Method**: `GET`
- **响应示例**:
  ```json
  {
    "name": "f5-tts",
    "version": "1.1.15"
  }
  ```

### 1.3 模型预热
显式触发一次短音频生成，用于 Kubernetes 就绪探针（Readiness Probe）或冷启动优化。

- **URL**: `/warmup`
- **Method**: `POST`
- **响应示例**:
  ```json
  {
    "status": "ok",
    "sample_rate": 24000,
    "duration_sec": 1.5
  }
  ```

---

## 2. 语音合成接口 (TTS)

### 2.1 单次合成
核心接口，支持通过上传文件或 URL 提供参考音频。

- **URL**: `/tts`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data` 或 `application/json`

#### 请求参数 (Multipart/Form-Data)

| 字段名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `request` | string (JSON) | 否 | 包含文本与生成参数的 JSON 字符串（见下表） |
| `ref_audio` | file | 否 | 参考音频文件（WAV/MP3/FLAC），优先级高于 `ref_audio_url` |
| `gen_text` | string | 否 | 待生成的文本（若未在 `request` JSON 中提供） |
| `ref_text` | string | 否 | 参考音频对应的文本（可选，为空则自动识别） |
| `ref_audio_url` | string | 否 | 参考音频的可访问 URL |

**Request JSON 结构**:
```json
{
  "gen_text": "需要生成的文本",
  "ref_text": "参考音频的文本",
  "ref_audio_url": "http://example.com/ref.wav",
  "params": {
    "nfe_step": 32,
    "cfg_strength": 2.0,
    "speed": 1.0,
    "fix_duration": null
  }
}
```

#### 推理参数 (params 对象)

| 参数名 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `nfe_step` | int | 32 | 推理步数，越高质量越好但速度越慢（建议 16-64） |
| `cfg_strength` | float | 2.0 | Classifier-Free Guidance 强度，控制对参考音频的保真度 |
| `speed` | float | 1.0 | 语速倍率 |
| `sway_sampling_coef` | float | -1.0 | 采样系数（通常保持默认） |
| `fix_duration` | float | null | 固定输出时长（秒），`null` 为自动计算 |

#### 响应结构
```json
{
  "audio_base64": "UklGRi...",  // WAV 格式的 Base64 编码字符串
  "sample_rate": 24000,
  "duration_sec": 3.5,
  "seed": 123456,
  "info": {
    "request_id": "a1b2c3d4",
    "model": "F5TTS_v1_Base",
    "device": "cuda",
    "params": { ... }
  }
}
```

#### 调用示例 (Python)
```python
import requests
import json

url = "http://localhost:8000/tts"
files = {
    'ref_audio': open('ref.wav', 'rb')
}
data = {
    'gen_text': "你好，世界",
    'ref_text': "这是参考文本",
    # 或者将复杂参数打包为 JSON 字符串
    # 'request': json.dumps({...}) 
}
response = requests.post(url, files=files, data=data)
result = response.json()
```

---

### 2.2 批量合成
用于一次性处理多个请求，受服务端并发队列控制。

- **URL**: `/tts/batch`
- **Method**: `POST`
- **Content-Type**: `application/json`

#### 请求参数
接收一个数组，每个元素结构同单次请求（不支持文件上传，仅支持 URL 或默认参考音频）。

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

#### 响应结构
```json
{
  "request_id": "batch_123",
  "results": [
    {
      "audio_base64": "...",
      "sample_rate": 24000,
      "duration_sec": 2.1
    },
    {
      "audio_base64": "...",
      "sample_rate": 24000,
      "duration_sec": 3.4
    }
  ]
}
```

## 错误码
- **200**: 成功
- **422**: 参数校验错误（如缺少 `gen_text`）
- **500**: 服务端内部错误（如显存不足、模型加载失败）

## 部署配置
可通过环境变量调整服务行为：
- `MAX_CONCURRENCY`: 最大并发请求数（默认 1）
- `F5TTS_MODEL`: 模型名称（默认 `F5TTS_v1_Base`）
- `F5TTS_DEVICE`: 指定设备 (`cuda`, `cpu`, `mps`)
- `HF_CACHE_DIR`: Hugging Face 模型缓存目录
