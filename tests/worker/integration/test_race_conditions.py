"""
Integration tests for race conditions in worker operations.

Concurrent operations on the inverted index and fingerprint cache
should be thread-safe and produce consistent results.
"""

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from worker.infrastructure.inverted_index import RedisInvertedIndex
from worker.infrastructure.redis_cache import RedisFingerprintCache
from worker.services.candidate_service import CandidateService
from worker.services.fingerprint_service import FingerprintService

pytestmark = pytest.mark.integration


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _fingerprint(fp_hash: int, start=(0, 0), end=(1, 0)) -> dict:
    return {"hash": fp_hash, "start": start, "end": end, "kgram_idx": 0}


@pytest.fixture
def cache(simple_redis):
    return RedisFingerprintCache(simple_redis, ttl=3600)


@pytest.fixture
def index(simple_redis):
    return RedisInvertedIndex(simple_redis, min_overlap_threshold=0.0)


@pytest.fixture
def fpsvc(cache):
    return FingerprintService(cache)


@pytest.fixture
def candsvc(index):
    return CandidateService(index)


class TestConcurrentFingerprinting:
    """Tests for concurrent fingerprint generation and caching."""

    def test_concurrent_duplicate_fingerprint_idempotent(
        self, fpsvc, temp_plagiarism_dir,
    ):
        """Two threads fingerprinting the same file produce identical results."""
        path = temp_plagiarism_dir / "test_concurrent.py"
        content = "def foo():\n    return 42\n"
        path.write_text(content)
        fhash = _content_hash(content)
        file_info = {"file_hash": fhash, "file_path": str(path)}

        # Pre-populate cache so concurrent calls only read (don't regenerate)
        fpsvc.ensure_fingerprinted(file_info, "python")

        def fingerprint():
            return fpsvc.ensure_fingerprinted(file_info, "python")

        n = 3
        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = [pool.submit(fingerprint) for _ in range(n)]
            results = [f.result() for f in futures]

        first = results[0]
        for r in results[1:]:
            assert r["fingerprints"] == first["fingerprints"]
            assert r["ast_hashes"] == first["ast_hashes"]
        assert len(first["fingerprints"]) > 0
        assert len(first["ast_hashes"]) > 0

    def test_concurrent_ensure_fingerprinted_caches_once(
        self, fpsvc, cache, temp_plagiarism_dir,
    ):
        """After N concurrent fingerprint calls, cache has exactly one entry."""
        path = temp_plagiarism_dir / "test_concurrent_cache.py"
        content = "def bar():\n    return 99\n"
        path.write_text(content)
        fhash = _content_hash(content)
        file_info = {"file_hash": fhash, "file_path": str(path)}

        def fingerprint():
            return fpsvc.ensure_fingerprinted(file_info, "python")

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(fingerprint) for _ in range(4)]
            for f in futures:
                f.result()

        cached = cache.batch_get([fhash])
        assert cached[fhash]["fingerprints"] is not None
        assert cached[fhash]["ast_hashes"] is not None


class TestConcurrentIndexOperations:
    """Tests for concurrent inverted index access."""

    def test_concurrent_index_add_is_idempotent(self, index, simple_redis):
        """Adding same file fingerprints to index concurrently is idempotent."""
        fhash = _content_hash("unique_file_content")
        fps = [_fingerprint(1), _fingerprint(2)]

        def add_to_index():
            index.add_file_fingerprints(fhash, fps, "python")

        n = 4
        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = [pool.submit(add_to_index) for _ in range(n)]
            for f in futures:
                f.result()

        fp_hashes = [str(fp["hash"]) for fp in fps]
        cands = index.find_candidates(fp_hashes, "python")
        assert fhash in cands
        assert cands[fhash] == 1.0

    def test_concurrent_find_candidates_thread_safe(self, index, simple_redis):
        """Multiple threads querying candidates simultaneously get correct results."""
        hashes = [_content_hash(f"content_{i}") for i in range(5)]
        fp_hashes = [str(_fingerprint(10 + i)["hash"]) for i in range(3)]

        for h in hashes:
            index.add_file_fingerprints(h, [_fingerprint(10 + i) for i in range(3)], "python")

        def query():
            return index.find_candidates(fp_hashes, "python")

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(query) for _ in range(4)]
            results = [f.result() for f in futures]

        for r in results:
            assert len(r) == len(hashes)
            for h in hashes:
                assert h in r
                assert 0.0 <= r[h] <= 1.0

    def test_concurrent_mixed_add_and_query(self, index, simple_redis):
        """Concurrent adds and queries don't cause errors and produce consistent results."""
        existing_hashes = [_content_hash(f"existing_{i}") for i in range(3)]
        fp_base = 100

        for i, h in enumerate(existing_hashes):
            index.add_file_fingerprints(h, [_fingerprint(fp_base + i)], "python")

        all_fp_hashes = [str(fp_base + i) for i in range(3)]

        def add_file(idx):
            fhash = _content_hash(f"new_{idx}")
            index.add_file_fingerprints(
                fhash, [_fingerprint(fp_base + (idx % 3))], "python",
            )
            return fhash

        def query():
            return index.find_candidates([all_fp_hashes[0]], "python")

        added_hashes = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            add_futures = [pool.submit(add_file, i) for i in range(6)]
            query_futures = [pool.submit(query) for _ in range(3)]
            for f in add_futures:
                added_hashes.append(f.result())
            for f in query_futures:
                r = f.result()
                assert len(r) >= len(existing_hashes)

        fp_hash_0 = all_fp_hashes[0]
        all_expected = set(existing_hashes) | {h for h in added_hashes if h}
        cands = index.find_candidates([fp_hash_0], "python")
        for h in all_expected:
            if h in cands:
                assert 0.0 <= cands[h] <= 1.0


class TestConcurrentCandidatePairs:
    """Tests for concurrent candidate pair generation."""

    def test_concurrent_intra_task_produces_correct_count(
        self, index, fpsvc, candsvc, temp_plagiarism_dir,
    ):
        """Two tasks simultaneously finding intra-task pairs from the same files get C(N,2)."""
        contents = [f"def func{i}():\n    return {i}\n" for i in range(4)]
        paths = []
        hashes = []
        for i, content in enumerate(contents):
            path = temp_plagiarism_dir / f"file_{i}.py"
            path.write_text(content)
            paths.append(str(path))
            hashes.append(_content_hash(content))

        files = [{"file_hash": h, "file_path": p, "id": str(i)}
                 for i, (h, p) in enumerate(zip(hashes, paths))]

        for f in files:
            fpsvc.ensure_fingerprinted(f, "python")
            fp_data = fpsvc.get_fingerprints(f["file_hash"])
            index.add_file_fingerprints(f["file_hash"], fp_data, "python")

        def find():
            return candsvc.find_candidate_pairs(files, language="python", deduplicate=True)

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(find)
            f2 = pool.submit(find)
            pairs1 = f1.result()
            pairs2 = f2.result()

        assert len(pairs1) == 6
        assert len(pairs2) == 6
        for a, b, sim in pairs1:
            assert a["id"] != b["id"]
            assert 0.0 <= sim <= 1.0

    def test_concurrent_cross_task_produces_correct_count(
        self, index, fpsvc, candsvc, temp_plagiarism_dir,
    ):
        """Concurrent cross-task candidate finding produces A*B pairs."""
        a_contents = [f"def alpha{i}():\n    return {i}\n" for i in range(3)]
        b_contents = [f"def beta{j}():\n    return {j}\n" for j in range(2)]

        a_files = []
        for i, content in enumerate(a_contents):
            path = temp_plagiarism_dir / f"alpha_{i}.py"
            path.write_text(content)
            fhash = _content_hash(content)
            a_files.append({"file_hash": fhash, "file_path": str(path), "id": f"a{i}"})

        b_files = []
        for j, content in enumerate(b_contents):
            path = temp_plagiarism_dir / f"beta_{j}.py"
            path.write_text(content)
            fhash = _content_hash(content)
            b_files.append({"file_hash": fhash, "file_path": str(path), "id": f"b{j}"})

        for f in a_files + b_files:
            fpsvc.ensure_fingerprinted(f, "python")
            fp_data = fpsvc.get_fingerprints(f["file_hash"])
            index.add_file_fingerprints(f["file_hash"], fp_data, "python")

        def find():
            return candsvc.find_candidate_pairs(
                a_files, b_files, language="python", deduplicate=False,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(find)
            f2 = pool.submit(find)
            pairs1 = f1.result()
            pairs2 = f2.result()

        assert len(pairs1) == 6
        assert len(pairs2) == 6
