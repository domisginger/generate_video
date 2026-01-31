# Use specific version of nvidia cuda image
# FROM wlsdml1114/my-comfy-models:v1 as model_provider
# FROM wlsdml1114/multitalk-base:1.7 as runtime
FROM wlsdml1114/engui_genai-base_blackwell:1.1 as runtime

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_ENABLE_HF_TRANSFER=1

WORKDIR /

RUN pip install -U --no-cache-dir "huggingface_hub[hf_transfer]" runpod websocket-client && \
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /ComfyUI && \
    pip install -r /ComfyUI/requirements.txt && \
    mkdir -p /ComfyUI/custom_nodes

RUN set -eux; \
    cd /ComfyUI/custom_nodes; \
    git clone --depth 1 https://github.com/Comfy-Org/ComfyUI-Manager.git; \
    pip install -r ComfyUI-Manager/requirements.txt; \
    git clone --depth 1 https://github.com/city96/ComfyUI-GGUF; \
    pip install -r ComfyUI-GGUF/requirements.txt; \
    git clone --depth 1 https://github.com/kijai/ComfyUI-KJNodes; \
    pip install -r ComfyUI-KJNodes/requirements.txt; \
    git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite; \
    pip install -r ComfyUI-VideoHelperSuite/requirements.txt; \
    git clone --depth 1 https://github.com/kael558/ComfyUI-GGUF-FantasyTalking; \
    pip install -r ComfyUI-GGUF-FantasyTalking/requirements.txt; \
    git clone --depth 1 https://github.com/orssorbit/ComfyUI-wanBlockswap; \
    git clone --depth 1 https://github.com/kijai/ComfyUI-WanVideoWrapper; \
    pip install -r ComfyUI-WanVideoWrapper/requirements.txt; \
    git clone --depth 1 https://github.com/eddyhhlure1Eddy/IntelligentVRAMNode; \
    git clone --depth 1 https://github.com/eddyhhlure1Eddy/auto_wan2.2animate_freamtowindow_server; \
    git clone --depth 1 https://github.com/eddyhhlure1Eddy/ComfyUI-AdaptiveWindowSize; \
    cd ComfyUI-AdaptiveWindowSize/ComfyUI-AdaptiveWindowSize; \
    mv * ../

RUN set -eux; \
    wget -q https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors -O /ComfyUI/models/diffusion_models/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors; \
    wget -q https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors -O /ComfyUI/models/diffusion_models/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors; \
    wget -q https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/high_noise_model.safetensors -O /ComfyUI/models/loras/high_noise_model.safetensors; \
    wget -q https://huggingface.co/lightx2v/Wan2.2-Lightning/resolve/main/Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/low_noise_model.safetensors -O /ComfyUI/models/loras/low_noise_model.safetensors; \
    wget -q https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors -O /ComfyUI/models/clip_vision/clip_vision_h.safetensors; \
    wget -q https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors -O /ComfyUI/models/text_encoders/umt5-xxl-enc-bf16.safetensors; \
    wget -q https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors -O /ComfyUI/models/vae/Wan2_1_VAE_bf16.safetensors

COPY . .
COPY extra_model_paths.yaml /ComfyUI/extra_model_paths.yaml
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]