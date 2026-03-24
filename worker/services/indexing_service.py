"""
Indexing service - manages inverted index population.

Responsible for:
- Adding file fingerprints to the inverted index
- Ensuring files are indexed (fingerprinting + index updates)
"""

import logging
import time
from typing import Dict, List, Any, Optional, Callable

from shared.interfaces import CandidateIndex, FingerprintCache
from worker.services.fingerprint_service import FingerprintService

logger = logging.getLogger(__name__)


class IndexingService:
    """Manages inverted index updates."""

    def __init__(self, index: CandidateIndex, cache: FingerprintCache, fingerprint_service: FingerprintService):
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
        existing_files: Optional[List[Dict[str, Any]]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Ensure all files are indexed. Returns fingerprint map.

        Args:
            files: List of file info dicts
            language: Programming language
            existing_files: Already indexed files from previous tasks
            on_progress: Callback(processed, total) called every 25 files
        """
        logger.info(f"Indexing {len(files)} new files...")
        fingerprint_map = {}
        total_fps = 0
        t0 = time.perf_counter()
        log_interval = max(1, min(25, len(files) // 8))  # ~8 progress updates

        # Process each file, generating fingerprints if needed
        for idx, file_info in enumerate(files, 1):
            file_hash = file_info.get('file_hash') or file_info.get('hash')
            if not file_hash:
                logger.warning(f"Skipping file {idx}: missing hash")
                continue

            file_start = time.perf_counter()
            try:
                fps = self.fingerprint_service.ensure_fingerprinted(file_info, language)
                self.index.add_file_fingerprints(file_hash, fps, language)
                fingerprint_map[file_hash] = fps
                file_elapsed = time.perf_counter() - file_start
                total_fps += len(fps)

                if idx % log_interval == 0 or idx == len(files):
                    elapsed = time.perf_counter() - t0
                    speed = idx / elapsed if elapsed > 0 else 0
                    logger.info(f"  Indexed {idx}/{len(files)} files "
                                f"({speed:.1f} files/sec, {file_elapsed*1000:.1f}ms last)")
                    if on_progress:
                        on_progress(idx, len(files))
            except Exception as e:
                logger.error(f"Failed to index file {file_hash[:16]}...: {e}")

        elapsed = time.perf_counter() - t0
        speed = len(fingerprint_map) / elapsed if elapsed > 0 else 0
        logger.info(f"Indexing complete: {len(fingerprint_map)} files, {total_fps} fingerprints "
                    f"in {elapsed:.2f}s ({speed:.1f} files/sec)")
        return fingerprint_map
