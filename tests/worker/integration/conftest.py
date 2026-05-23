"""
Async DB fixtures for worker integration tests under tests/worker/integration/.
Mirrors tests/integration/conftest.py so integration tests can access
real PostgreSQL fixtures without depending on parent conftest discovery.
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

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_src_path = os.path.join(_project_root, "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

os.environ.setdefault("STORAGE_LOCAL_PATH", "/tmp/test_s3_storage")

# Save the real get_session BEFORE tests/worker/conftest patches it with a mock.
import worker.database as _wdb  # noqa: E402 – save reference pre-patch
_real_get_session = _wdb.get_session   # unpatched; PostgresRepository will use this

from tests.integration.conftest import (  # noqa: E402 – after env/path setup
    TEST_DB_URL,
    setup_db_schema,
)


class SimpleRedis:
    """In-memory Redis stand-in supporting pipeline patterns used by IndexingService."""

    def __init__(self):
        self.hashes = {}
        self.sets = {}
        self.counters = {}
        self.strings = {}
        self._pipeline_results = None

    def _record(self, value):
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
            return self._record(len(mapping))
        if name not in self.hashes:
            self.hashes[name] = {}
        if field is not None:
            self.hashes[name][field] = value
            return self._record(1)
        return self._record(0)

    def hget(self, name, field):
        return self._record(self.hashes.get(name, {}).get(field))

    def hgetall(self, name):
        return self._record(self.hashes.get(name, {}).copy())

    def sadd(self, name, *members):
        if name not in self.sets:
            self.sets[name] = set()
        before = len(self.sets[name])
        self.sets[name].update(members)
        return self._record(len(self.sets[name]) - before)

    def smembers(self, name):
        return self._record(self.sets.get(name, set()).copy())

    def srem(self, name, *members):
        if name not in self.sets:
            return self._record(0)
        before = len(self.sets[name])
        for m in members:
            self.sets[name].discard(m)
        return self._record(before - len(self.sets[name]))

    def scard(self, name):
        return self._record(len(self.sets.get(name, set())))

    def incr(self, name, amount=1):
        self.counters[name] = self.counters.get(name, 0) + amount
        return self._record(self.counters[name])

    def decr(self, name, amount=1):
        self.counters[name] = self.counters.get(name, 0) - amount
        return self._record(self.counters[name])

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
        return self._record(
            name in self.hashes
            or name in self.sets
            or name in self.counters
            or name in self.strings
        )

    def scan_iter(self, match=None):
        keys = set(self.hashes.keys()) | set(self.sets.keys()) | set(self.counters.keys()) | set(self.strings.keys())
        if match:
            if match.endswith("*"):
                prefix = match[:-1]
                keys = [k for k in keys if k.startswith(prefix)]
            else:
                keys = [k for k in keys if k == match]
        return self._record(keys)

    def pipeline(self):
        self._pipeline_results = []
        return self

    @property
    def command_stack(self):
        return self._pipeline_results if self._pipeline_results is not None else []

    def execute(self):
        if self._pipeline_results is not None:
            results = self._pipeline_results
            self._pipeline_results = None
            return results
        return None

    def expire(self, name, ttl, **kwargs):
        return self._record(True)

    def set(self, name, value=None, **kwargs):
        self.strings[name] = value
        return self._record(True)

    def get(self, name):
        return self._record(self.strings.get(name))

    def register_script(self, script):
        class _MockLuaScript:
            def __init__(self, redis):
                self._redis = redis

            def call(self, keys, args):
                lang = args[0]
                qcount = int(args[1])
                query_hashes = [str(a) for a in args[4:]]
                cands = {}
                for qh in query_hashes:
                    inv_key = f"inv:hash:{lang}:{qh}"
                    for fh in self._redis.sets.get(inv_key, set()):
                        cands[fh] = cands.get(fh, 0) + 1
                result = []
                for fh, overlap in cands.items():
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

        return _MockLuaScript(self)


@pytest.fixture(autouse=True)
def mock_redis_client(monkeypatch):
    """Patch redis.Redis globally so that cache/index use SimpleRedis."""
    import redis as redis_module

    mock_factory = MagicMock()

    def _create(*args, **kwargs):
        return SimpleRedis()

    mock_factory.side_effect = _create
    mock_factory.return_value = None
    monkeypatch.setattr(redis_module, "Redis", mock_factory)


@pytest_asyncio.fixture
async def db_session(session_engine):
    """Dedicated AsyncSession for each test; tables truncated at fixture start."""
    # Truncate all tables for a clean start on every test
    async with session_engine.begin() as conn:
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
    SessionLocal = sessionmaker(session_engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session


@pytest.fixture(scope="session")
def session_engine():
    """Dedicated async engine reused across all tests in the session."""
    eng = create_async_engine(
        TEST_DB_URL,
        pool_size=1,
        max_overflow=0,
        echo=False,
    )
    yield eng
    import asyncio
    try:
        asyncio.get_event_loop().run_until_complete(eng.dispose())
    except Exception:
        pass


@pytest_asyncio.fixture
async def worker_db_session(session_engine):
    """Provide worker.database's real synchronous get_session as an async context manager.

    Worker-level tests (PostgresRepository, ResultService, …) call
    ``worker.database.get_session()`` which is sync psycopg2.  This fixture makes
    it available as an *async* session usable from pytest-asyncio tests.
    The original ``get_session`` is / may be replaced by the autouse mock in
    ``tests/worker/conftest.py``, so we fall back to a thin async shim if needed.
    """
    import contextlib

    try:
        from worker.database import get_session as _raw_gs
        # _raw_gs is a sync context-manager returning a real psycopg2 session
        @contextlib.asynccontextmanager
        async def _async_session_ctx():
            with _raw_gs() as _sync_sess:
                yield _sync_sess
    except Exception:  # pragma: no cover – defensive
        # Extreme fallback: create a minimal session directly
        @contextlib.asynccontextmanager
        async def _async_session_ctx():
            SessionLocal = sessionmaker(session_engine, class_=AsyncSession, expire_on_commit=False)
            async with SessionLocal() as _s:
                yield _s

    async with _async_session_ctx() as _sess:
        yield _sess


@pytest.fixture
def simple_redis():
    """Provide a fresh in-memory Redis mock."""
    return SimpleRedis()


@pytest.fixture
def temp_plagiarism_dir(tmp_path):
    """Temporary directory used to store test plagiarism source files."""
    return tmp_path
