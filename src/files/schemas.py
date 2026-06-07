"""
Files domain schemas - Pydantic models for file request/response.
"""

import uuid

from schemas.base import CustomBaseModel


class FileResponse(CustomBaseModel):
    id: str
    filename: str
    language: str
    created_at: str | None = None
    task_id: str
    status: str
    similarity: float | None = None
    upload_name: str | None = None
    assignment_id: str | None = None
    assignment_name: str | None = None
    subject_id: str | None = None
    subject_name: str | None = None
    is_confirmed: bool | None = False


class FileContentResponse(CustomBaseModel):
    id: str
    filename: str
    content: str
    language: str
    file_path: str


class FileUploadInfo(CustomBaseModel):
    id: str
    path: str
    hash: str
    filename: str


class FilesListResponse(CustomBaseModel):
    files: list[FileResponse]
    total: int


class FileInfoListItem(CustomBaseModel):
    """Minimal file info for dropdowns."""

    id: str
    filename: str
    language: str
    task_id: str
    assignment_id: str | None = None
    assignment_name: str | None = None
    subject_id: str | None = None
    subject_name: str | None = None


class ReviewNoteResponse(CustomBaseModel):
    id: str
    file_id: str
    assignment_id: str
    content: str
    created_at: str


class ReviewNoteCreate(CustomBaseModel):
    content: str


class FileMoveRequest(CustomBaseModel):
    target_task_id: uuid.UUID


class BulkFileMoveRequest(CustomBaseModel):
    file_ids: list[uuid.UUID]
    target_task_id: uuid.UUID


class FileEventResponse(CustomBaseModel):
    id: str
    assignment_id: str | None = None
    task_id: str | None = None
    user_id: str | None = None
    user_email: str | None = None
    event_type: str
    metadata: dict | None = None
    created_at: str | None = None


class TaskEventResponse(CustomBaseModel):
    id: str
    event_type: str
    assignment_id: str | None = None
    assignment_name: str | None = None
    task_id: str | None = None
    task_name: str | None = None
    user_id: str | None = None
    user_email: str | None = None
    metadata: dict | None = None
    files_count: int | None = None
    created_at: str | None = None


class BulkMoveByAssignmentRequest(CustomBaseModel):
    file_ids: list[uuid.UUID]
    target_assignment_id: uuid.UUID
