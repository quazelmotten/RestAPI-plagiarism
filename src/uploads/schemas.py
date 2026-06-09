"""
Uploads domain schemas - Pydantic models for upload request/response.
"""

from schemas.base import CustomBaseModel


class UploadProgress(CustomBaseModel):
    completed: int = 0
    total: int = 0
    percentage: float = 0.0
    display: str = "0/0"


class UploadResponse(CustomBaseModel):
    task_id: str
    name: str | None = None
    language: str | None = None
    status: str
    similarity: float | None = None
    matches: list[dict] | dict | None = None
    error: str | None = None
    created_at: str | None = None
    progress: UploadProgress | None = None
    assignment_id: str | None = None


class UploadListResponse(CustomBaseModel):
    task_id: str
    name: str | None = None
    language: str | None = None
    status: str
    similarity: float | None = None
    matches: list[dict] | dict | None = None
    error: str | None = None
    created_at: str | None = None
    progress: UploadProgress
    files_count: int = 0
    high_similarity_count: int = 0
    total_pairs: int = 0
    avg_similarity: float = 0.0
    assignment_id: str | None = None
    assignment_name: str | None = None
    subject_id: str | None = None
    subject_name: str | None = None


class UploadCreateResponse(CustomBaseModel):
    task_id: str
    name: str | None = None
    status: str
    files_count: int


class UploadUpdateRequest(CustomBaseModel):
    name: str | None = None
    language: str | None = None
    assignment_id: str | None = None


class ReanalyzeRequest(CustomBaseModel):
    language: str | None = None


class QuickCheckRequest(CustomBaseModel):
    assignment_id: str | None = None
    language: str | None = None


class QuickCheckResponse(CustomBaseModel):
    task_id: str
    status: str
    files_count: int
    results: list[dict] = []


class FileUpdateRequest(CustomBaseModel):
    filename: str | None = None
    language: str | None = None


class FileResponse(CustomBaseModel):
    id: str
    task_id: str
    filename: str
    file_path: str
    file_hash: str
    language: str
    max_similarity: float | None = None
    is_confirmed: bool = False
    created_at: str | None = None


class ReviewPairResponse(CustomBaseModel):
    pair_id: str
    task_id: str
    file_a_id: str
    file_a_name: str
    file_b_id: str
    file_b_name: str
    ast_similarity: float | None = None
    embedding_similarity: float | None = None
    review_disposition: str | None = None
    reviewed_at: str | None = None
    assignment_id: str | None = None
    assignment_name: str | None = None
    upload_name: str | None = None
    created_at: str | None = None
