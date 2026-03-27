from pydantic import BaseModel
from typing import Optional, List


class FileResponse(BaseModel):
    id: str
    filename: str
    language: str
    created_at: Optional[str] = None
    task_id: str
    status: str
    similarity: Optional[float] = None

    class Config:
        from_attributes = True


class FileContentResponse(BaseModel):
    id: str
    filename: str
    content: str
    language: str
    file_path: str


class FileUploadInfo(BaseModel):
    id: str
    path: str
    hash: str
    filename: str


class FilesListResponse(BaseModel):
    files: List[FileResponse]
    total: int


class FileInfoListItem(BaseModel):
    """Minimal file info for dropdowns/lists."""
    id: str
    filename: str
    language: str
    task_id: str
