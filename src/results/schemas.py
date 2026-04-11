"""
Results domain schemas - Pydantic models for similarity results.
"""

from schemas.base import CustomBaseModel
from tasks.schemas import TaskProgress


class MatchLocation(CustomBaseModel):
    """Represents a location in a file for a matched fragment."""

    start_line: int
    start_col: int
    end_line: int
    end_col: int


class MatchDetail(CustomBaseModel):
    """Details of a single matching fragment between two files."""

    file1: MatchLocation
    file2: MatchLocation
    kgram_count: int
    plagiarism_type: int | None = 1
    similarity: float | None = 1.0
    details: dict | None = None
    description: str | None = None


class FileInfo(CustomBaseModel):
    id: str
    filename: str
    task_id: str | None = None
    max_similarity: float | None = None
    is_confirmed: bool = False


class ResultItem(CustomBaseModel):
    id: str | None = None
    file_a: FileInfo
    file_b: FileInfo
    ast_similarity: float | None = None
    matches: list[MatchDetail] | None = None
    created_at: str | None = None


class ResultsListResponse(CustomBaseModel):
    id: str
    file_a: FileInfo
    file_b: FileInfo
    ast_similarity: float | None = None
    matches: list[MatchDetail] | None = None
    created_at: str | None = None
    task_id: str
    task_progress: dict


class TaskResultsResponse(CustomBaseModel):
    task_id: str
    status: str
    created_at: str | None = None
    progress: TaskProgress
    total_pairs: int
    files: list[FileInfo]
    results: list[ResultItem]
    overall_stats: dict | None = None


class HistogramBin(CustomBaseModel):
    """A single histogram bucket."""

    range: str
    count: int


class HistogramResponse(CustomBaseModel):
    """Histogram distribution for a task's similarity results."""

    histogram: list[HistogramBin]
    total: int


class ReviewQueueResponse(CustomBaseModel):
    """Smart review queue for an assignment."""

    assignment_id: str
    total_files: int
    confirmed_files: int
    remaining_files: int
    queue: list[ResultItem]
    estimated_reviews: int


class BulkConfirmResponse(CustomBaseModel):
    """Response for bulk confirm operation."""

    assignment_id: str
    threshold: float
    confirmed_pairs: int
    confirmed_files: int
    skipped_pairs: int


class ReviewExportResponse(CustomBaseModel):
    """Response for review export containing HTML content."""

    html_content: str
    filename: str


class ReviewStatusSummary(CustomBaseModel):
    """Summary of review status for an assignment."""

    assignment_id: str
    total_pairs: int
    unreviewed: int
    confirmed: int
    bulk_confirmed: int
    cleared: int
