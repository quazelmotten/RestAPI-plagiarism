"""
Analysis client for on-demand plagiarism analysis.

Provides a clean interface for analyzing file pairs without direct coupling
to the worker service implementation.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from plagiarism_core.analyzer import Analyzer as CoreAnalyzer
from shared.interfaces import FingerprintCache

logger = logging.getLogger(__name__)


class AnalysisClient:
    """
    Client for on-demand plagiarism analysis.

    Wraps the core analyzer with cache support and optional timeout.
    """

    def __init__(
        self, cache: FingerprintCache, analysis_executor: ThreadPoolExecutor | None = None
    ):
        """
        Initialize analysis client.

        Args:
            cache: Fingerprint cache implementation
            analysis_executor: Optional thread pool for timeouts (None = sync)
        """
        self.cache = cache
        self.analysis_executor = analysis_executor
        self.analyzer = CoreAnalyzer()

    def analyze_pair(
        self,
        file1_path: str,
        file2_path: str,
        language: str,
        file1_hash: str,
        file2_hash: str,
        timeout: int = 600,
    ) -> dict:
        """
        Analyze a file pair using cached fingerprints when available.

        Args:
            file1_path, file2_path: File paths
            language: Programming language
            file1_hash, file2_hash: Content hashes
            timeout: Timeout in seconds (only used if executor provided)

        Returns:
            Dict with 'similarity_ratio' and 'matches' list
        """

        def do_analyze():
            return self.analyzer.analyze_cached(
                file1_path=file1_path,
                file2_path=file2_path,
                file1_hash=file1_hash,
                file2_hash=file2_hash,
                get_fingerprints=self._get_fingerprints,
                get_ast_hashes=self._get_ast_hashes,
                cache_fingerprints=self._cache_fingerprints,
                language=language,
            )

        if self.analysis_executor is None:
            ast_sim, matches, _ = do_analyze()
        else:
            future = self.analysis_executor.submit(do_analyze)
            try:
                ast_sim, matches, _ = future.result(timeout=timeout)
            except TimeoutError:
                future.cancel()
                raise TimeoutError(f"Analysis timed out after {timeout}s") from None
            except Exception:
                raise

        return {"similarity_ratio": ast_sim, "matches": matches}

    # Cache helper methods
    def _get_fingerprints(self, file_hash: str):
        """Get fingerprints from cache."""
        data = self.cache.batch_get([file_hash])
        return data.get(file_hash, {}).get("fingerprints")

    def _get_ast_hashes(self, file_hash: str):
        """Get AST hashes from cache."""
        data = self.cache.batch_get([file_hash])
        return data.get(file_hash, {}).get("ast_hashes")

    def _cache_fingerprints(self, file_hash: str, fingerprints: list, ast_hashes: list) -> None:
        """Cache fingerprints and AST hashes."""
        self.cache.batch_cache([(file_hash, fingerprints, ast_hashes)])
