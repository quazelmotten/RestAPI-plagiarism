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

# Make src discoverable
ENV PYTHONPATH=/app/src

# Make CLI executable
RUN chmod +x /app/src/plagiarism/cli.py

CMD ["python3", "worker.py"]
