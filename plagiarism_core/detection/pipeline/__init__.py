"""Detection pipeline subpackage."""

from .api import (
    detect_plagiarism as detect_plagiarism,
)
from .api import (
    detect_plagiarism_from_files as detect_plagiarism_from_files,
)

__all__ = [
    "detect_plagiarism",
    "detect_plagiarism_from_files",
]
