"""
Shared type hints and protocols for infrastructure abstractions.

These protocols define the interfaces that infrastructure components
must implement. This allows swapping implementations and clean testing.
"""

from typing import Any, Protocol, runtime_checkable

# ============================================================
# Fingerprint Cache Interface
# ============================================================

@runtime_checkable
class FingerprintCache(Protocol):
    """Caches fingerprints and AST hashes for files."""

    def cache_fingerprints(
        self,
        file_hash: str,
        fingerprints: list[dict[str, Any]],
        ast_hashes: list[int]
    ) -> bool: ...

    def get_fingerprints(self, file_hash: str) -> list[dict[str, Any]] | None: ...

    def get_ast_hashes(self, file_hash: str) -> list[int] | None: ...

    def has_fingerprints(self, file_hash: str) -> bool: ...

    def batch_get(
        self,
        file_hashes: list[str]
    ) -> dict[str, dict[str, Any]]: ...

    def batch_cache(
        self,
        items: list[tuple[str, list[dict[str, Any]], list[int]]]
    ) -> None: ...


# ============================================================
# Candidate Index Interface
# ============================================================

@runtime_checkable
class CandidateIndex(Protocol):
    """Inverted index for finding candidate similar files."""

    def add_file_fingerprints(
        self,
        file_hash: str,
        fingerprints: list[dict[str, Any]],
        language: str = "python"
    ) -> None: ...

    def find_candidates(
        self,
        hash_values: list[str],
        language: str = "python"
    ) -> dict[str, float]: ...

    def get_file_fingerprints(
        self,
        file_hash: str,
        language: str = "python"
    ) -> list[str] | None: ...

    def get_file_fingerprints_batch(
        self,
        file_hashes: list[str],
        language: str = "python"
    ) -> dict[str, list[str] | None]: ...

    def remove_file(self, file_hash: str, language: str = "python") -> None: ...


# ============================================================
# Task Repository Interface
# ============================================================

@runtime_checkable
class TaskRepository(Protocol):
    """Repository for task and file persistence."""

    def get_all_files(self, exclude_task_id: str | None = None) -> list[dict[str, Any]]: ...

    def update_task(
        self,
        task_id: str,
        status: str,
        similarity: float | None = None,
        matches: dict[str, Any] | None = None,
        error: str | None = None,
        total_pairs: int | None = None,
        processed_pairs: int | None = None
    ) -> None: ...

    def bulk_insert_results(
        self,
        results: list[dict[str, Any]]
    ) -> None: ...

    def get_max_similarity(self, task_id: str) -> float: ...


# ============================================================
# Lock Manager Interface
# ============================================================

@runtime_checkable
class LockManager(Protocol):
    """Distributed locking for concurrent fingerprint computation."""

    def lock(self, key: str, timeout: int = 300) -> bool: ...

    def unlock(self, key: str) -> bool: ...
