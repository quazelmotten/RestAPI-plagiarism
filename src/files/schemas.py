"""
Files domain schemas - Pydantic models for file request/response.
"""

from schemas.base import CustomBaseModel


class FileResponse(CustomBaseModel):
    id: str
    filename: str
    language: str
    created_at: str | None = None
    task_id: str
    status: str
    similarity: float | None = None
    assignment_id: str | None = None
    assignment_name: str | None = None
    subject_id: str | None = None
    subject_name: str | None = None


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
