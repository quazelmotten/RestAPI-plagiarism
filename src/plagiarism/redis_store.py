"""
Redis-based fingerprint storage and similarity calculation.
Stores all fingerprints in Redis for fast similarity comparisons.
"""

import json
from typing import List, Dict, Tuple, Optional, Any
from redis_client import get_redis
from config import settings


class RedisFingerprintStore:
    """
    Store and retrieve code fingerprints from Redis.
    Uses Redis data structures optimized for fast similarity calculations.
    """
    
    # Key prefixes
    TOKEN_FP_PREFIX = "fp:token"
    AST_FP_PREFIX = "fp:ast"
    FILE_META_PREFIX = "file:meta"
    SIMILARITY_CACHE_PREFIX = "sim:cache"
    
    def __init__(self):
        self.redis = get_redis()
        self.ttl = settings.redis_fingerprint_ttl
    
    # ============================================================================
    # Token Fingerprint Storage
    # ============================================================================
    
    def store_token_fingerprints(self, file_hash: str, fingerprints: List[Dict[str, Any]]) -> None:
        """
        Store winnowed token fingerprints in Redis.
        Uses Redis Set for fast intersection operations.
        
        Args:
            file_hash: SHA256 hash of the file content
            fingerprints: List of fingerprint dicts with 'hash', 'start', 'end' keys
        """
        key = f"{self.TOKEN_FP_PREFIX}:{file_hash}"
        
        # Store as hash -> position mapping in Redis Hash
        # This allows us to retrieve positions for matching hashes later
        pipe = self.redis.pipeline()
        
        # Store count for quick access
        pipe.hset(f"{key}:count", "total", len(fingerprints))
        
        # Store each fingerprint's hash and position data
        for fp in fingerprints:
            hash_val = str(fp['hash'])
            position_data = json.dumps({
                'start': fp['start'],
                'end': fp['end']
            })
            # Use HSET to store hash -> position mapping
            pipe.hset(f"{key}:positions", hash_val, position_data)
            # Add to Set for intersection operations
            pipe.sadd(f"{key}:hashes", hash_val)
        
        # Set expiration
        pipe.expire(key, self.ttl)
        pipe.expire(f"{key}:count", self.ttl)
        pipe.expire(f"{key}:positions", self.ttl)
        pipe.expire(f"{key}:hashes", self.ttl)
        
        pipe.execute()
    
    def get_token_fingerprints(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve token fingerprints from Redis.
        
        Returns:
            Dict with 'hashes' (set of hash strings), 'positions' (dict), 'count' (int)
            or None if not found
        """
        key = f"{self.TOKEN_FP_PREFIX}:{file_hash}"
        
        # Check if exists
        if not self.redis.exists(f"{key}:hashes"):
            return None
        
        # Get all data
        hashes = self.redis.smembers(f"{key}:hashes")
        positions_raw = self.redis.hgetall(f"{key}:positions")
        count = self.redis.hget(f"{key}:count", "total")
        
        # Parse positions
        positions = {k: json.loads(v) for k, v in positions_raw.items()}
        
        return {
            'hashes': hashes,
            'positions': positions,
            'count': int(count) if count else 0
        }
    
    def has_token_fingerprints(self, file_hash: str) -> bool:
        """Check if token fingerprints exist for a file."""
        key = f"{self.TOKEN_FP_PREFIX}:{file_hash}"
        return self.redis.exists(f"{key}:hashes") > 0
    
    # ============================================================================
    # AST Fingerprint Storage
    # ============================================================================
    
    def store_ast_fingerprints(self, file_hash: str, ast_hashes: List[int]) -> None:
        """
        Store AST subtree hashes in Redis.
        Uses Redis Set for Jaccard similarity calculation.
        
        Args:
            file_hash: SHA256 hash of the file content
            ast_hashes: List of AST subtree hash values
        """
        key = f"{self.AST_FP_PREFIX}:{file_hash}"
        
        if not ast_hashes:
            return
        
        pipe = self.redis.pipeline()
        
        # Store count
        pipe.set(f"{key}:count", len(ast_hashes), ex=self.ttl)
        
        # Add all hashes to Set
        hash_strings = [str(h) for h in ast_hashes]
        pipe.sadd(f"{key}:hashes", *hash_strings)
        pipe.expire(f"{key}:hashes", self.ttl)
        
        pipe.execute()
    
    def get_ast_fingerprints(self, file_hash: str) -> Optional[set]:
        """
        Retrieve AST fingerprint hashes from Redis.
        
        Returns:
            Set of hash strings or None if not found
        """
        key = f"{self.AST_FP_PREFIX}:{file_hash}"
        
        if not self.redis.exists(f"{key}:hashes"):
            return None
        
        return self.redis.smembers(f"{key}:hashes")
    
    def has_ast_fingerprints(self, file_hash: str) -> bool:
        """Check if AST fingerprints exist for a file."""
        key = f"{self.AST_FP_PREFIX}:{file_hash}"
        return self.redis.exists(f"{key}:hashes") > 0
    
    # ============================================================================
    # Similarity Calculation (Using Redis Operations)
    # ============================================================================
    
    def find_matching_regions(self, file_a_hash: str, file_b_hash: str) -> List[Dict]:
        """
        Find matching regions between two files using token fingerprints.
        Uses Redis Set operations for fast intersection.
        
        Returns:
            List of matching regions with line/column positions
        """
        key_a = f"{self.TOKEN_FP_PREFIX}:{file_a_hash}"
        key_b = f"{self.TOKEN_FP_PREFIX}:{file_b_hash}"
        
        # Check if both exist
        if not self.redis.exists(f"{key_a}:hashes") or not self.redis.exists(f"{key_b}:hashes"):
            return []
        
        # Calculate intersection using Redis SINTER
        common_hashes = self.redis.sinter(f"{key_a}:hashes", f"{key_b}:hashes")
        
        if not common_hashes:
            return []
        
        # Get positions for matching hashes
        positions_a = self.redis.hmget(f"{key_a}:positions", list(common_hashes))
        positions_b = self.redis.hmget(f"{key_b}:positions", list(common_hashes))
        
        # Build matching regions
        matches = []
        for hash_val, pos_a_json, pos_b_json in zip(common_hashes, positions_a, positions_b):
            if pos_a_json and pos_b_json:
                pos_a = json.loads(pos_a_json)
                pos_b = json.loads(pos_b_json)
                matches.append({
                    'file1': {
                        'start_line': pos_a['start'][0],
                        'start_col': pos_a['start'][1],
                        'end_line': pos_a['end'][0],
                        'end_col': pos_a['end'][1],
                    },
                    'file2': {
                        'start_line': pos_b['start'][0],
                        'start_col': pos_b['start'][1],
                        'end_line': pos_b['end'][0],
                        'end_col': pos_b['end'][1],
                    }
                })
        
        return matches
    
    def calculate_ast_similarity(self, file_a_hash: str, file_b_hash: str) -> float:
        """
        Calculate AST-based similarity using Redis Set operations.
        Uses Jaccard index: |A ∩ B| / |A ∪ B|
        
        Optimization: Uses cached counts instead of SUNION
        |A ∪ B| = |A| + |B| - |A ∩ B|
        
        Returns:
            Similarity score between 0.0 and 1.0
        """
        key_a = f"{self.AST_FP_PREFIX}:{file_a_hash}"
        key_b = f"{self.AST_FP_PREFIX}:{file_b_hash}"
        
        # Check if both exist
        if not self.redis.exists(f"{key_a}:hashes") or not self.redis.exists(f"{key_b}:hashes"):
            return 0.0
        
        # Get cached counts (O(1) operation)
        count_a = int(self.redis.get(f"{key_a}:count") or 0)
        count_b = int(self.redis.get(f"{key_b}:count") or 0)
        
        if count_a == 0 or count_b == 0:
            return 0.0
        
        # Calculate intersection using Redis SINTER
        intersection = self.redis.sinter(f"{key_a}:hashes", f"{key_b}:hashes")
        intersection_size = len(intersection)
        
        # Calculate union size using formula: |A ∪ B| = |A| + |B| - |A ∩ B|
        union_size = count_a + count_b - intersection_size
        
        if union_size == 0:
            return 0.0
        
        return intersection_size / union_size
    
    # ============================================================================
    # File Metadata
    # ============================================================================
    
    def store_file_metadata(self, file_hash: str, metadata: Dict[str, Any]) -> None:
        """Store file metadata in Redis."""
        key = f"{self.FILE_META_PREFIX}:{file_hash}"
        self.redis.hset(key, mapping=metadata)
        self.redis.expire(key, self.ttl)
    
    def get_file_metadata(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve file metadata from Redis."""
        key = f"{self.FILE_META_PREFIX}:{file_hash}"
        data = self.redis.hgetall(key)
        return data if data else None
    
    # ============================================================================
    # Similarity Result Caching
    # ============================================================================
    
    def cache_similarity_result(self, file_a_hash: str, file_b_hash: str, 
                               ast_sim: float, 
                               matches: List[Dict]) -> None:
        """Cache similarity calculation result."""
        # Create consistent cache key (sorted hashes)
        hashes = sorted([file_a_hash, file_b_hash])
        key = f"{self.SIMILARITY_CACHE_PREFIX}:{hashes[0]}:{hashes[1]}"
        
        data = {
            'ast_similarity': ast_sim,
            'matches': json.dumps(matches)
        }
        
        self.redis.hset(key, mapping=data)
        self.redis.expire(key, self.ttl)
    
    def get_cached_similarity(self, file_a_hash: str, file_b_hash: str) -> Optional[Dict]:
        """Retrieve cached similarity result."""
        hashes = sorted([file_a_hash, file_b_hash])
        key = f"{self.SIMILARITY_CACHE_PREFIX}:{hashes[0]}:{hashes[1]}"
        
        data = self.redis.hgetall(key)
        if not data:
            return None
        
        return {
            'ast_similarity': float(data.get('ast_similarity', 0)),
            'matches': json.loads(data.get('matches', '[]'))
        }
    
    # ============================================================================
    # Utility Methods
    # ============================================================================
    
    def delete_file_fingerprints(self, file_hash: str) -> None:
        """Delete all fingerprints for a file."""
        token_key = f"{self.TOKEN_FP_PREFIX}:{file_hash}"
        ast_key = f"{self.AST_FP_PREFIX}:{file_hash}"
        meta_key = f"{self.FILE_META_PREFIX}:{file_hash}"
        
        # Delete token fingerprints
        self.redis.delete(
            f"{token_key}:hashes",
            f"{token_key}:positions",
            f"{token_key}:count"
        )
        
        # Delete AST fingerprints
        self.redis.delete(f"{ast_key}:hashes", f"{ast_key}:count")
        
        # Delete metadata
        self.redis.delete(meta_key)
    
    def clear_all_fingerprints(self) -> None:
        """Clear all fingerprint data from Redis. USE WITH CAUTION."""
        # Find all fingerprint keys
        token_keys = list(self.redis.scan_iter(match=f"{self.TOKEN_FP_PREFIX}:*"))
        ast_keys = list(self.redis.scan_iter(match=f"{self.AST_FP_PREFIX}:*"))
        meta_keys = list(self.redis.scan_iter(match=f"{self.FILE_META_PREFIX}:*"))
        cache_keys = list(self.redis.scan_iter(match=f"{self.SIMILARITY_CACHE_PREFIX}:*"))
        
        all_keys = token_keys + ast_keys + meta_keys + cache_keys
        
        if all_keys:
            self.redis.delete(*all_keys)


# Global store instance
fingerprint_store = RedisFingerprintStore()
