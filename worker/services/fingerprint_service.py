"""
Fingerprint service - manages file fingerprinting and caching.

Responsible for:
- Ensuring files are fingerprinted (from cache or generating)
- Caching fingerprints and AST hashes
"""

import logging
from typing import Dict, List, Any, Optional

from plagiarism_core.fingerprints import (
    tokenize_with_tree_sitter,
    compute_fingerprints,
    winnow_fingerprints,
)
from plagiarism_core.ast_hash import extract_ast_hashes
from shared.interfaces import FingerprintCache

logger = logging.getLogger(__name__)


class FingerprintService:
    """Generates and caches file fingerprints."""

    def __init__(self, cache: FingerprintCache):
        """
        Initialize fingerprint service.

        Args:
            cache: Fingerprint cache implementation
        """
        self.cache = cache

    def ensure_fingerprinted(
        self,
        file_info: Dict[str, Any],
        language: str
    ) -> List[Dict[str, Any]]:
        """
        Ensure file has fingerprints cached. Generate if missing.

        Args:
            file_info: Dict with 'file_hash', 'file_path' (or 'path')
            language: Programming language

        Returns:
            List of fingerprint dicts

        Raises:
            Exception if fingerprinting fails
        """
        file_hash = file_info.get('file_hash') or file_info.get('hash')
        file_path = file_info.get('file_path') or file_info.get('path')

        if not file_hash or not file_path:
            raise ValueError(f"Invalid file info: missing hash or path")

        # Check cache first
        cached = self.cache.batch_get([file_hash])
        file_data = cached.get(file_hash, {})
        fps = file_data.get('fingerprints')
        ast_hashes = file_data.get('ast_hashes')

        if fps is not None and ast_hashes is not None:
            logger.debug(f" fingerprints from cache for {file_hash[:16]}...")
            return fps

        # Generate from file
        tokens = tokenize_with_tree_sitter(file_path, language)
        raw_fps = compute_fingerprints(tokens)
        fps = winnow_fingerprints(raw_fps)
        ast_hashes = extract_ast_hashes(file_path, language)

        # Convert to expected format
        fps_for_storage = [
            {'hash': fp['hash'], 'start': tuple(fp['start']), 'end': tuple(fp['end'])}
            for fp in fps
        ]

        # Cache for future use
        self.cache.batch_cache([(file_hash, fps_for_storage, ast_hashes)])

        logger.info(f"Generated and cached {len(fps)} fingerprints + {len(ast_hashes)} AST hashes for {file_hash[:16]}...")

        return fps_for_storage

    def get_fingerprints(
        self,
        file_hash: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get fingerprints from cache if available."""
        cached = self.cache.batch_get([file_hash])
        return cached.get(file_hash, {}).get('fingerprints')

    def get_ast_hashes(self, file_hash: str) -> Optional[List[int]]:
        """Get AST hashes from cache if available."""
        cached = self.cache.batch_get([file_hash])
        return cached.get(file_hash, {}).get('ast_hashes')
