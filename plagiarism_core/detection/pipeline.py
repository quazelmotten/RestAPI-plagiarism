"""detect_plagiarism orchestrator.

Thin re-exporter for backward compatibility.
See pipeline/ subpackage for the implementation.
"""

from .pipeline import (
    detect_plagiarism as detect_plagiarism,
)
from .pipeline import (
    detect_plagiarism_from_files as detect_plagiarism_from_files,
)

__all__ = [
    "detect_plagiarism",
    "detect_plagiarism_from_files",
]
