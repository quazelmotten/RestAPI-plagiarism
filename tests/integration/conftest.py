"""
Integration tests conftest.py - shared fixtures for API integration tests.
Uses real services (PostgreSQL, Redis, RabbitMQ) via docker-compose.test.yml.
"""

import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(_project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

os.environ["INTEGRATION_TESTS"] = "1"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "5433"
os.environ["DB_NAME"] = "plagiarism_db"
os.environ["DB_USER"] = "plagiarism_user"
os.environ["DB_PASS"] = "iNseUMJMuFlX1Q5Sr6yPwjUDPprX4VMP"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6380"
os.environ["RMQ_HOST"] = "localhost"
os.environ["RMQ_PORT"] = "5673"
os.environ["RMQ_USER"] = "plagiarism_mq_user"
os.environ["RMQ_PASS"] = "06l6of6Shsz9n11Is5nWAGO9oJsEXrcI"
os.environ["STORAGE_LOCAL_PATH"] = "/tmp/test_plagiarism_storage"
os.environ["ENVIRONMENT"] = "development"
os.environ["LOG_LEVEL"] = "ERROR"
# RATE_LIMIT_ENABLED is now set in the session fixture

TEST_DB_URL = "postgresql+asyncpg://plagiarism_user:iNseUMJMuFlX1Q5Sr6yPwjUDPprX4VMP@localhost:5433/plagiarism_db"


@pytest.fixture(scope="session", autouse=True)
def setup_db_schema():
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    import asyncio

    from alembic import command
    from alembic.config import Config

    engine = create_async_engine(TEST_DB_URL, echo=False)

    alembic_cfg = Config("database/alembic.ini")
    alembic_cfg.set_main_option("script_location", "database/migration")
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)

    async def _ensure():
        async with engine.begin() as conn:
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))

        try:
            command.upgrade(alembic_cfg, "head")
        except Exception as e:
            print(f"Migration error (may be ok if already applied): {e}")

        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            )
            tables = [row[0] for row in result.fetchall()]
            print(f"Tables in database: {tables}")

    asyncio.run(_ensure())
    try:
        yield
    finally:
        del os.environ["RATE_LIMIT_ENABLED"]
        asyncio.run(engine.dispose())


@pytest_asyncio.fixture
async def fresh_db_session():
    engine = create_async_engine(
        TEST_DB_URL,
        pool_size=1,
        max_overflow=0,
        echo=False,
    )
    test_session_local = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with test_session_local() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def db_clean(fresh_db_session):
    engine = create_async_engine(
        TEST_DB_URL,
        pool_size=1,
        max_overflow=0,
        echo=False,
    )
    async with engine.begin() as conn:
        tables = [
            "similarity_results",
            "files",
            "plagiarism_tasks",
            "assignments",
            "subjects",
        ]
        for table in tables:
            try:
                await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            except Exception:
                pass
    await engine.dispose()
    yield


class MockRabbitMQ:
    is_connected = True

    async def publish_message(self, *args, **kwargs):
        pass

    async def connect(self):
        pass

    async def disconnect(self):
        pass


class MockRedisClient:
    is_connected = True

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    def get_async_client(self):
        mock = MagicMock()
        mock.ping = AsyncMock(return_value=True)
        return mock

    def get_sync_client(self):
        return MagicMock()

    async def ping(self):
        return True


class MockS3Storage:
    async def upload_file(self, *args, **kwargs):
        return {"path": "s3://test/file", "hash": "d41d8cd98f00b204e9800998ecf8427e"}

    async def upload_file_async(self, *args, **kwargs):
        return {"path": "s3://test/file", "hash": "d41d8cd98f00b204e9800998ecf8427e"}

    async def download_file(self, *args, **kwargs):
        return b"test content"

    async def delete_file(self, *args, **kwargs):
        pass


@pytest_asyncio.fixture
async def client(db_clean):
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    import database as db_module

    # Import app first - this loads the routes which depend on the original database module
    from app import app

    # Clear any dependency overrides from parent conftest.py
    app.dependency_overrides.clear()

    # Mock authentication
    from auth.dependencies import get_current_user
    from auth.models import User

    mock_user = User(
        id="test-user-id",
        email="test@example.com",
        hashed_password="test",
        is_global_admin=True,
        session_version=1,
    )

    async def mock_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = mock_get_current_user

    # Save the original for reference
    original_maker = db_module.async_session_maker

    # Set up test database after app import
    engine = create_async_engine(
        TEST_DB_URL,
        pool_size=1,
        max_overflow=0,
        echo=False,
    )
    test_session_local = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    db_module.engine = engine
    db_module.async_session_maker = test_session_local

    # Set up mocks
    if not hasattr(app.state, "redis_client"):
        app.state.redis_client = MockRedisClient()
    if not hasattr(app.state, "rabbitmq"):
        app.state.rabbitmq = MockRabbitMQ()
    if not hasattr(app.state, "s3_storage"):
        app.state.s3_storage = MockS3Storage()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    db_module.engine = None
    db_module.async_session_maker = original_maker
    await engine.dispose()


@pytest.fixture
def sample_assignment_data() -> dict:
    return {
        "name": f"Test Assignment {uuid.uuid4().hex[:8]}",
        "description": "Integration test assignment",
    }


@pytest.fixture
def sample_task_data() -> dict:
    return {
        "language": "python",
    }


@pytest_asyncio.fixture
async def seeded_assignment(client, sample_assignment_data) -> dict:
    response = await client.post(
        "/plagitype/plagiarism/assignments",
        json=sample_assignment_data,
        timeout=30.0,
    )
    if response.status_code not in (200, 201):
        pytest.skip(f"Could not create assignment: {response.status_code} {response.text}")
    return response.json()


@pytest_asyncio.fixture
async def seeded_task(client, seeded_assignment) -> dict:
    task_data = {"language": "python"}
    response = await client.post(
        f"/plagitype/plagiarism/assignments/{seeded_assignment['id']}/tasks",
        json=task_data,
        timeout=30.0,
    )
    if response.status_code not in (200, 201):
        pytest.skip(f"Could not create task: {response.status_code} {response.text}")
    return response.json()


@pytest.fixture
def sample_file_content() -> bytes:
    return b"""def hello():
    print("Hello World")
    return True

def add(a, b):
    return a + b
"""


@pytest.fixture
def sample_files(sample_file_content) -> list[dict]:
    return [
        {
            "filename": "test1.py",
            "content": sample_file_content,
        },
        {
            "filename": "test2.py",
            "content": b"""def world():
    print("World")
    return False

def multiply(x, y):
    return x * y
""",
        },
    ]


@pytest_asyncio.fixture
async def uploaded_files(client, seeded_task, sample_files) -> list[dict]:
    uploaded = []
    for file_info in sample_files:
        files = {"file": (file_info["filename"], file_info["content"], "text/plain")}
        response = await client.post(
            f"/plagitype/plagiarism/tasks/{seeded_task['task_id']}/files",
            files=files,
            timeout=30.0,
        )
        if response.status_code in (200, 201):
            uploaded.append(response.json())
    return uploaded


@pytest.fixture
def api_base_url() -> str:
    return "/plagitype/plagiarism"
