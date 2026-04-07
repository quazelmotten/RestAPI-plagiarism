"""
Tasks domain schemas - Pydantic models for task request/response.
"""

from schemas.base import CustomBaseModel


class TaskProgress(CustomBaseModel):
    completed: int = 0
    total: int = 0
    percentage: float = 0.0
    display: str = "0/0"


class TaskCreate(CustomBaseModel):
    language: str = "python"


class TaskResponse(CustomBaseModel):
    task_id: str
    status: str
    similarity: float | None = None
    matches: list[dict] | dict | None = None
    error: str | None = None
    created_at: str | None = None
    progress: TaskProgress | None = None


class TaskListResponse(CustomBaseModel):
    task_id: str
    status: str
    similarity: float | None = None
    matches: list[dict] | dict | None = None
    error: str | None = None
    created_at: str | None = None
    progress: TaskProgress
    files_count: int = 0
    high_similarity_count: int = 0
    total_pairs: int = 0
    avg_similarity: float = 0.0
    assignment_id: str | None = None
    assignment_name: str | None = None
    subject_id: str | None = None
    subject_name: str | None = None


class TaskCreateResponse(CustomBaseModel):
    task_id: str
    status: str
    files_count: int
