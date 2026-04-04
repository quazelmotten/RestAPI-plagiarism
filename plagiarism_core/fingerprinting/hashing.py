"""Stable hashing utilities."""

from functools import lru_cache

import xxhash


@lru_cache(maxsize=10000)
def stable_hash(s: str) -> int:
    """Deterministic hash for cross-run stability using xxhash."""
    return xxhash.xxh64(s.encode()).intdigest()
