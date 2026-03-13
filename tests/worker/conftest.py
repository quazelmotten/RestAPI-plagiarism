"""
Pytest configuration and shared fixtures for worker tests.
"""

import contextlib
import pytest
import tempfile
import os
import sys
from unittest.mock import MagicMock, patch
import json

# Setup paths for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
worker_dir = os.path.join(project_root, 'worker')
src_dir = os.path.join(project_root, 'src')
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if worker_dir not in sys.path:
    sys.path.insert(1, worker_dir)
if src_dir not in sys.path:
    sys.path.insert(2, src_dir)

from config import settings  # noqa: F401


class SimpleRedis:
    """A simple in-memory Redis mock supporting common operations with pipeline simulation."""

    def __init__(self):
        self.hashes = {}    # key -> dict(field->value)
        self.sets = {}      # key -> set(members)
        self.counters = {}  # key -> int
        self.strings = {}
        self._pipeline_results = None  # list to collect results during pipeline

    def _record(self, value):
        """If in pipeline mode, record the result for later execute."""
        if self._pipeline_results is not None:
            self._pipeline_results.append(value)
        return value

    def hset(self, name, field=None, value=None, **kwargs):
        if name not in self.hashes:
            self.hashes[name] = {}
        if isinstance(field, dict):
            mapping = field
            for f, v in mapping.items():
                self.hashes[name][f] = v
            result = len(mapping)
        else:
            self.hashes[name][field] = value
            result = 1
        return self._record(result)

    def hget(self, name, field):
        result = self.hashes.get(name, {}).get(field)
        return self._record(result)

    def hgetall(self, name):
        result = self.hashes.get(name, {}).copy()
        return self._record(result)

    def sadd(self, name, *members):
        if name not in self.sets:
            self.sets[name] = set()
        before = len(self.sets[name])
        self.sets[name].update(members)
        result = len(self.sets[name]) - before
        return self._record(result)

    def smembers(self, name):
        result = self.sets.get(name, set()).copy()
        return self._record(result)

    def srem(self, name, *members):
        if name not in self.sets:
            return self._record(0)
        before = len(self.sets[name])
        for m in members:
            self.sets[name].discard(m)
        result = before - len(self.sets[name])
        return self._record(result)

    def incr(self, name, amount=1):
        self.counters[name] = self.counters.get(name, 0) + amount
        result = self.counters[name]
        return self._record(result)

    def decr(self, name, amount=1):
        self.counters[name] = self.counters.get(name, 0) - amount
        result = self.counters[name]
        return self._record(result)

    def delete(self, *names):
        deleted = 0
        for name in names:
            if name in self.hashes or name in self.sets or name in self.counters or name in self.strings:
                deleted += 1
            self.hashes.pop(name, None)
            self.sets.pop(name, None)
            self.counters.pop(name, None)
            self.strings.pop(name, None)
        return self._record(deleted)

    def flushdb(self):
        self.hashes.clear()
        self.sets.clear()
        self.counters.clear()
        self.strings.clear()

    def exists(self, name):
        result = name in self.hashes or name in self.sets or name in self.counters or name in self.strings
        return self._record(result)

    def scan_iter(self, match=None):
        keys = set(self.hashes.keys()) | set(self.sets.keys()) | set(self.counters.keys()) | set(self.strings.keys())
        if match:
            if match.endswith('*'):
                prefix = match[:-1]
                keys = [k for k in keys if k.startswith(prefix)]
            else:
                keys = [k for k in keys if k == match]
        # Return as list for iteration; the real method returns generator, but list is fine.
        return self._record(keys)

    def pipeline(self):
        # Start pipeline collection; return self to allow chaining.
        self._pipeline_results = []
        return self

    def execute(self):
        if self._pipeline_results is not None:
            results = self._pipeline_results
            self._pipeline_results = None
            return results
        else:
            return None

    def expire(self, name, ttl, **kwargs):
        # Ignore expiration in mock; return True as success.
        return self._record(True)

    def set(self, name, value=None, **kwargs):
        self.strings[name] = value
        return self._record(True)


@pytest.fixture(scope="session")
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture(scope="function")
def mock_redis():
    """Mock Redis client that behaves like real one but in-memory (MagicMock)."""
    with patch('redis.Redis') as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
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
        # scan_iter for clear_all
        mock_instance.scan_iter.return_value = []
        # pipeline support
        mock_pipeline = MagicMock()
        mock_pipeline.__enter__ = MagicMock(return_value=mock_pipeline)
        mock_pipeline.__exit__ = MagicMock(return_value=False)
        mock_instance.pipeline.return_value = mock_pipeline
        yield mock_instance


@pytest.fixture(scope="function")
def redis_test_instance():
    """Provide a simple in-memory Redis mock for integration tests."""
    redis_mock = SimpleRedis()
    # Reset RedisClient singleton to ensure fresh instance
    try:
        from redis_client import RedisClient
        RedisClient._instance = None
    except ImportError:
        pass
    # Patch redis.Redis to return our mock
    with patch('redis.Redis', return_value=redis_mock):
        # Ensure inverted_index uses this mock if already imported
        try:
            from inverted_index import inverted_index
            inverted_index.redis = redis_mock
        except ImportError:
            pass
        yield redis_mock


@pytest.fixture(scope="function")
def mock_db_session():
    """Mock SQLAlchemy session."""
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


@pytest.fixture(autouse=True)
def mock_get_session(monkeypatch, mock_db_session):
    """Patch get_session in crud module to return a mock sync context manager."""
    import crud
    @contextlib.contextmanager
    def fake_get_session():
        yield mock_db_session
    monkeypatch.setattr(crud, 'get_session', fake_get_session)


# Markers for test categorization
def pytest_configure(config):
    config.addinivalue_line("markers", "integration: marks tests as integration (requires Redis/DB)")
    config.addinivalue_line("markers", "performance: marks tests as performance benchmarks")
    config.addinivalue_line("markers", "slow: marks tests as slow-running")
