import asyncio
import base64
import io
import logging
import os
import uuid
from pathlib import Path
from typing import Optional, List

import numpy as np
import soundfile as sf
import tomli
from fastapi import FastAPI, UploadFile, File, Body, Form, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from importlib.resources import files

from f5_tts.api import F5TTS


class InferenceParams(BaseModel):
    target_rms: float = 0.1
    cross_fade_duration: float = 0.15
    sway_sampling_coef: float = -1.0
    cfg_strength: float = 2.0
    nfe_step: int = 32
    speed: float = 1.0
    fix_duration: Optional[float] = None
    seed: Optional[int] = None


class TTSRequest(BaseModel):
    gen_text: str = Field(..., description="待生成的文本")
    ref_text: Optional[str] = Field("", description="参考音频的转写文本；为空则自动转写")
    ref_audio_url: Optional[str] = Field(None, description="参考音频的可访问 URL")
    language: Optional[str] = Field(None, description="参考音频语言提示（用于 ASR）")
    params: InferenceParams = Field(default_factory=InferenceParams)


class TTSBatchItem(BaseModel):
    gen_text: str
    ref_text: Optional[str] = ""
    ref_audio_url: Optional[str] = None
    language: Optional[str] = None
    params: InferenceParams = Field(default_factory=InferenceParams)


class TTSResponse(BaseModel):
    audio_base64: str
    sample_rate: int
    duration_sec: float
    seed: int
    info: dict


logger = logging.getLogger("f5tts")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

class AppState:
    def __init__(self):
        self.f5tts: Optional[F5TTS] = None
        
        # 尝试加载配置文件
        config_path = files("f5_tts").joinpath("infer/examples/fastapi/fastapi.toml")
        config = {}
        if config_path.exists():
            try:
                with config_path.open("rb") as f:
                    config = tomli.load(f)
                logger.info(f"Loaded config from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")

        # 优先级：环境变量 > 配置文件 > 默认值
        server_conf = config.get("server", {})
        
        # 并发数配置
        self.max_concurrency = int(os.environ.get(
            "MAX_CONCURRENCY", 
            server_conf.get("max_concurrency", 1)
        ))
        self.sema = asyncio.Semaphore(self.max_concurrency)
        logger.info(f"Max concurrency set to: {self.max_concurrency}")

        self.model_name = os.environ.get("F5TTS_MODEL", "F5TTS_v1_Base")
        self.device = os.environ.get("F5TTS_DEVICE", None)
        self.vocoder_local_path = os.environ.get("VOCODER_LOCAL_PATH", None)
        self.hf_cache_dir = os.environ.get("HF_CACHE_DIR", None)
        # 固定参考音频路径，支持环境变量覆盖
        self.default_ref_audio = os.environ.get(
            "DEFAULT_REF_AUDIO", 
            "/home/zju/projects/F5-TTS/data/ref_audio/aliyuntts-4sec.wav"
        )
        # 固定参考文本，支持环境变量覆盖
        self.default_ref_text = os.environ.get(
            "DEFAULT_REF_TEXT",
            "沈先生，你好，我是客服助手小黄，很高兴为您服务"
        )


state = AppState()
app = FastAPI(title="F5-TTS FastAPI Service", version="1.0")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _ensure_model_loaded():
    if state.f5tts is None:
        state.f5tts = F5TTS(
            model=state.model_name,
            device=state.device,
            vocoder_local_path=state.vocoder_local_path,
            hf_cache_dir=state.hf_cache_dir,
        )


async def _save_upload_to_temp(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "ref.wav").suffix or ".wav"
    tmp_path = Path(os.environ.get("TMPDIR", "/tmp")) / f"f5tts_{uuid.uuid4().hex}{suffix}"
    content = await upload.read()
    tmp_path.write_bytes(content)
    return tmp_path


def _wav_to_base64(wav: np.ndarray, sample_rate: int) -> str:
    buf = io.BytesIO()
    sf.write(buf, wav, sample_rate, format="WAV")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


@app.on_event("startup")
async def startup_event():
    logger.info("Starting up F5-TTS service...")
    try:
        # 在启动时预加载模型，避免首次请求延迟
        _ensure_model_loaded()
        logger.info(f"Model {state.model_name} loaded on {state.f5tts.device}")
    except Exception as e:
        logger.error(f"Failed to load model on startup: {e}")

@app.get("/health")
def health():
    try:
        loaded = state.f5tts is not None
        # 如果模型未加载，尝试推断应使用的设备
        if loaded:
            device = str(state.f5tts.device)
            mel_spec = state.f5tts.mel_spec_type
        else:
            import torch
            device = (
                "cuda"
                if torch.cuda.is_available()
                else "xpu"
                if torch.xpu.is_available()
                else "mps"
                if torch.backends.mps.is_available()
                else "cpu"
            )
            mel_spec = "unknown"
            
        return {
            "status": "ok", 
            "loaded": loaded, 
            "device": device, 
            "mel_spec_type": mel_spec,
            "model_name": state.model_name
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/warmup")
def warmup():
    try:
        _ensure_model_loaded()
        ref_file = str(files("f5_tts").joinpath("infer/examples/basic/basic_ref_en.wav"))
        wav, sr, _ = state.f5tts.infer(
            ref_file=ref_file,
            ref_text="Warm up the engine.",
            gen_text="This is a warmup run for the service.",
            target_rms=0.1,
            cross_fade_duration=0.0,
            sway_sampling_coef=-1.0,
            cfg_strength=2.0,
            nfe_step=8,
            speed=1.0,
            fix_duration=1.5,
            remove_silence=True,
            file_wave=None,
            file_spec=None,
            seed=42,
        )
        return {"status": "ok", "sample_rate": sr, "duration_sec": float(len(wav) / sr)}
    except Exception as e:
        logger.exception("Warmup failed")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.get("/version")
def version():
    try:
        pyproject_path = _project_root() / "pyproject.toml"
        with pyproject_path.open("rb") as f:
            data = tomli.load(f)
        return {"name": data["project"]["name"], "version": data["project"]["version"]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/tts", response_model=TTSResponse)
async def tts(
    request: Request,
    request_str: Optional[str] = Form(None, alias="request", description="JSON string of TTSRequest"),
    gen_text: Optional[str] = Form(None),
    ref_text: Optional[str] = Form(""),
    ref_audio_url: Optional[str] = Form(None),
    ref_audio: Optional[UploadFile] = File(None),
):
    req_id = uuid.uuid4().hex[:8]
    # 使用信号量控制并发
    async with state.sema:
        try:
            # 1. 尝试直接从 Body 解析 JSON (针对 Content-Type: application/json)
            # 注意：在 FastAPI 中，一旦定义了 Form/File 参数，Request 流通常会被消耗。
            # 如果是 application/json，request.form() 会报错或为空。
            # 我们需要先判断 Content-Type。
            content_type = request.headers.get("content-type", "")
            tts_request = None
            
            if "application/json" in content_type:
                try:
                    data = await request.json()
                    tts_request = TTSRequest(**data)
                except Exception as e:
                    logger.warning(f"Failed to parse body as json: {e}")
            
            # 2. 如果不是 JSON body，尝试从 Form 解析
            if tts_request is None:
                # 尝试解析 request_str (from form field 'request')
                if request_str:
                    try:
                        import json
                        data = json.loads(request_str)
                        tts_request = TTSRequest(**data)
                    except Exception as e:
                        logger.warning(f"Failed to parse form request json: {e}")
                
                # 3. 尝试从单独字段构建
                if tts_request is None:
                    if gen_text:
                        tts_request = TTSRequest(
                            gen_text=gen_text,
                            ref_text=ref_text,
                            ref_audio_url=ref_audio_url,
                            params=InferenceParams() # 使用默认参数
                        )
            
            if tts_request is None:
                raise ValueError("Missing gen_text or valid request JSON")

            _ensure_model_loaded()
            if ref_audio is not None:
                ref_path = await _save_upload_to_temp(ref_audio)
            elif tts_request.ref_audio_url:
                # 下载 URL 内容到临时文件
                import httpx

                ref_path = Path(os.environ.get("TMPDIR", "/tmp")) / f"f5tts_{uuid.uuid4().hex}.wav"
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.get(tts_request.ref_audio_url)
                    resp.raise_for_status()
                    ref_path.write_bytes(resp.content)
            else:
                # 使用预置的固定参考音频
                ref_path = Path(state.default_ref_audio)
                if not ref_path.exists():
                     # 回退到内置示例以防路径错误
                     logger.warning(f"Default ref audio not found at {ref_path}, using built-in example.")
                     ref_path = Path(files("f5_tts").joinpath("infer/examples/basic/basic_ref_en.wav"))

            params = tts_request.params
            
            # 使用 run_in_executor 将同步的 infer 调用移出事件循环
            loop = asyncio.get_running_loop()
            wav, sr, _ = await loop.run_in_executor(
                None, 
                lambda: state.f5tts.infer(
                    ref_file=str(ref_path),
                    ref_text=tts_request.ref_text or state.default_ref_text,
                    gen_text=tts_request.gen_text,
                    target_rms=params.target_rms,
                    cross_fade_duration=params.cross_fade_duration,
                    sway_sampling_coef=params.sway_sampling_coef,
                    cfg_strength=params.cfg_strength,
                    nfe_step=params.nfe_step,
                    speed=params.speed,
                    fix_duration=params.fix_duration,
                    remove_silence=True,
                    file_wave=None,
                    file_spec=None,
                    seed=params.seed,
                )
            )

            audio_b64 = _wav_to_base64(wav, sr)
            info = {
                "request_id": req_id,
                "model": state.model_name,
                "device": state.f5tts.device,
                "params": params.model_dump(),
            }
            return TTSResponse(
                audio_base64=audio_b64,
                sample_rate=sr,
                duration_sec=float(len(wav) / sr),
                seed=state.f5tts.seed,
                info=info,
            )
        except Exception as e:
            logger.exception("TTS failed %s", req_id)
            return JSONResponse(status_code=500, content={"status": "error", "message": str(e), "request_id": req_id})
        finally:
            try:
                if ref_audio is not None and "ref_path" in locals():
                    Path(ref_path).unlink(missing_ok=True)
            except Exception:
                pass


@app.post("/tts/batch")
async def tts_batch(items: List[TTSBatchItem]):
    req_id = uuid.uuid4().hex[:8]
    async with state.sema:
        try:
            _ensure_model_loaded()
            results = []
            for item in items:
                if item.ref_audio_url:
                    import httpx

                    ref_path = Path(os.environ.get("TMPDIR", "/tmp")) / f"f5tts_{uuid.uuid4().hex}.wav"
                    async with httpx.AsyncClient(timeout=60) as client:
                        resp = await client.get(item.ref_audio_url)
                        resp.raise_for_status()
                        ref_path.write_bytes(resp.content)
                else:
                    ref_path = Path(state.default_ref_audio)
                    if not ref_path.exists():
                         ref_path = Path(files("f5_tts").joinpath("infer/examples/basic/basic_ref_en.wav"))

                p = item.params
                wav, sr, _ = state.f5tts.infer(
                    ref_file=str(ref_path),
                    ref_text=item.ref_text or state.default_ref_text,
                    gen_text=item.gen_text,
                    target_rms=p.target_rms,
                    cross_fade_duration=p.cross_fade_duration,
                    sway_sampling_coef=p.sway_sampling_coef,
                    cfg_strength=p.cfg_strength,
                    nfe_step=p.nfe_step,
                    speed=p.speed,
                    fix_duration=p.fix_duration,
                    remove_silence=True,
                    file_wave=None,
                    file_spec=None,
                    seed=p.seed,
                )
                audio_b64 = _wav_to_base64(wav, sr)
                results.append(
                    {
                        "audio_base64": audio_b64,
                        "sample_rate": sr,
                        "duration_sec": float(len(wav) / sr),
                        "seed": state.f5tts.seed,
                    }
                )
                try:
                    if item.ref_audio_url:
                        Path(ref_path).unlink(missing_ok=True)
                except Exception:
                    pass
            return {"request_id": req_id, "results": results}
        except Exception as e:
            logger.exception("Batch TTS failed %s", req_id)
            return JSONResponse(status_code=500, content={"status": "error", "message": str(e), "request_id": req_id})
