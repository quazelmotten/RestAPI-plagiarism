# Source Code Plagiarism Detection API

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![RabbitMQ](https://img.shields.io/badge/Rabbitmq-FF6600?style=for-the-badge&logo=rabbitmq&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)

## About

A comprehensive REST API for detecting plagiarism in source code files. Built using FastAPI for the REST API and RabbitMQ with Celery-style workers for background processing.

Using the REST API, users submit code files for plagiarism analysis. The worker processes the files asynchronously and stores the results in PostgreSQL. If an error occurs during processing, the task is sent to a dead-letter queue for later review.

**Python version 3.11+ is required for the web application to work correctly**

### Repository Structure:
- **src/** - FastAPI application with plagiarism detection endpoints
- **worker/** - Background worker for processing plagiarism checks  
- **frontend/** - React frontend application
- **database/** - Database migrations
- **docker-compose.yml** - Docker orchestration for all services
- **scripts/** - Setup and testing scripts

## 🚀 Quick Start (One-Command Setup)

### Prerequisites
- Docker
- Docker Compose

### Option 1: Automatic Setup (Recommended)

Run the comprehensive setup script:

```bash
./scripts/setup-complete.sh
```

This will:
1. ✅ Check all prerequisites
2. ✅ Generate secure `.env` file with random passwords
3. ✅ Create necessary directories
4. ✅ Build all Docker images
5. ✅ Start all services (API, Worker, Database, RabbitMQ)
6. ✅ Wait for services to be healthy
7. ✅ Run a quick health check

**That's it!** Your application will be running at:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **RabbitMQ Management**: http://localhost:15672

### Option 2: Development Mode with Hot Reload

For development with hot reload enabled:

```bash
./scripts/setup-complete.sh dev
```

This starts the API with hot reload for rapid development.

### Option 3: Manual Docker Setup

If you prefer manual control:

```bash
# Generate environment file
./setup.sh

# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f
```

### Option 4: Manual Setup (Without Docker)

See [Manual Setup](#manual-setup) section below.

## 🧪 Testing

### Run Integration Tests

To verify everything is working correctly:

```bash
./scripts/test-integration.sh
```

This will test:
- ✅ API health endpoints
- ✅ Database connectivity
- ✅ RabbitMQ connectivity
- ✅ File upload functionality
- ✅ Plagiarism check workflow
- ✅ Frontend serving

### Run Smoke Test (Quick)

```bash
curl http://localhost:8000/health
```

## 🛠️ Development

### Frontend Development

The frontend is built with React and TypeScript.

**Prerequisites**: Node.js 20.19+ or 22.12+ is required.

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs at http://localhost:3000

### API Development

For API development with hot reload:

```bash
./scripts/setup-complete.sh dev
```

Or manually:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### Running Tests

#### Unit Tests

```bash
cd src
pytest
```

#### Integration Tests

```bash
./scripts/test-integration.sh
```

#### Load Tests

```bash
# Run 10 concurrent health checks
for i in {1..10}; do
  curl -s http://localhost:8000/health &
done
wait
```

## 📊 API Documentation

When the API is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### API Key Authentication

The API supports authentication via API keys in addition to JWT tokens. This is useful for programmatic access, CI/CD pipelines, and third-party integrations.

#### Creating an API Key

1. Login via `/auth/login` to get a JWT token
2. POST to `/auth/api-keys` with `{"name": "my-key-name", "expires_in_days": 30}`
3. Save the returned `raw_key` value - it won't be shown again!

Example:
```bash
# First, get a JWT token
curl -X POST http://localhost:8000/plagitype/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"your-password"}'

# Use the token to create an API key
curl -X POST http://localhost:8000/plagitype/auth/api-keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"My API Key","expires_in_days":30}'
```

#### Using an API Key

Include the `X-API-Key` header in your requests:

```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:8000/plagitype/plagiarism/tasks
```

#### Managing API Keys

- **List keys**: `GET /auth/api-keys` (requires authentication)
- **Create key**: `POST /auth/api-keys` (requires authentication)
- **Revoke key**: `DELETE /auth/api-keys/{key_id}` (requires authentication)

API keys can also be managed through the web UI in the Settings page at `/dashboard/settings`.

#### Security Notes

- API keys have the same permissions as the user who created them
- Keys are hashed (SHA-256) before storage - the raw key is only returned once during creation
- Expired keys are automatically rejected
- Revoked keys are permanently deleted

## 🏗️ Architecture

The system uses a producer-consumer pattern:
- **API** receives file uploads and publishes tasks to RabbitMQ
- **Worker** consumes tasks from the queue and performs plagiarism analysis
- **Database** stores task status and results
- **Dead Letter Queue** handles failed tasks for retry or review
- **Inverted Index** (Redis) enables fast candidate filtering for cross-task comparisons

### Performance Optimization

The system includes an **Inverted Index** for efficient cross-task plagiarism detection:

- **Without Inverted Index**: O(n×m) comparisons (new files × all existing files)
- **With Inverted Index**: Only O(n×k) comparisons (new files × viable candidates)

The inverted index uses Redis to store fingerprint-to-files mappings, allowing the system to:
1. Index all file fingerprints as they're processed
2. Quickly find candidate files that share significant fingerprint overlap
3. Skip detailed analysis for files below the similarity threshold (default: 15%)

This dramatically reduces processing time when the database contains thousands of files.

**Configuration**: 
- Set `INVERTED_INDEX_MIN_OVERLAP_THRESHOLD` in `.env` (default: 0.15 for 15%)
- Lower values = more thorough but slower
- Higher values = faster but may miss borderline cases

### Service Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│   API (8000) │────▶│  PostgreSQL │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   RabbitMQ   │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │    Worker    │
                    └──────────────┘
```

## 🔧 Manual Setup

### Start the API

1. Go to the directory `src`
```bash
cd src
```

2. Create `.env` file:
```bash
touch .env
```

3. Add environment variables:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=plagiarism_db
DB_USER=appuser
DB_PASS=password

RMQ_HOST=localhost
RMQ_PORT=5672
RMQ_USER=guest
RMQ_PASSWORD=guest

RMQ_QUEUE_EXCHANGE=plagiarism
RMQ_QUEUE_ROUTING_KEY=plagiarism
RMQ_QUEUE_NAME=plagiarism_queue
RMQ_QUEUE_DEAD_LETTER_EXCHANGE=plagiarism_dlx
RMQ_QUEUE_ROUTING_KEY_DEAD_LETTER=plagiarism.dead
RMQ_QUEUE_DEAD_LETTER_NAME=plagiarism_dead
```

4. Install packages:
```bash
pip install -r requirements.txt
```

5. Run the API:
```bash
uvicorn app:app --reload
```

### Start the Worker

1. Go to the directory `worker`
```bash
cd worker
```

2. Create `.env` file with the same variables as above

3. Install packages:
```bash
pip install -r requirements.txt
```

4. Run the worker:
```bash
python3 worker.py
```

## 🗄️ Database Setup

To set up the database schema:

1. Go to the directory `database`
```bash
cd database
```

2. Create `.env` file:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=plagiarism_db
DB_USER=appuser
DB_PASS=password
```

3. Run migrations:
```bash
alembic upgrade head
```

## 🐳 Docker Commands

```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api

# Stop all services
docker-compose down

# Stop and remove volumes (clears all data)
docker-compose down -v

# Restart a service
docker-compose restart api

# Scale workers
docker-compose up -d --scale worker=4
```

## 🔒 Security

The setup script automatically generates secure passwords for:
- Database password
- RabbitMQ password
- API secret key

**Never commit the `.env` file!** It's already in `.gitignore`.

## 📝 Environment Variables

See `.env.example` for all available environment variables and their descriptions.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `./scripts/test-integration.sh`
4. Submit a pull request

## 📄 License

This project is for educational use at the university.

## 🆘 Troubleshooting

### Services won't start

```bash
# Check what's running
docker-compose ps

# View logs
docker-compose logs <service-name>

# Restart everything
docker-compose down -v
docker-compose up -d --build
```

### Frontend not showing

The frontend is built into the API Docker image. If you need to rebuild:

```bash
docker-compose build --no-cache api
docker-compose up -d
```

### Database connection issues

Make sure the database is healthy before starting the API:

```bash
docker-compose up -d postgres
sleep 10
docker-compose up -d api worker
```
