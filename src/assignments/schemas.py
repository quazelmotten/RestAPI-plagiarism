"""
Assignments domain schemas - Pydantic models for assignment request/response.
"""

from results.schemas import FileInfo, ResultItem
from schemas.base import CustomBaseModel
from tasks.schemas import TaskListResponse


class AssignmentCreate(CustomBaseModel):
    name: str
    description: str | None = None


class AssignmentResponse(CustomBaseModel):
    id: str
    name: str
    description: str | None = None
    created_at: str | None = None
    tasks_count: int = 0
    files_count: int = 0


class AssignmentUpdate(CustomBaseModel):
    name: str | None = None
    description: str | None = None


class AssignmentFullResponse(CustomBaseModel):
    """Full assignment details with all tasks, files, results, and stats."""

    id: str
    name: str
    description: str | None = None
    created_at: str | None = None
    tasks_count: int = 0
    files_count: int = 0
    tasks: list[TaskListResponse] = []
    files: list[FileInfo] = []
    results: list[ResultItem] = []
    total_pairs: int = 0
    overall_stats: dict | None = None
