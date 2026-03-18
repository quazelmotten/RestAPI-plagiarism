"""
Backward compatibility: PlagiarismService is now AnalysisService.
This import is deprecated; use AnalysisService directly for new code.
"""

from .analysis_service import AnalysisService as PlagiarismService

__all__ = ['PlagiarismService']
