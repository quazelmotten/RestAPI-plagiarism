import pytest
import sys
import os

# Set up environment variables before importing
os.environ.setdefault('STORAGE_LOCAL_PATH', '/tmp/test_s3_storage')

sys.path.insert(0, '/home/bobbybrown/RestAPI-plagiarism/src')


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
