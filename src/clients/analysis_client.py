"""
Analysis client for on-demand plagiarism analysis.

Re-exports the shared AnalysisService as AnalysisClient for the API layer.
"""

from worker.services.analysis_service import AnalysisService as AnalysisClient

__all__ = ["AnalysisClient"]
