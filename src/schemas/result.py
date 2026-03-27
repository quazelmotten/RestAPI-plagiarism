from pydantic import BaseModel
from typing import Optional, Any, List

from schemas.task import TaskProgress


class FileInfo(BaseModel):
    id: str
    filename: str


class ResultItem(BaseModel):
    file_a: FileInfo
    file_b: FileInfo
    ast_similarity: Optional[float] = None
    matches: Optional[Any] = None
    created_at: Optional[str] = None


class ResultsListResponse(BaseModel):
    id: str
    file_a: FileInfo
    file_b: FileInfo
    ast_similarity: Optional[float] = None
    matches: Optional[Any] = None
    created_at: Optional[str] = None
    task_id: str
    task_progress: dict


class TaskResultsResponse(BaseModel):
    task_id: str
    status: str
    created_at: Optional[str] = None
    progress: TaskProgress
    total_pairs: int
    files: List[FileInfo]
    results: List[ResultItem]
    overall_stats: Optional[dict] = None  # Contains avg_similarity, high, medium, low counts


class FileSimilarityItem(BaseModel):
    """Similarity result involving a specific file."""
    id: str
    filename: str
    language: str
    task_id: str
    status: str
    similarity: float


class HistogramBin(BaseModel):
    """A single histogram bucket."""
    range: str
    count: int


class HistogramResponse(BaseModel):
    """Histogram distribution for a task's similarity results."""
    histogram: List[HistogramBin]
    total: int
