FROM python:3.11-bullseye

WORKDIR /app/worker

# Install system dependencies for ML libraries
RUN apt update && \
    apt install -y gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies - use PyTorch CPU-only index to speed up downloads
COPY ./worker/requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Pre-download F2LLM-v2-80M model (optional, reduces first-run latency)
# Comment out if building without ML dependencies
# RUN python3 -c "from transformers import AutoModel, AutoTokenizer; \
#     AutoTokenizer.from_pretrained('codefuse-ai/F2LLM-v2-80M'); \
#     AutoModel.from_pretrained('codefuse-ai/F2LLM-v2-80M', torch_dtype='auto')" || true

# Copy worker code
COPY ./worker ./

# Copy src code to /app/src (NOT inside worker)
COPY ./src /app/src

# Copy cli code for analyzer
COPY ./cli /app/cli

# Copy new shared infrastructure modules
COPY ./shared /app/shared
COPY ./plagiarism_core /app/plagiarism_core

# Make all relevant directories discoverable
ENV PYTHONPATH=/app/src:/app/plagiarism_core:/app/shared:/app


CMD ["python3", "-m", "worker.main"]
