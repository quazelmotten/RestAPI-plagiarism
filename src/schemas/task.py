from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class TaskProgress(BaseModel):
    completed: int = 0
    total: int = 0
    percentage: float = 0.0
    display: str = "0/0"


class TaskCreate(BaseModel):
    language: str = "python"


class TaskResponse(BaseModel):
    task_id: str
    status: str
    similarity: Optional[float] = None
    matches: Optional[Any] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    progress: Optional[TaskProgress] = None

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    task_id: str
    status: str
    similarity: Optional[float] = None
    matches: Optional[Any] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    progress: TaskProgress
    files_count: int = 0
    high_similarity_count: int = 0
    total_pairs: int = 0


class TaskCreateResponse(BaseModel):
    task_id: str
    status: str
    files_count: int
