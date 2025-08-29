FROM runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /workspace

# Copy only necessary files first (for better Docker layer caching)
COPY ComfyUI/ /workspace/ComfyUI/
COPY Dockerfile .gitignore /workspace/

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git wget curl build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install ComfyUI requirements
RUN pip install --no-cache-dir -r ComfyUI/requirements.txt

# Install custom nodes requirements with better error handling
RUN find ComfyUI/custom_nodes -name "requirements.txt" -not -path "*/.*" | \
    while read req_file; do \
        echo "Installing requirements from: $req_file"; \
        pip install --no-cache-dir -r "$req_file" || echo "Failed to install $req_file, continuing..."; \
    done

# Create models directory structure (will be mounted from network storage)
RUN mkdir -p /workspace/ComfyUI/models/{checkpoints,vae,loras,controlnet,clip_vision,style_models,embeddings,diffusers,unet}

# Create comprehensive startup script
RUN echo '#!/bin/bash\n\
cd /workspace/ComfyUI\n\
python main.py \\\n\
  --listen 0.0.0.0 \\\n\
  --port 8188 \\\n\
  --enable-cors-header \\\n\
  --max-upload-size 500 \\\n\
  --output-directory /workspace/ComfyUI/output \\\n\
  --temp-directory /workspace/ComfyUI/temp' > /start.sh && \
    chmod +x /start.sh

# Set environment variables
ENV PYTHONPATH=/workspace/ComfyUI:$PYTHONPATH
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8188
CMD ["/start.sh"]