"""
Integration test: cross-language contamination.

Files in different programming languages should never be matched
as plagiarism candidates — the inverted index is language-scoped.
"""

import hashlib

import pytest

from worker.infrastructure.inverted_index import RedisInvertedIndex
from worker.infrastructure.redis_cache import RedisFingerprintCache
from worker.services.fingerprint_service import FingerprintService

pytestmark = pytest.mark.integration


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


class TestCrossLanguageContamination:
    """Candidates from one language must never leak into another."""

    def test_python_and_cpp_do_not_cross_contaminate(
        self, simple_redis, temp_plagiarism_dir,
    ):
        """Python fingerprints should not match C++ fingerprints."""
        cache = RedisFingerprintCache(simple_redis, ttl=3600)
        fpsvc = FingerprintService(cache)
        index = RedisInvertedIndex(simple_redis, min_overlap_threshold=0.0)

        py_content = "def hello():\n    print('hello')\n"
        cpp_content = '#include <iostream>\nint main() { std::cout << "hello"; }\n'

        py_path = temp_plagiarism_dir / "hello.py"
        cpp_path = temp_plagiarism_dir / "hello.cpp"
        py_path.write_text(py_content)
        cpp_path.write_text(cpp_content)

        py_hash = _content_hash(py_content)
        cpp_hash = _content_hash(cpp_content)

        py_info = {"file_hash": py_hash, "file_path": str(py_path)}
        cpp_info = {"file_hash": cpp_hash, "file_path": str(cpp_path)}

        py_result = fpsvc.ensure_fingerprinted(py_info, "python")
        cpp_result = fpsvc.ensure_fingerprinted(cpp_info, "cpp")

        py_fps = py_result["fingerprints"]
        cpp_fps = cpp_result["fingerprints"]

        index.add_file_fingerprints(py_hash, py_fps, "python")
        index.add_file_fingerprints(cpp_hash, cpp_fps, "cpp")

        py_fp_hashes = [str(fp["hash"]) for fp in py_fps]
        cpp_fp_hashes = [str(fp["hash"]) for fp in cpp_fps]

        py_cands = index.find_candidates(py_fp_hashes, "python")
        cpp_cands = index.find_candidates(cpp_fp_hashes, "cpp")

        assert cpp_hash not in py_cands, (
            "C++ file must not appear in Python candidates"
        )
        assert py_hash not in cpp_cands, (
            "Python file must not appear in C++ candidates"
        )

        # Each file should find itself (self-similarity)
        assert py_hash in py_cands, "Python file must find itself"
        assert cpp_hash in cpp_cands, "C++ file must find itself"

    def test_same_language_files_are_candidates(
        self, simple_redis, temp_plagiarism_dir,
    ):
        """Two Python files with similar code should be candidates for each other."""
        cache = RedisFingerprintCache(simple_redis, ttl=3600)
        fpsvc = FingerprintService(cache)
        index = RedisInvertedIndex(simple_redis, min_overlap_threshold=0.0)

        content_a = "def add(a, b):\n    return a + b\n"
        content_b = "def add(x, y):\n    return x + y\n"

        path_a = temp_plagiarism_dir / "a.py"
        path_b = temp_plagiarism_dir / "b.py"
        path_a.write_text(content_a)
        path_b.write_text(content_b)

        hash_a = _content_hash(content_a)
        hash_b = _content_hash(content_b)

        info_a = {"file_hash": hash_a, "file_path": str(path_a)}
        info_b = {"file_hash": hash_b, "file_path": str(path_b)}

        result_a = fpsvc.ensure_fingerprinted(info_a, "python")
        result_b = fpsvc.ensure_fingerprinted(info_b, "python")

        fps_a = result_a["fingerprints"]
        fps_b = result_b["fingerprints"]

        index.add_file_fingerprints(hash_a, fps_a, "python")
        index.add_file_fingerprints(hash_b, fps_b, "python")

        fp_hashes_a = [str(fp["hash"]) for fp in fps_a]

        cands_a = index.find_candidates(fp_hashes_a, "python")

        assert hash_b in cands_a, (
            "Similar Python file must be a candidate"
        )
        assert hash_a in cands_a, "File must find itself"
        assert 0.0 < cands_a[hash_b] <= 1.0, (
            "Similarity must be positive and bounded"
        )

    def test_pure_cpp_fingerprints_scope_isolation(
        self, simple_redis, temp_plagiarism_dir,
    ):
        """C++ query must not return Python-indexed files at all."""
        cache = RedisFingerprintCache(simple_redis, ttl=3600)
        fpsvc = FingerprintService(cache)
        index = RedisInvertedIndex(simple_redis, min_overlap_threshold=0.0)

        py_content = "x = 1\n"
        cpp_content = "int x = 1;\n"

        py_path = temp_plagiarism_dir / "x.py"
        cpp_path = temp_plagiarism_dir / "x.cpp"
        py_path.write_text(py_content)
        cpp_path.write_text(cpp_content)

        py_hash = _content_hash(py_content)
        cpp_hash = _content_hash(cpp_content)

        py_result = fpsvc.ensure_fingerprinted(
            {"file_hash": py_hash, "file_path": str(py_path)}, "python",
        )
        fpsvc.ensure_fingerprinted(
            {"file_hash": cpp_hash, "file_path": str(cpp_path)}, "cpp",
        )

        index.add_file_fingerprints(py_hash, py_result["fingerprints"], "python")

        py_fp_hashes = [str(fp["hash"]) for fp in py_result["fingerprints"]]
        cpp_cands = index.find_candidates(py_fp_hashes, "cpp")

        assert py_hash not in cpp_cands, (
            "Python file must not appear as candidate in C++ scope"
        )
