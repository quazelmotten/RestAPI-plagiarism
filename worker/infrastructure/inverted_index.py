"""
Inverted index for fast candidate file lookup.

Maps fingerprint hashes to files, enabling quick similarity candidate discovery.
"""

import logging
from typing import Dict, List, Optional, Any

import redis

from shared.interfaces import CandidateIndex

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lua script: server-side candidate finding + Jaccard computation.
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

local cands = {}
for i = 4, #ARGV do
  local key = "inv:hash:" .. lang .. ":" .. ARGV[i]
  local files = redis.call("SMEMBERS", key)
  for _, fh in ipairs(files) do
    cands[fh] = (cands[fh] or 0) + 1
  end
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

    def __init__(self, redis_client: redis.Redis, min_overlap_threshold: float = 0.15):
        self.redis = redis_client
        self.min_overlap_threshold = min_overlap_threshold
        self._lua_script = self.redis.register_script(_FIND_CANDIDATES_LUA)

    def add_file_fingerprints(
        self,
        file_hash: str,
        fingerprints: List[Dict[str, Any]],
        language: str = "python"
    ) -> None:
        """Add file fingerprints to the inverted index."""
        if not fingerprints:
            return

        pipe = self.redis.pipeline()
        hash_values = set()

        for fp in fingerprints:
            hash_val = str(fp['hash'])
            hash_values.add(hash_val)

            inv_key = f"{self.HASH_TO_FILES_PREFIX}:{language}:{hash_val}"
            pipe.sadd(inv_key, file_hash)

        file_key = f"{self.FILE_TO_HASHES_PREFIX}:{language}:{file_hash}"
        if hash_values:
            pipe.sadd(file_key, *hash_values)

        pipe.execute()

        logger.debug(f"Indexed {len(hash_values)} fingerprints for {file_hash[:16]}...")

    def find_candidates(
        self,
        hash_values: List[str],
        language: str = "python"
    ) -> Dict[str, float]:
        """
        Find candidate files with similarity scores using Jaccard overlap.

        Uses a Redis Lua script so all set operations (SMEMBERS, SCARD) and
        the Jaccard computation happen server-side in a single round trip.

        Args:
            hash_values: List of fingerprint hash strings to search for
            language: Programming language

        Returns:
            Dict mapping file_hash -> similarity_score (0.0 to 1.0)
        """
        if not hash_values:
            return {}

        query_hashes = [str(h) for h in hash_values]
        query_count = len(query_hashes)
        min_overlap = max(1, int(query_count * self.min_overlap_threshold))

        # Lua script: single round trip
        flat = self._lua_script(
            keys=[],
            args=[language, query_count, min_overlap] + query_hashes,
        )

        # Parse flat array: [file_hash, sim, file_hash, sim, ...]
        result: Dict[str, float] = {}
        for i in range(0, len(flat), 2):
            result[flat[i]] = float(flat[i + 1])
        return result

    def get_file_fingerprints(
        self,
        file_hash: str,
        language: str = "python"
    ) -> Optional[List[str]]:
        """Get stored fingerprint hash strings for a file."""
        file_key = f"{self.FILE_TO_HASHES_PREFIX}:{language}:{file_hash}"
        hashes = self.redis.smembers(file_key)
        return list(hashes) if hashes else None

    def get_file_fingerprints_batch(
        self,
        file_hashes: List[str],
        language: str = "python"
    ) -> Dict[str, Optional[List[str]]]:
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

        result: Dict[str, Optional[List[str]]] = {}
        for fh, hashes in zip(ordered, raw_results):
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

        logger.debug(f"Removed {file_hash[:16]}... from inverted index ({len(hash_values)} hashes)")
