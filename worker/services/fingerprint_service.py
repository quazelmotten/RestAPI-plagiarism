"""
Fingerprint service - manages file fingerprinting and caching.

Responsible for:
- Ensuring files are fingerprinted (from cache or generating)
- Caching fingerprints, AST hashes, body signatures, and embeddings
"""

import logging
from typing import Any

from plagiarism_core.fingerprints import (
    compute_and_winnow,
    extract_body_signatures_from_tree,
    parse_file_once,
    tokenize_and_hash_ast,
)
from shared.interfaces import FingerprintCache

from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class FingerprintService:
    """Generates and caches file fingerprints."""

    def __init__(
        self,
        cache: FingerprintCache,
        embedding_service: EmbeddingService | None = None,
    ):
        """
        Initialize fingerprint service.

        Args:
            cache: Fingerprint cache implementation
            embedding_service: Optional embedding service for generating embeddings
        """
        self.cache = cache
        self.embedding_svc = embedding_service

    def ensure_fingerprinted(
        self, file_info: dict[str, Any], language: str
    ) -> dict[str, Any]:
        """
        Ensure file has fingerprints and embeddings cached. Generate if missing.

        Args:
            file_info: Dict with 'file_hash', 'file_path' (or 'path')
            language: Programming language

        Returns:
            Dict with 'fingerprints', 'ast_hashes', 'embedding' (if available)

        Raises:
            Exception if fingerprinting fails
        """
        file_hash = file_info.get("file_hash") or file_info.get("hash")
        file_path = file_info.get("file_path") or file_info.get("path")

        if not file_hash or not file_path:
            raise ValueError("Invalid file info: missing hash or path")

        # Check cache first
        cached = self.cache.batch_get([file_hash])
        file_data = cached.get(file_hash, {})
        fps = file_data.get("fingerprints")
        ast_hashes = file_data.get("ast_hashes")

        result = {"fingerprints": fps, "ast_hashes": ast_hashes, "embedding": None}

        # Generate fingerprints if missing
        if fps is None or ast_hashes is None:
            # Generate from file — single tree walk + single fingerprint pass
            tree, source_bytes = parse_file_once(file_path, language)
            tokens, ast_hashes = tokenize_and_hash_ast(file_path, language, tree=tree)
            fps = compute_and_winnow(tokens)

            # Extract body signatures for functions (for Stage 1 semantic matching)
            body_signatures = extract_body_signatures_from_tree(tree, source_bytes, language)

            # Convert to expected format (preserve kgram_idx for fragment building)
            fps_for_storage = [
                {
                    "hash": fp["hash"],
                    "start": tuple(fp["start"]),
                    "end": tuple(fp["end"]),
                    "kgram_idx": fp.get("kgram_idx", 0),
                }
                for fp in fps
            ]

            # Cache for future use (fingerprints, ast_hashes, and body_signatures)
            self.cache.batch_cache(
                [(file_hash, fps_for_storage, ast_hashes, body_signatures)]
            )

            logger.info(
                f"Generated and cached {len(fps)} fingerprints + "
                f"{len(ast_hashes)} AST hashes for {file_hash[:16]}..."
            )

            result["fingerprints"] = fps_for_storage
            result["ast_hashes"] = ast_hashes

        else:
            logger.debug(f"Fingerprints from cache for {file_hash[:16]}...")

        # Generate embedding if embedding service is available
        if self.embedding_svc is not None:
            try:
                embedding = self.embedding_svc.ensure_embedded(file_info, language)
                result["embedding"] = embedding
            except Exception as e:
                logger.warning(f"Failed to generate embedding for {file_hash[:16]}: {e}")

        return result

    def get_fingerprints(self, file_hash: str) -> list[dict[str, Any]] | None:
        """Get fingerprints from cache if available."""
        cached = self.cache.batch_get([file_hash])
        return cached.get(file_hash, {}).get("fingerprints")

    def get_ast_hashes(self, file_hash: str) -> list[int] | None:
        """Get AST hashes from cache if available."""
        cached = self.cache.batch_get([file_hash])
        return cached.get(file_hash, {}).get("ast_hashes")
