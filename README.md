# Source Code Plagiarism Detection API

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![RabbitMQ](https://img.shields.io/badge/Rabbitmq-FF6600?style=for-the-badge&logo=rabbitmq&logoColor=white)

## About

A comprehensive REST API for detecting plagiarism in source code files. Built using FastAPI for the REST API and RabbitMQ with Celery-style workers for background processing.

Using the REST API, users submit code files for plagiarism analysis. The worker processes the files asynchronously and stores the results in PostgreSQL. If an error occurs during processing, the task is sent to a dead-letter queue for later review.

**Python version 3.11+ is required for the web application to work correctly**

### Repository Structure:
- **src/** - FastAPI application with plagiarism detection endpoints
- **worker/** - Background worker for processing plagiarism checks
- **database/** - Database migrations
- **docker-compose.yml** - Docker orchestration for all services

## API Endpoints

### Plagiarism Detection

**POST /plagiarism/check** - Submit two files for plagiarism comparison
- Upload two source code files
- Returns a task ID for tracking

**GET /plagiarism/{task_id}** - Get plagiarism check results
- Retrieve similarity score and matching segments

## Getting Started

### Option 1: Docker (Recommended)

To run the entire application stack:

```shell
docker-compose up -d --build
```

The API will be available at `http://localhost:8000`

To stop the application:
```shell
docker-compose down
```

### Option 2: Manual Setup

#### Start the API

1. Go to the directory `src`
```shell
cd src
```

2. Create `.env` file:
```shell
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
```shell
pip install -r requirements.txt
```

5. Run the API:
```shell
uvicorn app:app --reload
```

#### Start the Worker

1. Go to the directory `worker`
```shell
cd worker
```

2. Create `.env` file with the same variables as above

3. Install packages:
```shell
pip install -r requirements.txt
```

4. Run the worker:
```shell
python3 worker.py
```

## Database Setup

To set up the database schema:

1. Go to the directory `database`
```shell
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
```shell
alembic upgrade head
```

## Architecture

The system uses a producer-consumer pattern:
- **API** receives file uploads and publishes tasks to RabbitMQ
- **Worker** consumes tasks from the queue and performs plagiarism analysis
- **Database** stores task status and results
- **Dead Letter Queue** handles failed tasks for retry or review

## API Documentation

When the API is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Development

### Adding New Features

The codebase is organized as follows:
- `src/plagiarism/` - Plagiarism detection logic and API routes
- `src/models/` - SQLAlchemy database models
- `worker/engines/engine_plagiarism/` - Plagiarism analysis implementation
- `src/rabbit.py` - RabbitMQ connection management
- `src/startup/` - Application startup tasks

### Testing

Run tests (when implemented):
```shell
pytest
```

## License

This project is for educational use at the university.
