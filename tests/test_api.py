import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Resolve src path relative to project root (parent of tests/)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "src"))

from app import app  # noqa: E402
import database as db_module


@pytest.fixture(scope="session")
def test_storage_dir():
    """Create temporary storage directory for tests."""
    temp_dir = tempfile.mkdtemp()
    os.makedirs(os.path.join(temp_dir, "s3_storage"), exist_ok=True)
    yield temp_dir
    # Cleanup handled by tempfile


@pytest.fixture(scope="session", autouse=True)
def set_env_vars(test_storage_dir):
    """Set up environment variables for tests."""
    # Set up environment for storage path
    os.environ["STORAGE_LOCAL_PATH"] = os.path.join(test_storage_dir, "s3_storage")

    # Mock database env vars
    os.environ["DB_HOST"] = "localhost"
    os.environ["DB_PORT"] = "5432"
    os.environ["DB_NAME"] = "test_db"
    os.environ["DB_USER"] = "test_user"
    os.environ["DB_PASS"] = "test_password_12345678"
    os.environ["DB_POOL_SIZE"] = "5"
    os.environ["DB_MAX_OVERFLOW"] = "10"
    os.environ["DB_POOL_TIMEOUT"] = "30"

    os.environ["RMQ_HOST"] = "localhost"
    os.environ["RMQ_PORT"] = "5672"
    os.environ["RMQ_USER"] = "test_mq_user"
    os.environ["RMQ_PASS"] = "test_mq_password_12345678"
    os.environ["RMQ_QUEUE_EXCHANGE"] = "test"
    os.environ["RMQ_QUEUE_ROUTING_KEY"] = "test"
    os.environ["RMQ_QUEUE_NAME"] = "test_queue"
    os.environ["RMQ_QUEUE_DEAD_LETTER_EXCHANGE"] = "test_dlx"
    os.environ["RMQ_QUEUE_ROUTING_KEY_DEAD_LETTER"] = "test.dead"
    os.environ["RMQ_QUEUE_DEAD_LETTER_NAME"] = "test_dead"

    os.environ["ENVIRONMENT"] = "development"
    os.environ["API_HOST"] = "0.0.0.0"
    os.environ["API_PORT"] = "8000"
    os.environ["API_WORKERS"] = "1"
    os.environ["CORS_ORIGINS"] = "http://localhost:3000"

    os.environ["DEFAULT_PLAGIARISM_THRESHOLD"] = "0.75"
    os.environ["SUPPORTED_LANGUAGES"] = "python,java,cpp"
    os.environ["MAX_FILE_SIZE"] = "1048576"
    os.environ["MAX_FILES_PER_BATCH"] = "100"

    os.environ["WORKER_CONCURRENCY"] = "4"
    os.environ["WORKER_PREFETCH_COUNT"] = "1"

    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["LOG_FORMAT"] = "json"

    os.environ["REDIS_HOST"] = "localhost"
    os.environ["REDIS_PORT"] = "6379"
    os.environ["REDIS_DB"] = "0"
    os.environ["REDIS_FINGERPRINT_TTL"] = "604800"
    os.environ["REDIS_USE_SSL"] = "false"

    os.environ["INVERTED_INDEX_MIN_OVERLAP_THRESHOLD"] = "0.15"


@pytest_asyncio.fixture
async def client():
    """Async test client fixture."""
    from clients.redis_client import RedisClient

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_session.commit = AsyncMock()
    mock_session.close = AsyncMock()

    async def mock_get_session():
        yield mock_session

    app.dependency_overrides[db_module.get_async_session] = mock_get_session

    if not hasattr(app.state, "redis_client"):
        app.state.redis_client = RedisClient()
    if not hasattr(app.state, "rabbitmq"):
        class DummyRabbitMQ:
            is_connected = False
            publish_message = AsyncMock()

        app.state.rabbitmq = DummyRabbitMQ()
    if not hasattr(app.state, "ws_manager"):
        class DummyWSManager:
            async def start(self):
                pass

            async def stop(self):
                pass

        app.state.ws_manager = DummyWSManager()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


class TestHealthEndpoint:
    async def test_health_check(self, client):
        response = await client.get("/health")
        # Returns 200 if all deps healthy, 503 if degraded
        assert response.status_code in (200, 503)
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert "checks" in data
        assert "db" in data["checks"]
        assert "redis" in data["checks"]
        assert "rmq" in data["checks"]

    async def test_version_endpoint(self, client):
        response = await client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "service" in data

    async def test_root_endpoint(self, client):
        response = await client.get("/")
        assert response.status_code in (200, 302)  # Either redirect or 200 if served


class TestPlagiarismEndpoints:
    async def test_get_task_not_found(self, client):
        response = await client.get(
            "/plagitype/plagiarism/tasks/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

    async def test_get_task_invalid_uuid(self, client):
        response = await client.get("/plagitype/plagiarism/tasks/not-a-uuid")
        assert response.status_code == 422

    async def test_get_task_results_not_found(self, client):
        response = await client.get(
            "/plagitype/plagiarism/tasks/00000000-0000-0000-0000-000000000000/results"
        )
        assert response.status_code == 404

    async def test_get_task_results_invalid_uuid(self, client):
        response = await client.get("/plagitype/plagiarism/tasks/not-a-uuid/results")
        assert response.status_code == 422


class TestFileEndpoints:
    async def test_get_files(self, client):
        response = await client.get("/plagitype/plagiarism/files")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    async def test_get_file_content_invalid_uuid(self, client):
        response = await client.get("/plagitype/plagiarism/files/not-a-uuid/content")
        assert response.status_code == 422

    async def test_get_file_content_not_found(self, client):
        response = await client.get(
            "/plagitype/plagiarism/files/00000000-0000-0000-0000-000000000000/content"
        )
        assert response.status_code == 404


class TestResultsEndpoints:
    async def test_get_all_results(self, client):
        response = await client.get("/plagitype/plagiarism/results")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
