FROM python:3.11-bullseye

WORKDIR /app/worker

# Install system dependencies for ML libraries
RUN apt update && \
    apt install -y gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY ./worker/requirements.txt ./
RUN pip install --upgrade pip --index-url https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn && \
    pip install -r requirements.txt --index-url https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

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
