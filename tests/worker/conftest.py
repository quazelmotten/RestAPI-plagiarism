"""
Pytest configuration and shared fixtures for worker tests.
"""

import pytest
import tempfile
import os
import sys
from unittest.mock import MagicMock, patch
import redis

# Add worker and src to path
worker_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'worker')
sys.path.insert(0, worker_dir)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from config import settings


@pytest.fixture(scope="session")
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture(scope="function")
def mock_redis():
    """Mock Redis client that behaves like real one but in-memory."""
    with patch('redis.Redis') as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        # Set up common methods
        mock_instance.ping.return_value = True
        mock_instance.exists.return_value = False
        mock_instance.smembers.return_value = set()
        mock_instance.hgetall.return_value = {}
        mock_instance.sinter.return_value = []
        mock_instance.scard.return_value = 0
        mock_instance.sadd = MagicMock()
        mock_instance.hset = MagicMock()
        mock_instance.expire = MagicMock()
        mock_instance.delete = MagicMock()
        mock_instance.incr = MagicMock()
        mock_instance.set.return_value = True
        mock_instance.flushdb = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture(scope="function")
def mock_db_session():
    """Mock SQLAlchemy session."""
    from unittest.mock import MagicMock, AsyncMock
    mock_session = MagicMock()
    mock_execute = MagicMock()
    mock_session.execute = mock_execute
    mock_execute.return_value.scalars.return_value.all.return_value = []
    mock_session.commit = MagicMock()
    mock_session.rollback = MagicMock()
    mock_session.close = MagicMock()
    yield mock_session


@pytest.fixture(scope="function")
def mock_rabbitmq():
    """Mock RabbitMQ channel."""
    from unittest.mock import MagicMock
    mock_channel = MagicMock()
    mock_channel.basic_ack = MagicMock()
    yield mock_channel


@pytest.fixture(scope="function")
def test_config():
    """Override settings for tests."""
    with patch.object(settings, 'worker_concurrency', 2), \
         patch.object(settings, 'redis_ttl', 3600), \
         patch.object(settings, 'inverted_index_min_overlap_threshold', 0.15):
        yield settings


@pytest.fixture(scope="function")
def redis_test_instance():
    """Create a real Redis connection to local test Redis (if running)."""
    # Use a separate test DB
    test_redis = redis.Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=15,  # Test DB
        decode_responses=True
    )
    try:
        test_redis.ping()
        test_redis.flushdb()
        yield test_redis
        test_redis.flushdb()
        test_redis.close()
    except redis.ConnectionError:
        pytest.skip("Redis not available for integration tests")


# Markers for test categorization
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: marks tests as integration (requires Redis/DB)"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance benchmarks"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow-running"
    )
