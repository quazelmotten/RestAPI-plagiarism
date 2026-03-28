"""
Shared schemas - base models and common response types.

Domain-specific schemas live in their respective modules:
- tasks.schemas (TaskProgress, TaskCreate, TaskResponse, TaskListResponse, TaskCreateResponse)
- files.schemas (FileResponse, FileContentResponse, FileUploadInfo, FileInfoListItem)
- results.schemas (ResultItem, ResultsListResponse, TaskResultsResponse, HistogramResponse)

Import directly from domain modules to avoid circular dependencies.
This module only exports shared schemas.
"""

from .base import CustomBaseModel
from .common import PaginatedResponse

__all__ = [
    "CustomBaseModel",
    "PaginatedResponse",
]
