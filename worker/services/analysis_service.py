"""
Analysis service - performs plagiarism analysis using core library.

Thin wrapper around CoreAnalyzer with cache integration and timeout support.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Dict, List, Optional, Callable

from plagiarism_core.analyzer import Analyzer as CoreAnalyzer
from shared.interfaces import FingerprintCache

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    Service for plagiarism analysis using the core library.

    Provides both cached and full analysis with optional timeout.
    """

    def __init__(
        self,
        cache: FingerprintCache,
        analysis_executor: Optional[ThreadPoolExecutor] = None
    ):
        """
        Initialize analysis service.

        Args:
            cache: Fingerprint cache implementation
            analysis_executor: Optional thread pool for timeouts (None = sync)
        """
        self.cache = cache
        self.analysis_executor = analysis_executor
        self.analyzer = CoreAnalyzer(ast_threshold=0.15)

    def analyze_pair(
        self,
        file1_path: str,
        file2_path: str,
        language: str,
        file1_hash: str,
        file2_hash: str,
        timeout: int = 600,
        threshold: float = 0.15
    ) -> Dict:
        """
        Analyze pair using cached fingerprints when available.

        Args:
            file1_path, file2_path: File paths
            language: Programming language
            file1_hash, file2_hash: Content hashes
            timeout: Timeout in seconds (only used if executor provided)
            threshold: AST similarity threshold

        Returns:
            Dict with 'similarity_ratio' and 'matches' list
        """
        # Define the analysis function
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
                ast_threshold=threshold
            )

        # Run with or without executor
        if self.analysis_executor is None:
            ast_sim, matches, _ = do_analyze()
        else:
            future = self.analysis_executor.submit(do_analyze)
            try:
                ast_sim, matches, _ = future.result(timeout=timeout)
            except TimeoutError:
                future.cancel()
                raise TimeoutError(f"Analysis timed out after {timeout}s")
            except Exception:
                raise

        return {'similarity_ratio': ast_sim, 'matches': matches}

    def analyze_pair_full(
        self,
        file1_path: str,
        file2_path: str,
        language: str,
        timeout: int = 600
    ) -> Dict:
        """
        Full analysis without relying on cache (fallback).

        Args:
            file1_path, file2_path: File paths
            language: Programming language
            timeout: Timeout in seconds (only used if executor provided)

        Returns:
            Dict with 'similarity_ratio' and 'matches'
        """
        def do_analyze():
            result = self.analyzer.analyze(
                file1_path, file2_path, language, ast_threshold=0.0
            )
            return {
                'similarity_ratio': result.similarity_ratio,
                'matches': [
                    {
                        'file1': m.file1,
                        'file2': m.file2,
                        'kgram_count': m.kgram_count
                    }
                    for m in result.matches
                ]
            }

        if self.analysis_executor is None:
            return do_analyze()

        future = self.analysis_executor.submit(do_analyze)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f"Full analysis timed out after {timeout}s")
        except Exception:
            raise

    def generate_fingerprints(
        self,
        file_path: str,
        language: str,
        timeout: int = 600
    ) -> Dict:
        """
        Generate fingerprints and AST hashes for a file.

        Args:
            file_path: Path to file
            language: Programming language
            timeout: Timeout in seconds (only used if executor provided)

        Returns:
            Dict with 'fingerprints', 'ast_hashes', etc.
        """
        from plagiarism_core.fingerprints import (
            tokenize_with_tree_sitter,
            compute_fingerprints,
            winnow_fingerprints,
            compute_and_winnow,
            parse_file_once,
            tokenize_and_hash_ast,
        )

        def do_generate():
            tree, _ = parse_file_once(file_path, language)
            tokens, ast_hashes = tokenize_and_hash_ast(file_path, language, tree=tree)
            fps = compute_and_winnow(tokens)

            return {
                'file': file_path,
                'language': language,
                'fingerprints': [
                    {'hash': fp['hash'], 'start': list(fp['start']), 'end': list(fp['end'])}
                    for fp in fps
                ],
                'ast_hashes': ast_hashes,
                'token_count': len(tokens),
                'fingerprint_count': len(fps),
            }

        if self.analysis_executor is None:
            return do_generate()

        future = self.analysis_executor.submit(do_generate)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f"Fingerprint generation timed out after {timeout}s")
        except Exception:
            raise

    # Cache helper methods
    def _get_fingerprints(self, file_hash: str):
        """Get fingerprints from cache."""
        data = self.cache.batch_get([file_hash])
        return data.get(file_hash, {}).get('fingerprints')

    def _get_ast_hashes(self, file_hash: str):
        """Get AST hashes from cache."""
        data = self.cache.batch_get([file_hash])
        return data.get(file_hash, {}).get('ast_hashes')

    def _cache_fingerprints(
        self,
        file_hash: str,
        fingerprints: List[Dict],
        ast_hashes: List[int]
    ) -> None:
        """Cache fingerprints and AST hashes."""
        self.cache.batch_cache([(file_hash, fingerprints, ast_hashes)])

    def shutdown(self):
        """Shutdown the analysis executor if we own it."""
        if self.analysis_executor:
            self.analysis_executor.shutdown(wait=True)
