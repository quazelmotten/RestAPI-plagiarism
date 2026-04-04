"""
Inverted index for fast candidate file lookup.

Maps fingerprint hashes to files, enabling quick similarity candidate discovery.
"""

import logging
from typing import Any

import redis
from shared.interfaces import CandidateIndex

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lua script: server-side candidate finding + Jaccard computation.
# Uses SSCAN instead of SMEMBERS for memory-efficient iteration over large sets.
# Instead of N+M round trips per file (N=hashes, M=candidates), this runs
# entirely inside Redis in a single EVAL call.
#
# KEYS: (none)   ARGV: 1=lang, 2=query_count, 3=min_overlap, 4..n=query_hashes
# Returns: flat array [file_hash, similarity, file_hash, similarity, ...]
# ---------------------------------------------------------------------------
_FIND_CANDIDATES_LUA = r"""
local lang = ARGV[1]
local qcount = tonumber(ARGV[2])
local min_overlap = tonumber(ARGV[3])
local scan_count = tonumber(ARGV[4])

local cands = {}
local cands_count = {}
for i = 5, #ARGV do
  local key = "inv:hash:" .. lang .. ":" .. ARGV[i]
  local cursor = "0"
  repeat
    local result = redis.call("SSCAN", key, cursor, "COUNT", scan_count)
    cursor = result[1]
    local files = result[2]
    for _, fh in ipairs(files) do
      cands[fh] = (cands[fh] or 0) + 1
      cands_count[fh] = (cands_count[fh] or 0) + 1
    end
  until cursor == "0"
end

local result = {}
for fh, overlap in pairs(cands) do
  if overlap >= min_overlap then
    local fkey = "inv:file:" .. lang .. ":" .. fh
    local bcount = redis.call("SCARD", fkey)
    local union = qcount + bcount - overlap
    if union > 0 then
      local sim = overlap / union
      if sim > 1.0 then sim = 1.0 end
      table.insert(result, fh)
      table.insert(result, tostring(sim))
    end
  end
end
return result
"""


class RedisInvertedIndex(CandidateIndex):
    """
    Redis-based inverted index for candidate file search.

    Stores:
        inv:hash:{lang}:{hash} -> Set[file_hashes]
        inv:file:{lang}:{file_hash} -> Set[hash_values]
    """

    HASH_TO_FILES_PREFIX = "inv:hash"
    FILE_TO_HASHES_PREFIX = "inv:file"

    # Pre-filter: skip candidate search if fingerprint counts differ by more than this ratio.
    # A file with 5000 fingerprints can't be meaningfully similar to one with 200.
    MAX_FP_COUNT_RATIO = 4.0

    def __init__(self, redis_client: redis.Redis, min_overlap_threshold: float = 0.15):
        self.redis = redis_client
        self.min_overlap_threshold = min_overlap_threshold
        self._lua_script = self.redis.register_script(_FIND_CANDIDATES_LUA)
        # Cache of file_hash -> fingerprint count for pre-filtering
        self._fp_count_cache: dict[str, int] = {}

    def add_file_fingerprints(
        self, file_hash: str, fingerprints: list[dict[str, Any]], language: str = "python"
    ) -> None:
        """Add file fingerprints to the inverted index."""
        if not fingerprints:
            return

        pipe = self.redis.pipeline()
        hash_values = set()

        for fp in fingerprints:
            hash_val = str(fp["hash"])
            hash_values.add(hash_val)

            inv_key = f"{self.HASH_TO_FILES_PREFIX}:{language}:{hash_val}"
            pipe.sadd(inv_key, file_hash)

        file_key = f"{self.FILE_TO_HASHES_PREFIX}:{language}:{file_hash}"
        if hash_values:
            pipe.sadd(file_key, *hash_values)

        pipe.execute()

        # Update local fingerprint count cache for pre-filtering
        self._fp_count_cache[file_hash] = len(hash_values)

        logger.debug(f"Indexed {len(hash_values)} fingerprints for {file_hash[:16]}...")

    def find_candidates(self, hash_values: list[str], language: str = "python") -> dict[str, float]:
        """
        Find candidate files with similarity scores using Jaccard overlap.

        Uses a Redis Lua script with SSCAN for memory-efficient iteration.
        Pre-filters candidates by fingerprint count ratio to skip impossible matches.

        Args:
            hash_values: List of fingerprint hash strings to search for
            language: Programming language

        Returns:
            Dict mapping file_hash -> similarity_score (0.0 to 1.0)
        """
        if not hash_values:
            return {}

        query_count = len(hash_values)
        min_overlap = max(1, int(query_count * self.min_overlap_threshold))
        scan_count = 100  # SSCAN batch size

        # Lua script: single round trip with SSCAN
        flat = self._lua_script(
            keys=[],
            args=[language, query_count, min_overlap, scan_count] + [str(h) for h in hash_values],
        )

        # Parse flat array: [file_hash, sim, file_hash, sim, ...]
        result: dict[str, float] = {}
        for i in range(0, len(flat), 2):
            file_hash = flat[i]
            sim = float(flat[i + 1])

            # Pre-filter: skip if fingerprint counts are wildly different
            if self._should_filter_by_count(file_hash, query_count):
                continue

            result[file_hash] = sim
        return result

    def _should_filter_by_count(self, candidate_hash: str, query_fp_count: int) -> bool:
        """
        Pre-filter candidate by fingerprint count ratio.

        If the candidate has vastly more or fewer fingerprints than the query,
        they can't be meaningfully similar. This avoids expensive Redis lookups
        for impossible matches.

        Args:
            candidate_hash: File hash of the candidate
            query_fp_count: Number of fingerprints in the query file

        Returns:
            True if the candidate should be filtered out
        """
        candidate_count = self._fp_count_cache.get(candidate_hash)
        if candidate_count is None:
            # Fetch and cache from Redis if not in local cache
            file_key = f"{self.FILE_TO_HASHES_PREFIX}:python:{candidate_hash}"
            candidate_count = self.redis.scard(file_key)
            self._fp_count_cache[candidate_hash] = candidate_count

        if candidate_count == 0:
            return True

        ratio = max(query_fp_count, candidate_count) / min(query_fp_count, candidate_count)
        return ratio > self.MAX_FP_COUNT_RATIO

    def get_file_fingerprints(self, file_hash: str, language: str = "python") -> list[str] | None:
        """Get stored fingerprint hash strings for a file."""
        file_key = f"{self.FILE_TO_HASHES_PREFIX}:{language}:{file_hash}"
        hashes = self.redis.smembers(file_key)
        count = len(hashes) if hashes else 0
        if count > 0:
            self._fp_count_cache[file_hash] = count
        return list(hashes) if hashes else None

    def get_file_fingerprints_batch(
        self, file_hashes: list[str], language: str = "python"
    ) -> dict[str, list[str] | None]:
        """
        Batch-fetch fingerprint sets for multiple files in a single pipeline.

        Returns dict mapping file_hash -> List[str] (or None if not indexed).
        """
        if not file_hashes:
            return {}

        pipe = self.redis.pipeline()
        ordered = []
        for fh in file_hashes:
            file_key = f"{self.FILE_TO_HASHES_PREFIX}:{language}:{fh}"
            pipe.smembers(file_key)
            ordered.append(fh)

        raw_results = pipe.execute()

        result: dict[str, list[str] | None] = {}
        for fh, hashes in zip(ordered, raw_results, strict=False):
            count = len(hashes) if hashes else 0
            if count > 0:
                self._fp_count_cache[fh] = count
            result[fh] = list(hashes) if hashes else None
        return result

    def remove_file(self, file_hash: str, language: str = "python") -> None:
        """Remove a file from the inverted index."""
        file_key = f"{self.FILE_TO_HASHES_PREFIX}:{language}:{file_hash}"
        hash_values = self.redis.smembers(file_key)

        if not hash_values:
            return

        pipe = self.redis.pipeline()

        for hash_val in hash_values:
            inv_key = f"{self.HASH_TO_FILES_PREFIX}:{language}:{hash_val}"
            pipe.srem(inv_key, file_hash)

        pipe.delete(file_key)
        pipe.execute()

        self._fp_count_cache.pop(file_hash, None)

        logger.debug(f"Removed {file_hash[:16]}... from inverted index ({len(hash_values)} hashes)")
