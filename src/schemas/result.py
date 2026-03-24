from pydantic import BaseModel
from typing import Optional, Any, List, Dict


class FileInfo(BaseModel):
    id: str
    filename: str


class ResultFileInfo(BaseModel):
    id: str
    filename: str


class ResultItem(BaseModel):
    file_a: ResultFileInfo
    file_b: ResultFileInfo
    ast_similarity: Optional[float] = None
    matches: Optional[Any] = None
    created_at: Optional[str] = None


class ResultResponse(BaseModel):
    id: str
    file_a: ResultFileInfo
    file_b: ResultFileInfo
    ast_similarity: Optional[float] = None
    matches: Optional[Any] = None
    created_at: Optional[str] = None
    task_id: str
    task_progress: dict


class TaskProgress(BaseModel):
    completed: int
    total: int
    percentage: float
    display: str


class ResultsListResponse(BaseModel):
    id: str
    file_a: ResultFileInfo
    file_b: ResultFileInfo
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
