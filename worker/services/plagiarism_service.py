"""
Service for plagiarism analysis operations.
Handles fingerprint generation and similarity analysis.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Dict, List, Optional

from worker.config import settings
from worker.redis_cache import cache

log = logging.getLogger(__name__)


class PlagiarismService:
    """Handles fingerprint generation and plagiarism analysis."""

    def __init__(self, analysis_executor: Optional[ThreadPoolExecutor] = None):
        self.analysis_executor = analysis_executor or ThreadPoolExecutor(
            max_workers=getattr(settings, 'worker_concurrency', 4)
        )
        self.cache = cache

    def run_cli_analyze(self, file1_path: str, file2_path: str, language: str) -> Dict:
        """Run full plagiarism analysis between two files."""
        from cli.analyzer import Analyzer
        analyzer = Analyzer()
        return analyzer.Start(file1_path, file2_path, language)

    def run_cached_analysis(
        self,
        file1_path: str,
        file2_path: str,
        file1_hash: str,
        file2_hash: str,
        language: str,
        ast_threshold: float = 0.15
    ) -> Dict:
        """Run plagiarism analysis using cached fingerprints from Redis."""
        from cli.analyzer import analyze_plagiarism_cached

        ast_sim, matches, metrics = analyze_plagiarism_cached(
            file1_path, file2_path, file1_hash, file2_hash,
            cache=cache,
            language=language,
            ast_threshold=ast_threshold
        )

        if ast_sim >= ast_threshold:
            matches_data = self.transform_matches_to_legacy_format(matches)
        else:
            matches_data = []

        return {
            "similarity_ratio": ast_sim,
            "matches": matches_data,
        }

    def safe_run_cached_analyze(
        self,
        file1_path: str,
        file2_path: str,
        file1_hash: str,
        file2_hash: str,
        language: str,
        timeout: int = 600
    ) -> Dict:
        """Run cached analysis with timeout protection."""
        if self.analysis_executor is None:
            return self.run_cached_analysis(file1_path, file2_path, file1_hash, file2_hash, language)

        future = self.analysis_executor.submit(
            self.run_cached_analysis,
            file1_path, file2_path, file1_hash, file2_hash, language
        )
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f"Cached analysis timed out after {timeout}s for {file1_path} vs {file2_path}")
        except Exception as e:
            log.error(f"Error in safe_run_cached_analyze: {e}")
            raise

    def transform_matches_to_legacy_format(self, matches: List[Dict]) -> List[Dict]:
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

    def run_cli_fingerprint(self, file_path: str, language: str) -> Dict:
        """Extract fingerprints and AST hashes from a file."""
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

    def safe_run_cli_fingerprint(self, file_path: str, language: str, timeout: int = 600) -> Dict:
        """Run fingerprint extraction with timeout protection."""
        if self.analysis_executor is None:
            return self.run_cli_fingerprint(file_path, language)

        future = self.analysis_executor.submit(
            self.run_cli_fingerprint,
            file_path, language
        )
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f"Fingerprint generation timed out after {timeout}s for {file_path}")
        except Exception as e:
            log.error(f"Error in safe_run_cli_fingerprint: {e}")
            raise

    def safe_run_cli_analyze(self, file1_path: str, file2_path: str, language: str, timeout: int = 600) -> Dict:
        """Run full analysis with timeout protection."""
        if self.analysis_executor is None:
            return self.run_cli_analyze(file1_path, file2_path, language)

        future = self.analysis_executor.submit(
            self.run_cli_analyze,
            file1_path, file2_path, language
        )
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f"Analysis timed out after {timeout}s for {file1_path} vs {file2_path}")
        except Exception as e:
            log.error(f"Error in safe_run_cli_analyze: {e}")
            raise

    def shutdown(self):
        """Shutdown the analysis executor."""
        if self.analysis_executor:
            self.analysis_executor.shutdown(wait=True)
