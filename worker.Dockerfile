FROM python:3.11-bullseye

WORKDIR /app/worker

# Install dependencies
COPY ./worker/requirements.txt ./
RUN apt update && \
    pip install --upgrade pip && \
    pip install -r requirements.txt

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
