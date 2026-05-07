"""
Embedding cache layer.

Supports both Redis (fast, ephemeral) and PostgreSQL (persistent) caching.
"""

import logging
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import delete, select

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """
    Cache for pre-computed embeddings.

    Supports:
    - Redis: Fast in-memory cache with TTL
    - PostgreSQL: Persistent storage in file_embeddings table
    - Hybrid: Check Redis first, fallback to PostgreSQL

    All methods are synchronous to avoid asyncio event loop issues.
    """

    def __init__(
        self,
        redis_client=None,
        db_session=None,
        use_redis: bool = True,
        use_db: bool = True,
    ):
        """
        Initialize cache.

        Args:
            redis_client: Redis client (from worker/infrastructure/redis_cache.py)
            db_session: Database session for persistent storage
            use_redis: Whether to use Redis cache
            use_db: Whether to use database storage
        """
        self.redis = redis_client if use_redis else None
        self.db = db_session if use_db else None
        self._redis_prefix = "emb:"

    def get(self, file_hash: str) -> np.ndarray | None:
        """
        Get embedding for a file by its content hash.

        Checks Redis first, then database.

        Args:
            file_hash: SHA256 hash of file content

        Returns:
            Numpy array or None if not cached
        """
        # Try Redis first
        if self.redis:
            try:
                key = f"{self._redis_prefix}{file_hash}"
                data = self.redis.get(key)
                if data:
                    # Data is float16 bytes, convert back to float32
                    import base64
                    decoded = base64.b64decode(data)
                    return np.frombuffer(decoded, dtype=np.float16).astype(np.float32)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")

        # Try database
        if self.db:
            try:
                from shared.models import FileEmbedding
                result = self.db.execute(
                    select(FileEmbedding).where(FileEmbedding.file_hash == file_hash)
                )
                emb_record = result.scalar_one_or_none()
                if emb_record and emb_record.embedding:
                    # Convert bytes back to numpy array
                    return np.frombuffer(emb_record.embedding, dtype=np.float16).astype(np.float32)
            except Exception as e:
                logger.warning(f"DB get failed: {e}")

        return None

    def set(
        self,
        file_hash: str,
        embedding: np.ndarray,
        ttl: int | None = 86400,  # 24 hours default
    ) -> None:
        """
        Cache an embedding.

        Args:
            file_hash: SHA256 hash of file content
            embedding: Numpy array (will be stored as float16 for precision)
            ttl: Redis TTL in seconds (None = no expiry)
        """
        # Store as float16 for good precision with reasonable storage
        # float16: 2 bytes per dimension, ~0.1% error (vs ~50% for int8)
        emb_float16 = embedding.astype(np.float16)
        emb_bytes = emb_float16.tobytes()

        # Store in Redis
        if self.redis:
            try:
                import base64
                key = f"{self._redis_prefix}{file_hash}"
                encoded = base64.b64encode(emb_bytes).decode('ascii')
                self.redis.set(key, encoded, ex=ttl)
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")

        # Store in database
        if self.db:
            try:
                from shared.models import FileEmbedding

                # Check if exists
                result = self.db.execute(
                    select(FileEmbedding).where(FileEmbedding.file_hash == file_hash)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.embedding = emb_bytes
                    existing.updated_at = datetime.now(UTC)
                else:
                    emb_record = FileEmbedding(
                        file_hash=file_hash,
                        embedding=emb_bytes,
                        embedding_dim=len(embedding),
                        model_version="F2LLM-v2-80M",
                    )
                    self.db.add(emb_record)

                self.db.commit()
            except Exception as e:
                logger.warning(f"DB set failed: {e}")
                self.db.rollback()

    def get_batch(self, file_hashes: list[str]) -> dict[str, np.ndarray]:
        """
        Get multiple embeddings at once.

        Args:
            file_hashes: List of file hashes

        Returns:
            Dict mapping file_hash to embedding array
        """
        results = {}

        # Try Redis pipeline for batch get
        if self.redis:
            try:
                import base64
                keys = [f"{self._redis_prefix}{h}" for h in file_hashes]
                # Note: This is a simplified version - actual Redis pipeline would be better
                for key, file_hash in zip(keys, file_hashes, strict=False):
                    data = self.redis.get(key)
                    if data:
                        decoded = base64.b64decode(data)
                        results[file_hash] = np.frombuffer(decoded, dtype=np.float16).astype(np.float32)
            except Exception as e:
                logger.warning(f"Redis batch get failed: {e}")

        # Fill missing from database
        missing = [h for h in file_hashes if h not in results]
        if missing and self.db:
            try:
                from shared.models import FileEmbedding
                result = self.db.execute(
                    select(FileEmbedding).where(FileEmbedding.file_hash.in_(missing))
                )
                for emb_record in result.scalars().all():
                    if emb_record.embedding:
                        results[emb_record.file_hash] = (
                            np.frombuffer(emb_record.embedding, dtype=np.float16)
                            .astype(np.float32)
                        )
            except Exception as e:
                logger.warning(f"DB batch get failed: {e}")

        return results

    def delete(self, file_hash: str) -> None:
        """Delete embedding from cache."""
        if self.redis:
            try:
                key = f"{self._redis_prefix}{file_hash}"
                self.redis.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")

        if self.db:
            try:
                from shared.models import FileEmbedding
                self.db.execute(
                    delete(FileEmbedding).where(FileEmbedding.file_hash == file_hash)
                )
                self.db.commit()
            except Exception as e:
                logger.warning(f"DB delete failed: {e}")
                self.db.rollback()


def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """
    Compute cosine similarity between two embeddings.

    Args:
        emb1, emb2: 1D numpy arrays (assumed normalized)

    Returns:
        Cosine similarity in range [-1, 1]
    """
    return float(np.dot(emb1, emb2))
