"""
In-memory implementations of infrastructure interfaces for benchmarking.

These implementations provide the same interface as the Redis/PostgreSQL
backends but operate entirely in memory, allowing benchmarking of the
core algorithms without any infrastructure dependencies.
"""

from collections import defaultdict
from typing import Any

from shared.interfaces import CandidateIndex, FingerprintCache, TaskRepository


class InMemoryFingerprintCache(FingerprintCache):
    """In-memory fingerprint cache (no Redis)."""

    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}

    def cache_fingerprints(
        self, file_hash: str, fingerprints: list[dict], ast_hashes: list[int]
    ) -> bool:
        self._store[file_hash] = {"fingerprints": fingerprints, "ast_hashes": ast_hashes}
        return True

    def get_fingerprints(self, file_hash: str) -> list[dict] | None:
        data = self._store.get(file_hash)
        return data["fingerprints"] if data else None

    def get_ast_hashes(self, file_hash: str) -> list[int] | None:
        data = self._store.get(file_hash)
        return data["ast_hashes"] if data else None

    def has_fingerprints(self, file_hash: str) -> bool:
        return file_hash in self._store

    def batch_get(self, file_hashes: list[str]) -> dict[str, dict[str, Any]]:
        result = {}
        for fh in file_hashes:
            data = self._store.get(fh)
            if data:
                result[fh] = {
                    "fingerprints": data["fingerprints"],
                    "ast_hashes": data["ast_hashes"],
                    "fingerprint_count": len(data["fingerprints"]) if data["fingerprints"] else 0,
                }
            else:
                result[fh] = {"fingerprints": None, "ast_hashes": None, "fingerprint_count": 0}
        return result

    def batch_cache(self, items: list[tuple[str, list[dict], list[int]]]) -> None:
        for fh, fps, ast in items:
            self._store[fh] = {"fingerprints": fps, "ast_hashes": ast}


class InMemoryCandidateIndex(CandidateIndex):
    """In-memory inverted index (no Redis)."""

    def __init__(self, min_overlap_threshold: float = 0.15):
        self.min_overlap_threshold = min_overlap_threshold
        # hash_value -> set of file_hashes
        self._hash_to_files: dict[str, set] = defaultdict(set)
        # file_hash -> set of hash_values
        self._file_to_hashes: dict[str, set] = defaultdict(set)

    def add_file_fingerprints(
        self, file_hash: str, fingerprints: list[dict], language: str = "python"
    ) -> None:
        if not fingerprints:
            return
        for fp in fingerprints:
            h = str(fp["hash"])
            self._hash_to_files[h].add(file_hash)
            self._file_to_hashes[file_hash].add(h)

    def find_candidates(self, hash_values: list[str], language: str = "python") -> dict[str, float]:
        if not hash_values:
            return {}

        query_hashes = {str(h) for h in hash_values}
        candidate_to_hashes: dict[str, set] = defaultdict(set)

        for h in query_hashes:
            for fh in self._hash_to_files.get(h, set()):
                candidate_to_hashes[fh].add(h)

        query_count = len(query_hashes)
        min_overlap = max(1, int(query_count * self.min_overlap_threshold))

        candidates = {
            fh for fh, shared in candidate_to_hashes.items() if len(shared) >= min_overlap
        }
        if not candidates:
            return {}

        result = {}
        for fh in candidates:
            candidate_count = len(self._file_to_hashes.get(fh, set()))
            if candidate_count == 0:
                continue
            overlap_count = len(candidate_to_hashes[fh])
            union = query_count + candidate_count - overlap_count
            if union > 0:
                result[fh] = min(1.0, overlap_count / union)

        return result

    def get_file_fingerprints(self, file_hash: str, language: str = "python") -> list[str] | None:
        hashes = self._file_to_hashes.get(file_hash)
        return list(hashes) if hashes else None

    def remove_file(self, file_hash: str, language: str = "python") -> None:
        hashes = self._file_to_hashes.pop(file_hash, set())
        for h in hashes:
            files = self._hash_to_files.get(h, set())
            files.discard(file_hash)
            if not files:
                self._hash_to_files.pop(h, None)


class InMemoryTaskRepository(TaskRepository):
    """In-memory task repository (no PostgreSQL)."""

    def __init__(self):
        self._tasks: dict[str, dict] = {}
        self._results: list[dict] = []

    def get_all_files(self, exclude_task_id: str | None = None) -> list[dict]:
        return []

    def update_task(
        self,
        task_id: str,
        status: str,
        similarity: float | None = None,
        matches: dict[str, Any] | None = None,
        error: str | None = None,
        total_pairs: int | None = None,
        processed_pairs: int | None = None,
    ) -> None:
        if task_id not in self._tasks:
            self._tasks[task_id] = {}
        self._tasks[task_id]["status"] = status
        if similarity is not None:
            self._tasks[task_id]["similarity"] = similarity
        if matches is not None:
            self._tasks[task_id]["matches"] = matches
        if error is not None:
            self._tasks[task_id]["error"] = error
        if total_pairs is not None:
            self._tasks[task_id]["total_pairs"] = total_pairs
        if processed_pairs is not None:
            self._tasks[task_id]["processed_pairs"] = processed_pairs

    def bulk_insert_results(self, results: list[dict]) -> None:
        self._results.extend(results)

    def get_max_similarity(self, task_id: str) -> float:
        task_results = [r for r in self._results if r.get("task_id") == task_id]
        if not task_results:
            return 0.0
        return max(r.get("ast_similarity", 0.0) for r in task_results)

    @property
    def result_count(self) -> int:
        return len(self._results)
