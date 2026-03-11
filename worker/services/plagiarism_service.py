"""
Service for plagiarism analysis operations.
Handles fingerprint generation and similarity analysis.
"""

import logging
from concurrent.futures import ProcessPoolExecutor, TimeoutError
from typing import Dict, List, Optional

from config import settings

log = logging.getLogger(__name__)


class PlagiarismService:
    """Service for plagiarism analysis operations."""
    
    def __init__(self, analysis_executor: Optional[ProcessPoolExecutor] = None):
        """
        Initialize plagiarism service.
        
        Args:
            analysis_executor: ProcessPoolExecutor for running analysis in separate processes.
                              If None, will be created with worker_concurrency.
        """
        self.analysis_executor = analysis_executor or ProcessPoolExecutor(
            max_workers=getattr(settings, 'worker_concurrency', 4)
        )
    
    def run_cli_analyze(self, file1_path: str, file2_path: str, language: str) -> Dict:
        """
        Run plagiarism analysis using the new analyzer (Dolos-style fragment building).
        Returns parsed JSON result with similarity and matches.
        """
        from cli.analyzer import Analyzer
        
        analyzer = Analyzer()
        result = analyzer.Start(file1_path, file2_path, language)
        return result
    
    def transform_matches_to_legacy_format(self, matches: List[Dict]) -> List[Dict]:
        """
        Transform matches from new analyzer format to legacy DB format.
        New format: [{file1: {start_line, start_col, end_line, end_col}, file2: {...}}]
        Legacy format: [{file_a_start_line, file_a_end_line, file_b_start_line, file_b_end_line}]
        """
        legacy_matches = []
        for match in matches:
            legacy_matches.append({
                "file_a_start_line": match["file1"]["start_line"],
                "file_a_end_line": match["file1"]["end_line"],
                "file_b_start_line": match["file2"]["start_line"],
                "file_b_end_line": match["file2"]["end_line"]
            })
        return legacy_matches
    
    def run_cli_fingerprint(self, file_path: str, language: str) -> Dict:
        """
        Run fingerprint extraction.
        Returns parsed JSON result with fingerprints and ast_hashes.
        """
        from cli.analyzer import (
            tokenize_with_tree_sitter,
            winnow_fingerprints,
            compute_fingerprints,
            extract_ast_hashes,
        )
        
        tokens = tokenize_with_tree_sitter(file_path, language)
        fingerprints = winnow_fingerprints(compute_fingerprints(tokens))
        ast_hashes = extract_ast_hashes(file_path, language, min_depth=3)
        
        fingerprints_serializable = []
        for fp in fingerprints:
            fingerprints_serializable.append({
                "hash": fp["hash"],
                "start": list(fp["start"]),
                "end": list(fp["end"]),
            })
        
        tokens_serializable = [
            {"type": t[0], "start": list(t[1]), "end": list(t[2])}
            for t in tokens
        ]
        
        return {
            "file": file_path,
            "language": language,
            "fingerprints": fingerprints_serializable,
            "ast_hashes": ast_hashes,
            "tokens": tokens_serializable,
            "token_count": len(tokens),
            "fingerprint_count": len(fingerprints),
        }
    
    def safe_run_cli_fingerprint(self, file_path: str, language: str, timeout: int = 300) -> Dict:
        """
        Run fingerprint extraction in a separate process with timeout.
        """
        if self.analysis_executor is None:
            raise RuntimeError("Analysis executor not initialized")
        future = self.analysis_executor.submit(self.run_cli_fingerprint, file_path, language)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f"Fingerprint generation timed out after {timeout} seconds for {file_path}")
        except Exception as e:
            log.error(f"Error in safe_run_cli_fingerprint: {e}")
            raise
    
    def safe_run_cli_analyze(self, file1_path: str, file2_path: str, language: str, timeout: int = 600) -> Dict:
        """
        Run plagiarism analysis in a separate process with timeout.
        """
        if self.analysis_executor is None:
            raise RuntimeError("Analysis executor not initialized")
        future = self.analysis_executor.submit(self.run_cli_analyze, file1_path, file2_path, language)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f"Analysis timed out after {timeout} seconds for {file1_path} vs {file2_path}")
        except Exception as e:
            log.error(f"Error in safe_run_cli_analyze: {e}")
            raise
    
    def shutdown(self):
        """Shutdown the analysis executor."""
        if self.analysis_executor:
            self.analysis_executor.shutdown(wait=True)
