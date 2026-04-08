"""
Pytest configuration and shared fixtures for worker tests.
"""

import contextlib
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Setup paths for imports (project root is set via pytest.ini pythonpath)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from worker.config import settings  # noqa: E402, F401


class _MockLuaScript:
    """Simulates redis-py Script by running candidate-finding logic in Python."""

    def __init__(self, redis_mock):
        self._redis = redis_mock

    def call(self, keys, args):
        lang = args[0]
        qcount = int(args[1])
        min_overlap = int(args[2])
        query_hashes = [str(a) for a in args[3:]]

        # Count how many query hashes each candidate file shares
        cands = {}
        for qh in query_hashes:
            inv_key = f"inv:hash:{lang}:{qh}"
            for fh in self._redis.sets.get(inv_key, set()):
                cands[fh] = cands.get(fh, 0) + 1

        # Compute Jaccard
        result = []
        for fh, overlap in cands.items():
            if overlap >= min_overlap:
                fkey = f"inv:file:{lang}:{fh}"
                bcount = len(self._redis.sets.get(fkey, set()))
                union = qcount + bcount - overlap
                if union > 0:
                    sim = min(1.0, overlap / union)
                    result.append(fh)
                    result.append(sim)
        return result

    def __call__(self, keys=None, args=None):
        return self.call(keys or [], args or [])


class SimpleRedis:
    """A simple in-memory Redis mock supporting common operations with pipeline simulation."""

    def __init__(self):
        self.hashes = {}  # key -> dict(field->value)
        self.sets = {}  # key -> set(members)
        self.counters = {}  # key -> int
        self.strings = {}
        self._pipeline_results = None  # list to collect results during pipeline

    def _record(self, value):
        """If in pipeline mode, record the result for later execute."""
        if self._pipeline_results is not None:
            self._pipeline_results.append(value)
        return value

    def hset(self, name, field=None, value=None, **kwargs):
        if "mapping" in kwargs:
            mapping = kwargs["mapping"]
            if name not in self.hashes:
                self.hashes[name] = {}
            for f, v in mapping.items():
                self.hashes[name][f] = v
            result = len(mapping)
            return self._record(result)
        if isinstance(field, dict):
            mapping = field
            if name not in self.hashes:
                self.hashes[name] = {}
            for f, v in mapping.items():
                self.hashes[name][f] = v
            result = len(mapping)
            return self._record(result)
        if name not in self.hashes:
            self.hashes[name] = {}
        if field is not None:
            self.hashes[name][field] = value
            result = 1
        else:
            result = 0
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

    def scard(self, name):
        result = len(self.sets.get(name, set()))
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
            if (
                name in self.hashes
                or name in self.sets
                or name in self.counters
                or name in self.strings
            ):
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
        result = (
            name in self.hashes
            or name in self.sets
            or name in self.counters
            or name in self.strings
        )
        return self._record(result)

    def scan_iter(self, match=None):
        keys = (
            set(self.hashes.keys())
            | set(self.sets.keys())
            | set(self.counters.keys())
            | set(self.strings.keys())
        )
        if match:
            if match.endswith("*"):
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

    @property
    def command_stack(self):
        """Return the current pipeline command stack (list of commands). Used by IndexingService to check if pipeline has pending commands."""
        return self._pipeline_results if self._pipeline_results is not None else []

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

    def get(self, name):
        result = self.strings.get(name)
        return self._record(result)

    def register_script(self, script):
        return _MockLuaScript(self)


@pytest.fixture(scope="session")
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture(scope="function")
def mock_redis():
    """Mock Redis client that behaves like real one but in-memory (MagicMock)."""
    with patch("redis.Redis") as mock:
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
    # Patch redis.Redis to return our mock
    with patch("redis.Redis", return_value=redis_mock):
        # Ensure inverted_index uses this mock if already imported
        try:
            from worker.inverted_index import inverted_index

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
    with (
        patch.object(settings, "worker_concurrency", 2),
        patch.object(settings, "redis_ttl", 3600),
        patch.object(settings, "inverted_index_min_overlap_threshold", 0.15),
    ):
        yield settings


@pytest.fixture(autouse=True)
def mock_get_session(monkeypatch, mock_db_session):
    """Patch get_session in database module to return a mock sync context manager."""
    import worker.database as db_module

    @contextlib.contextmanager
    def fake_get_session():
        yield mock_db_session

    monkeypatch.setattr(db_module, "get_session", fake_get_session)


# Markers for test categorization
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: marks tests as integration (requires Redis/DB)"
    )
    config.addinivalue_line("markers", "performance: marks tests as performance benchmarks")
    config.addinivalue_line("markers", "slow: marks tests as slow-running")
