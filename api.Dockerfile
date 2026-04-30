# Build stage for React frontend
FROM node:20-alpine as frontend-build

WORKDIR /frontend

# Copy package files
COPY frontend/package*.json ./
RUN npm install

# Copy source and build
COPY frontend/ ./
RUN npm run build

# Python API stage
FROM python:3.11-bullseye as base

WORKDIR /app

# Install system dependencies for WeasyPrint (PDF generation)
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY ./src/requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy Python source
COPY ./src ./

# Copy additional required modules
COPY ./cli ./cli
COPY ./worker ./worker
COPY ./shared ./shared
COPY ./plagiarism_core ./plagiarism_core
COPY ./database ./database

# Copy built frontend from previous stage
COPY --from=frontend-build /frontend/dist ./frontend/dist

ENV PYTHONPATH=/app

EXPOSE 8000

# Production mode - no reload
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
