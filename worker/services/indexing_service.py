"""
Indexing service - manages inverted index population.

Responsible for:
- Adding file fingerprints to the inverted index
- Ensuring files are indexed (fingerprinting + index updates)
"""

import logging
from typing import Dict, List, Any, Optional

from shared.interfaces import CandidateIndex, FingerprintCache
from worker.services.fingerprint_service import FingerprintService

logger = logging.getLogger(__name__)


class IndexingService:
    """Manages inverted index updates."""

    def __init__(self, index: CandidateIndex, cache: FingerprintCache, fingerprint_service: FingerprintService):
        """
        Initialize indexing service.

        Args:
            index: Inverted index implementation
            cache: Fingerprint cache (for reading)
            fingerprint_service: Service for generating and caching fingerprints
        """
        self.index = index
        self.cache = cache
        self.fingerprint_service = fingerprint_service

    def index_file(
        self,
        file_info: Dict[str, Any],
        language: str
    ) -> None:
        """
        Index a file's fingerprints in the inverted index.

        Args:
            file_info: Dict with 'file_hash', 'file_path' or 'path'
            language: Programming language
        """
        file_hash = file_info.get('file_hash') or file_info.get('hash')
        file_path = file_info.get('file_path') or file_info.get('path')

        if not file_hash or not file_path:
            logger.warning(f"Skipping file with missing hash/path")
            return

        try:
            # Generate or get from cache via fingerprint service
            fps = self.fingerprint_service.ensure_fingerprinted(file_info, language)
            # Add to inverted index
            self.index.add_file_fingerprints(file_hash, fps, language)
            logger.debug(f"Indexed {len(fps)} fingerprints for {file_hash[:16]}...")
        except Exception as e:
            logger.error(f"Failed to index file {file_hash[:16]}...: {e}")

    def ensure_files_indexed(
        self,
        files: List[Dict[str, Any]],
        language: str,
        existing_files: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Ensure all files are indexed. Returns fingerprint map.

        Args:
            files: List of file info dicts
            language: Programming language
            existing_files: Already indexed files from previous tasks

        Returns:
            Dict mapping file_hash -> fingerprints (list of dicts with 'hash', 'start', 'end')
        """
        logger.info(f"Indexing {len(files)} new files...")
        fingerprint_map = {}

        # Process each file, generating fingerprints if needed
        for idx, file_info in enumerate(files, 1):
            file_hash = file_info.get('file_hash') or file_info.get('hash')
            if not file_hash:
                logger.warning(f"Skipping file {idx}: missing hash")
                continue

            try:
                # Use fingerprint service to ensure fingerprints are available
                fps = self.fingerprint_service.ensure_fingerprinted(file_info, language)
                # Add to inverted index
                self.index.add_file_fingerprints(file_hash, fps, language)
                fingerprint_map[file_hash] = fps
                logger.debug(f"Indexed {file_hash[:16]}... ({idx}/{len(files)})")
            except Exception as e:
                logger.error(f"Failed to index file {file_hash[:16]}...: {e}")

        logger.info(f"Indexing complete: {len(fingerprint_map)} files indexed")
        return fingerprint_map
