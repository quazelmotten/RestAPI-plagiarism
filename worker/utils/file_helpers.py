"""
File-related helper functions.
"""

import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)


def extract_file_hash(file_info: Dict) -> Optional[str]:
    """Extract file hash from file info dict."""
    return file_info.get('hash') or file_info.get('file_hash')


def extract_file_path(file_info: Dict) -> Optional[str]:
    """Extract file path from file info dict."""
    return file_info.get('path') or file_info.get('file_path')


def extract_filename(file_info: Dict) -> str:
    """Extract filename from file info dict."""
    return file_info.get('filename', 'unknown')


def validate_file_info(file_info: Dict) -> bool:
    """
    Validate that file info has required fields.
    
    Returns:
        True if valid, False otherwise
    """
    file_hash = extract_file_hash(file_info)
    file_path = extract_file_path(file_info)
    return bool(file_hash and file_path)


def filter_valid_files(files: list) -> list:
    """Filter out files with missing hash or path."""
    return [f for f in files if validate_file_info(f)]
