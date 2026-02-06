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

# Install Python dependencies
COPY ./src/requirements.txt ./
RUN apt update && pip install --upgrade pip && pip3 install -r requirements.txt

# Copy Python source
COPY ./src ./

# Copy built frontend from previous stage
COPY --from=frontend-build /frontend/dist ./frontend/dist

EXPOSE 8000

ENTRYPOINT ["uvicorn", "app:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
