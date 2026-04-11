import os
import sys
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

# Resolve src path relative to project root (parent of tests/)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(_project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Ensure src/database is loaded as the 'database' module before worker/database shadows it
import importlib  # noqa: E402
import importlib.util  # noqa: E402

if "database" not in sys.modules:
    spec = importlib.util.spec_from_file_location("database", os.path.join(src_path, "database.py"))
    database_mod = importlib.util.module_from_spec(spec)
    sys.modules["database"] = database_mod
    spec.loader.exec_module(database_mod)

# Pre-load src/models to prevent worker/models.py from shadowing it
if "models" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "models",
        os.path.join(src_path, "models", "__init__.py"),
        submodule_search_locations=[os.path.join(src_path, "models")],
    )
    models_pkg = importlib.util.module_from_spec(spec)
    sys.modules["models"] = models_pkg
    spec.loader.exec_module(models_pkg)


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

    # Use FastAPI's dependency_overrides
    from app import app
    from assignments.dependencies import get_assignment_repository, get_assignment_service
    from database import get_async_session
    from dependencies import get_s3_storage
    from files.dependencies import get_file_repository, get_file_service
    from results.dependencies import get_result_repository, get_result_service
    from tasks.dependencies import get_task_repository, get_task_service

    mock_storage = MagicMock()

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

    yield

    # Clean up overrides after test
    app.dependency_overrides.clear()


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
