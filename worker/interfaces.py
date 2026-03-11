"""
Interface definitions for services.
Using Python's structural typing ( Protocols) for flexibility.
"""

from typing import Protocol, List, Dict, Tuple, Optional


class PlagiarismServiceProtocol(Protocol):
    """Protocol for plagiarism service."""
    
    def safe_run_cli_fingerprint(self, file_path: str, language: str, timeout: int = 300) -> Dict:
        ...
    
    def safe_run_cli_analyze(self, file1_path: str, file2_path: str, language: str, timeout: int = 600) -> Dict:
        ...
    
    def transform_matches_to_legacy_format(self, matches: List[Dict]) -> List[Dict]:
        ...


class ProcessorServiceProtocol(Protocol):
    """Protocol for processor service."""
    
    def ensure_files_indexed(
        self, 
        files: List[Dict], 
        language: str, 
        task_id: str,
        existing_files: Optional[List[Dict]] = None
    ) -> None:
        ...
    
    def find_intra_task_pairs(
        self, 
        files: List[Dict], 
        language: str, 
        task_id: str
    ) -> List[Tuple[dict, dict]]:
        ...
    
    def find_cross_task_pairs(
        self, 
        new_files: List[Dict], 
        existing_files: List[Dict], 
        language: str, 
        task_id: str
    ) -> List[Tuple[dict, dict]]:
        ...


class ResultServiceProtocol(Protocol):
    """Protocol for result service."""
    
    def process_pair(
        self,
        file_a: Dict,
        file_b: Dict,
        language: str,
        task_id: str,
        total_pairs: int,
        processed_count: int
    ) -> Tuple[bool, int]:
        ...
    
    def update_task_progress(
        self, 
        task_id: str, 
        processed: int, 
        total: int
    ) -> None:
        ...
    
    def finalize_task(
        self, 
        task_id: str, 
        total_pairs: int, 
        processed_count: int
    ) -> None:
        ...
