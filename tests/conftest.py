import pytest
import sys
import os

# Set up environment variables before importing
os.environ.setdefault('STORAGE_LOCAL_PATH', '/tmp/test_s3_storage')
os.environ.setdefault('DB_HOST', 'localhost')
os.environ.setdefault('DB_PORT', '5432')
os.environ.setdefault('DB_NAME', 'test_db')
os.environ.setdefault('DB_USER', 'test_user')
os.environ.setdefault('DB_PASS', 'test_password_12345678')
os.environ.setdefault('RMQ_HOST', 'localhost')
os.environ.setdefault('RMQ_PORT', '5672')
os.environ.setdefault('RMQ_USER', 'test_mq_user')
os.environ.setdefault('RMQ_PASS', 'test_mq_password_12345678')

# Resolve src path relative to project root (parent of tests/)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(_project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Ensure src/database is loaded as the 'database' module before worker/database shadows it
import importlib
import importlib.util
if 'database' not in sys.modules:
    spec = importlib.util.spec_from_file_location('database', os.path.join(src_path, 'database.py'))
    database_mod = importlib.util.module_from_spec(spec)
    sys.modules['database'] = database_mod
    spec.loader.exec_module(database_mod)

# Pre-load src/models to prevent worker/models.py from shadowing it
if 'models' not in sys.modules:
    spec = importlib.util.spec_from_file_location('models', os.path.join(src_path, 'models', '__init__.py'),
                                                   submodule_search_locations=[os.path.join(src_path, 'models')])
    models_pkg = importlib.util.module_from_spec(spec)
    sys.modules['models'] = models_pkg
    spec.loader.exec_module(models_pkg)


@pytest.fixture(autouse=True)
def mock_s3_storage(monkeypatch):
    """Mock S3 storage to avoid file system issues."""
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.upload_file.return_value = {"path": "s3://bucket/test.py", "hash": "abc123"}
    mock.download_file.return_value = b"print('hello')"
    monkeypatch.setattr("s3_storage.s3_storage", mock)


@pytest.fixture(autouse=True)
def mock_rabbit(monkeypatch):
    """Mock RabbitMQ publish_message."""
    from unittest.mock import AsyncMock
    mock = AsyncMock()
    monkeypatch.setattr("src.rabbit.publish_message", mock)


@pytest.fixture(autouse=True)
def mock_database(monkeypatch):
    """Mock database session."""
    from unittest.mock import AsyncMock, MagicMock
    mock_session = AsyncMock()
    mock_execute = MagicMock()
    mock_session.execute = mock_execute
    mock_execute.return_value.scalars.return_value.all.return_value = []
    monkeypatch.setattr("database.get_session", mock_session)
