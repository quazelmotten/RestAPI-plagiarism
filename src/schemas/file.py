from pydantic import BaseModel
from typing import Optional


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
