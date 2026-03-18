"""
Service for full AST-based plagiarism analysis.
Performs detailed comparison with match detection between file pairs.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Dict, List, Optional

from worker.config import settings
from worker.redis_cache import cache as global_cache

log = logging.getLogger(__name__)

# Module-level reference for test patching compatibility
cache = global_cache


class AnalysisService:
    """Handles full plagiarism analysis with detailed match detection."""

    def __init__(self, analysis_executor: Optional[ThreadPoolExecutor] = None):
        self.analysis_executor = analysis_executor or ThreadPoolExecutor(
            max_workers=getattr(settings, 'worker_concurrency', 4)
        )
        self.cache = cache

    @property
    def _cache(self):
        return globals()['cache']

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
        Perform full plagiarism analysis between two files.
        Uses cached fingerprints when available for efficiency.
        
        Args:
            file1_path: Path to first file
            file2_path: Path to second file
            language: Programming language
            file1_hash: SHA256 hash of file1
            file2_hash: SHA256 hash of file2
            timeout: Timeout in seconds (ignored if no executor)
            threshold: AST similarity threshold (default 0.15)
            
        Returns:
            Dict with 'similarity_ratio' (float) and 'matches' (list of match dicts)
        """
        # If no executor, run directly
        if self.analysis_executor is None:
            return self._run_analysis_cached(
                file1_path, file2_path, language,
                file1_hash, file2_hash, threshold
            )

        # Otherwise submit with timeout
        future = self.analysis_executor.submit(
            self._run_analysis_cached,
            file1_path, file2_path, language,
            file1_hash, file2_hash, threshold
        )
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f"Analysis timed out after {timeout}s for {file1_path} vs {file2_path}")
        except Exception as e:
            log.error(f"Error in analyze_pair: {e}")
            raise

    def analyze_pair_full(
        self,
        file1_path: str,
        file2_path: str,
        language: str,
        timeout: int = 600
    ) -> Dict:
        """
        Perform full analysis without relying on cached fingerprints.
        Used as fallback when cached analysis fails.
        
        Args:
            file1_path: Path to first file
            file2_path: Path to second file
            language: Programming language
            timeout: Timeout in seconds (ignored if no executor)
            
        Returns:
            Dict with 'similarity_ratio' and 'matches'
        """
        # If no executor, run directly
        if self.analysis_executor is None:
            return self._run_analysis_full(file1_path, file2_path, language)

        # Otherwise submit with timeout
        future = self.analysis_executor.submit(
            self._run_analysis_full,
            file1_path, file2_path, language
        )
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f"Full analysis timed out after {timeout}s for {file1_path} vs {file2_path}")
        except Exception as e:
            log.error(f"Error in analyze_pair_full: {e}")
            raise

    def generate_fingerprints(
        self,
        file_path: str,
        language: str,
        timeout: int = 600
    ) -> Dict:
        """
        Extract fingerprints and AST hashes from a file.
        
        Args:
            file_path: Path to the file
            language: Programming language
            timeout: Timeout in seconds (ignored if no executor)
            
        Returns:
            Dict with fingerprints, ast_hashes, tokens, and counts
        """
        # If no executor, run directly
        if self.analysis_executor is None:
            return self._run_generate_fingerprints(file_path, language)

        # Otherwise submit with timeout
        future = self.analysis_executor.submit(
            self._run_generate_fingerprints,
            file_path, language
        )
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f"Fingerprint generation timed out after {timeout}s for {file_path}")
        except Exception as e:
            log.error(f"Error in generate_fingerprints: {e}")
            raise

    def _run_analysis_cached(
        self,
        file1_path: str,
        file2_path: str,
        language: str,
        file1_hash: str,
        file2_hash: str,
        threshold: float = 0.15
    ) -> Dict:
        """Internal: run cached analysis."""
        from cli.analyzer import analyze_plagiarism_cached

        ast_sim, matches, metrics = analyze_plagiarism_cached(
            file1_path, file2_path, file1_hash, file2_hash,
            cache=self._cache,
            language=language,
            ast_threshold=threshold
        )

        matches_data = []
        if ast_sim >= threshold and matches:
            matches_data = self._transform_matches(matches)

        return {
            "similarity_ratio": ast_sim,
            "matches": matches_data,
        }

    def _run_analysis_full(
        self,
        file1_path: str,
        file2_path: str,
        language: str
    ) -> Dict:
        """Internal: run full analysis without cache."""
        from cli.analyzer import Analyzer

        analyzer = Analyzer()
        result = analyzer.Start(file1_path, file2_path, language)
        
        return {
            "similarity_ratio": result.get("similarity_ratio", 0.0),
            "matches": result.get("matches", [])
        }

    def _run_generate_fingerprints(
        self,
        file_path: str,
        language: str
    ) -> Dict:
        """Internal: generate fingerprints."""
        from cli.analyzer import (
            tokenize_with_tree_sitter,
            winnow_fingerprints,
            compute_fingerprints,
            extract_ast_hashes,
        )

        tokens = tokenize_with_tree_sitter(file_path, language)
        fingerprints = winnow_fingerprints(compute_fingerprints(tokens))
        ast_hashes = extract_ast_hashes(file_path, language, min_depth=3)

        return {
            "file": file_path,
            "language": language,
            "fingerprints": [
                {"hash": fp["hash"], "start": list(fp["start"]), "end": list(fp["end"])}
                for fp in fingerprints
            ],
            "ast_hashes": ast_hashes,
            "tokens": [
                {"type": t[0], "start": list(t[1]), "end": list(t[2])}
                for t in tokens
            ],
            "token_count": len(tokens),
            "fingerprint_count": len(fingerprints),
        }

    def _transform_matches(self, matches: List[Dict]) -> List[Dict]:
        """Transform matches from analyzer format to legacy DB format."""
        return [
            {
                "file_a_start_line": m["file1"]["start_line"],
                "file_a_end_line": m["file1"]["end_line"],
                "file_b_start_line": m["file2"]["start_line"],
                "file_b_end_line": m["file2"]["end_line"]
            }
            for m in matches
        ]

    # Backward compatibility aliases (deprecated - use safe_* methods)
    def run_cached_analysis(
        self,
        file1_path: str,
        file2_path: str,
        file1_hash: str,
        file2_hash: str,
        language: str,
        threshold: float = 0.15
    ) -> Dict:
        """[Deprecated] Use analyze_pair. Run cached analysis directly (no timeout)."""
        return self._run_analysis_cached(
            file1_path, file2_path, language,
            file1_hash, file2_hash, threshold
        )

    def run_cli_analyze(
        self,
        file1_path: str,
        file2_path: str,
        language: str
    ) -> Dict:
        """[Deprecated] Use analyze_pair_full. Run full analysis directly (no timeout)."""
        return self._run_analysis_full(file1_path, file2_path, language)

    def run_cli_fingerprint(
        self,
        file_path: str,
        language: str
    ) -> Dict:
        """[Deprecated] Use generate_fingerprints. Generate fingerprints directly (no timeout)."""
        return self._run_generate_fingerprints(file_path, language)

    def safe_run_cached_analyze(
        self,
        file1_path: str,
        file2_path: str,
        file1_hash: str,
        file2_hash: str,
        language: str,
        timeout: int = 600
    ) -> Dict:
        """[Deprecated] Use analyze_pair. Run cached analysis with timeout."""
        return self.analyze_pair(
            file1_path, file2_path, language,
            file1_hash, file2_hash, timeout
        )

    def safe_run_cli_analyze(
        self,
        file1_path: str,
        file2_path: str,
        language: str,
        timeout: int = 600
    ) -> Dict:
        """[Deprecated] Use analyze_pair_full. Run full analysis with timeout."""
        return self.analyze_pair_full(file1_path, file2_path, language, timeout)

    def safe_run_cli_fingerprint(
        self,
        file_path: str,
        language: str,
        timeout: int = 600
    ) -> Dict:
        """[Deprecated] Use generate_fingerprints. Generate fingerprints with timeout."""
        return self.generate_fingerprints(file_path, language, timeout)

    def transform_matches_to_legacy_format(self, matches: List[Dict]) -> List[Dict]:
        """[Deprecated] Use _transform_matches."""
        return self._transform_matches(matches)

    def shutdown(self):
        """Shutdown the analysis executor."""
        if self.analysis_executor:
            self.analysis_executor.shutdown(wait=True)
