"""
Shared type hints and protocols for infrastructure abstractions.

These protocols define the interfaces that infrastructure components
must implement. This allows swapping implementations and clean testing.
"""

from typing import Protocol, runtime_checkable, List, Dict, Any, Tuple, Optional
from pathlib import Path


# ============================================================
# Fingerprint Cache Interface
# ============================================================

@runtime_checkable
class FingerprintCache(Protocol):
    """Caches fingerprints and AST hashes for files."""

    def cache_fingerprints(
        self,
        file_hash: str,
        fingerprints: List[Dict[str, Any]],
        ast_hashes: List[int]
    ) -> bool: ...

    def get_fingerprints(self, file_hash: str) -> Optional[List[Dict[str, Any]]]: ...

    def get_ast_hashes(self, file_hash: str) -> Optional[List[int]]: ...

    def has_fingerprints(self, file_hash: str) -> bool: ...

    def batch_get(
        self,
        file_hashes: List[str]
    ) -> Dict[str, Dict[str, Any]]: ...

    def batch_cache(
        self,
        items: List[Tuple[str, List[Dict[str, Any]], List[int]]]
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
        fingerprints: List[Dict[str, Any]],
        language: str = "python"
    ) -> None: ...

    def find_candidates(
        self,
        hash_values: List[str],
        language: str = "python"
    ) -> Dict[str, float]: ...

    def get_file_fingerprints(
        self,
        file_hash: str,
        language: str = "python"
    ) -> Optional[List[str]]: ...

    def remove_file(self, file_hash: str, language: str = "python") -> None: ...


# ============================================================
# Task Repository Interface
# ============================================================

@runtime_checkable
class TaskRepository(Protocol):
    """Repository for task and file persistence."""

    def get_all_files(self, exclude_task_id: Optional[str] = None) -> List[Dict[str, Any]]: ...

    def update_task(
        self,
        task_id: str,
        status: str,
        similarity: Optional[float] = None,
        matches: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        total_pairs: Optional[int] = None,
        processed_pairs: Optional[int] = None
    ) -> None: ...

    def bulk_insert_results(
        self,
        results: List[Dict[str, Any]]
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
