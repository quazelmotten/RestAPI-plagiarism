import logging
import os

import pytest

# Check if running integration tests - if so, skip autouse fixtures
RUNNING_INTEGRATION_TESTS = "INTEGRATION_TESTS" in os.environ

# Only set DB defaults if not already set AND not in integration tests
if not RUNNING_INTEGRATION_TESTS:
    os.environ.setdefault("STORAGE_LOCAL_PATH", "/tmp/test_s3_storage")
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_PORT", "5432")
    os.environ.setdefault("DB_NAME", "test_db")
    os.environ.setdefault("DB_USER", "test_user")
    os.environ.setdefault("DB_PASS", "test_password_12345678")
    os.environ.setdefault("RMQ_HOST", "localhost")
    os.environ.setdefault("RMQ_PORT", "5672")
    os.environ.setdefault("RMQ_USER", "test_mq_user")
    os.environ.setdefault("RMQ_PASS", "test_mq_password_12345678")

    # Clear rate limit env vars that might leak from integration tests
    for key in list(os.environ.keys()):
        if key.startswith("RATE_LIMIT_"):
            try:
                del os.environ[key]
            except KeyError:
                pass


@pytest.fixture(scope="session", autouse=True)
def preserve_pytest_logging_handlers():
    """Save pytest's logging handlers before any configure_logging() calls."""
    original_handlers = logging.root.handlers.copy()
    original_level = logging.root.level

    yield

    # Restore after all tests complete
    logging.root.handlers = original_handlers
    logging.root.setLevel(original_level)


# Remove the problematic caplog autouse fixture


@pytest.fixture(autouse=not RUNNING_INTEGRATION_TESTS)
def mock_rabbit(monkeypatch):
    """Mock RabbitMQ publish_message."""
    from unittest.mock import AsyncMock

    mock = AsyncMock()
    try:
        monkeypatch.setattr("dependencies.get_publisher", lambda: mock)
    except Exception:
        pass


@pytest.fixture(autouse=not RUNNING_INTEGRATION_TESTS)
def mock_database():
    """Mock database session and domain dependencies via FastAPI dependency_overrides."""
    from unittest.mock import AsyncMock, MagicMock

    mock_session = AsyncMock()
    mock_execute = MagicMock()
    mock_session.execute = mock_execute
    mock_execute.return_value.scalars.return_value.all.return_value = []
    mock_session.get.return_value = None
    mock_session.add.return_value = None
    mock_session.commit.return_value = None
    mock_session.flush.return_value = None

    async def mock_get_async_session():
        yield mock_session

    # Create mock services
    mock_task_service = MagicMock()
    mock_task_service.get_task = AsyncMock(return_value=None)
    mock_task_service.get_all_tasks = AsyncMock(
        return_value=MagicMock(items=[], total=0, limit=50, offset=0)
    )
    mock_task_service.create_task = AsyncMock(return_value=None)

    mock_assignment_service = MagicMock()
    mock_assignment_service.get_assignment = AsyncMock(return_value=None)
    mock_assignment_service.get_all_assignments = AsyncMock(
        return_value=MagicMock(items=[], total=0, limit=50, offset=0)
    )
    mock_assignment_service.create_assignment = AsyncMock(return_value=None)
    mock_assignment_service.update_assignment = AsyncMock(return_value=None)
    mock_assignment_service.delete_assignment = AsyncMock(return_value=True)

    mock_file_service = MagicMock()
    mock_file_service.get_files = AsyncMock(
        return_value=MagicMock(items=[], total=0, limit=50, offset=0)
    )
    mock_file_service.get_all_file_info = AsyncMock(
        return_value=MagicMock(items=[], total=0, limit=50, offset=0)
    )
    mock_file_service.get_file_similarities = AsyncMock(
        return_value=MagicMock(items=[], total=0, limit=0, offset=0)
    )
    mock_file_service.get_file_content = AsyncMock(return_value=None)

    mock_result_service = MagicMock()
    mock_result_service.get_all_results = AsyncMock(
        return_value=MagicMock(items=[], total=0, limit=50, offset=0)
    )
    mock_result_service.get_task_results = AsyncMock(return_value=None)
    mock_result_service.get_file_pair = AsyncMock(return_value=None)
    mock_result_service.get_task_histogram = AsyncMock(
        return_value={"histogram": [], "total": 0, "bins": 200}
    )
    mock_result_service.analyze_file_pair = AsyncMock(return_value=None)

    # Create mock repositories
    mock_task_repo = MagicMock()
    mock_task_repo.get_task = AsyncMock(return_value=None)

    mock_assignment_repo = MagicMock()
    mock_assignment_repo.get_assignment = AsyncMock(return_value=None)

    mock_file_repo = MagicMock()
    mock_file_repo.get_file = AsyncMock(return_value=None)

    mock_result_repo = MagicMock()

    async def mock_get_task_service():
        return mock_task_service

    async def mock_get_assignment_service():
        return mock_assignment_service

    async def mock_get_file_service():
        return mock_file_service

    async def mock_get_result_service():
        return mock_result_service

    async def mock_get_task_repo():
        return mock_task_repo

    async def mock_get_assignment_repo():
        return mock_assignment_repo

    async def mock_get_file_repo():
        return mock_file_repo

    async def mock_get_result_repo():
        return mock_result_repo

    # Only import app and setup FastAPI dependency overrides if needed
    try:
        from src.app import app

        from assignments.dependencies import get_assignment_repository, get_assignment_service
        from auth.dependencies import get_current_user
        from auth.models import User
        from database import get_async_session
        from dependencies import get_s3_storage
        from files.dependencies import get_file_repository, get_file_service
        from results.dependencies import get_result_repository, get_result_service
        from tasks.dependencies import get_task_repository, get_task_service

        mock_storage = MagicMock()
        mock_user = User(id="test-user-id", email="test@example.com", is_global_admin=True)

        app.dependency_overrides[get_async_session] = mock_get_async_session
        app.dependency_overrides[get_s3_storage] = lambda: mock_storage
        app.dependency_overrides[get_task_repository] = mock_get_task_repo
        app.dependency_overrides[get_assignment_repository] = mock_get_assignment_repo
        app.dependency_overrides[get_file_repository] = mock_get_file_repo
        app.dependency_overrides[get_result_repository] = mock_get_result_repo
        app.dependency_overrides[get_task_service] = mock_get_task_service
        app.dependency_overrides[get_assignment_service] = mock_get_assignment_service
        app.dependency_overrides[get_file_service] = mock_get_file_service
        app.dependency_overrides[get_result_service] = mock_get_result_service
        app.dependency_overrides[get_current_user] = lambda: mock_user

        yield

        # Clean up overrides after test
        app.dependency_overrides.clear()
    except ImportError:
        # Skip FastAPI dependency setup for pure worker unit tests that don't need it
        yield


@pytest.fixture
def sample_assignment_payload():
    """Returns a minimal valid assignment payload."""
    return {"name": "Test Assignment", "description": "Test description"}


@pytest.fixture
def sample_task_payload():
    """Returns a minimal valid task payload."""
    return {"language": "python"}


@pytest.fixture
def sample_subject_payload():
    """Returns a minimal valid subject payload."""
    return {"name": "Test Subject", "description": "Test subject description"}
