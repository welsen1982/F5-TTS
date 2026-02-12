# 恢复使用官方 PyTorch 镜像 (已配置 Docker Daemon 代理)
FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-devel

USER root

ARG DEBIAN_FRONTEND=noninteractive

LABEL github_repo="https://github.com/welsen1982/F5-TTS.git"

# 切换 APT 国内源 (阿里云)
RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list \
    && sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list

RUN set -x \
    && apt-get update \
    && apt-get -y install wget curl man git less openssl libssl-dev unzip unar build-essential aria2 tmux vim \
    && apt-get install -y openssh-server sox libsox-fmt-all libsox-fmt-mp3 libsndfile1-dev ffmpeg \
    && apt-get install -y librdmacm1 libibumad3 librdmacm-dev libibverbs1 libibverbs-dev ibverbs-utils ibverbs-providers \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean
    
WORKDIR /workspace

# 配置 pip 国内源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 直接复制本地代码到容器
COPY . /workspace/F5-TTS

# 安装依赖
RUN cd F5-TTS \
    && pip install -e . --no-cache-dir

# 单独安装 WeTextProcessing 并预热缓存（避免启动时编译耗时）
# 注意：WeTextProcessing 依赖 pynini，可能需要较长安装时间
RUN python -c "from f5_tts.model.text_normalizer import _global_normalizer; _global_normalizer.initialize()" || true
    
ENV SHELL=/bin/bash

VOLUME /root/.cache/huggingface/hub/
VOLUME /root/.cache/f5_tts/tn_cache/

EXPOSE 8008

WORKDIR /workspace/F5-TTS

# 设置默认环境变量
ENV MAX_CONCURRENCY=3
ENV F5TTS_MODEL=F5TTS_v1_Base

# 默认启动 FastAPI 服务
CMD ["uvicorn", "f5_tts.runtime.fastapi.app:app", "--host", "0.0.0.0", "--port", "8008"]
