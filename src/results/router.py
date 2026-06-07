"""
Results domain router - endpoints for similarity result queries and on-demand analysis.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query, status

from auth.dependencies import get_current_user
from auth.models import User
from dependencies import get_fingerprint_cache
from exceptions.exceptions import NotFoundError
from results.dependencies import get_result_service
from results.schemas import (
    BulkConfirmResponse,
    HistogramResponse,
    ResultItem,
    ReviewExportResponse,
    ReviewQueueResponse,
    ReviewStatusSummary,
    TaskResultsResponse,
)
from results.service import ResultService
from schemas.common import PaginatedResponse

router = APIRouter(prefix="/plagiarism", tags=["Results"])
logger = logging.getLogger(__name__)


@router.get(
    "/tasks/{task_id}/results",
    response_model=TaskResultsResponse,
    summary="Get task plagiarism results",
    description="Retrieve detailed similarity analysis results for a specific task.",
    responses={
        status.HTTP_200_OK: {
            "model": TaskResultsResponse,
            "description": "Results retrieved successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Task not found or no results available",
        },
    },
)
async def get_plagiarism_results(
    task_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    limit: int = Query(default=50, ge=1, le=500, description="Number of results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip for pagination"),
    current_user: User = Depends(get_current_user),
):
    """Get detailed similarity results for all file pairs in a task with progress."""
    result = await result_service.get_task_results(str(task_id), limit=limit, offset=offset)
    if not result:
        raise NotFoundError("Task not found")
    return result


@router.get(
    "/tasks/{task_id}/histogram",
    response_model=HistogramResponse,
    summary="Get similarity histogram for a task",
    description="Generate a histogram distribution of similarity scores for a given task.",
    responses={
        status.HTTP_200_OK: {
            "model": HistogramResponse,
            "description": "Histogram data retrieved successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Task not found or no results",
        },
    },
)
async def get_task_histogram(
    task_id: uuid.UUID,
    bins: int = Query(200, ge=5, le=1000, description="Number of histogram bins (5-1000)"),
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Get histogram data for a task's similarity distribution using SQL GROUP BY."""
    return await result_service.get_task_histogram(str(task_id), bins)


@router.get(
    "/results",
    response_model=PaginatedResponse,
    summary="List all similarity results",
    description="Retrieve a paginated list of all similarity results across all tasks.",
    responses={
        status.HTTP_200_OK: {
            "model": PaginatedResponse,
            "description": "Successfully retrieved results",
        },
    },
)
async def get_all_results(
    result_service: ResultService = Depends(get_result_service),
    limit: int = Query(default=50, ge=1, le=500, description="Number of results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    current_user: User = Depends(get_current_user),
):
    """Get all similarity results across all tasks with file details and progress."""
    return await result_service.get_all_results(limit=limit, offset=offset)


@router.get(
    "/file-pair",
    response_model=ResultItem,
    summary="Get file pair plagiarism results",
    description="Retrieve existing plagiarism results for a specific file pair.",
    responses={
        status.HTTP_200_OK: {
            "model": ResultItem,
            "description": "Results retrieved successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "No results found for this file pair",
        },
    },
)
async def get_file_pair(
    file_a: uuid.UUID = Query(..., description="UUID of first file"),
    file_b: uuid.UUID = Query(..., description="UUID of second file"),
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Get existing plagiarism results for a file pair."""
    result = await result_service.get_file_pair(str(file_a), str(file_b))
    if not result:
        raise NotFoundError("No results found for this file pair")
    return result


@router.post(
    "/file-pair/analyze",
    response_model=ResultItem,
    summary="Analyze a specific file pair for plagiarism",
    description="Run full analysis on a specific file pair and return detailed results.",
    responses={
        status.HTTP_200_OK: {
            "model": ResultItem,
            "description": "Analysis complete, results updated in database",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "One or both files not found",
        },
        status.HTTP_501_NOT_IMPLEMENTED: {
            "model": None,
            "description": "On-demand analysis not available via API. Use task-based analysis.",
        },
    },
)
async def analyze_file_pair(
    file_a: uuid.UUID,
    file_b: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    cache=Depends(get_fingerprint_cache),
):
    """Run full plagiarism analysis on a file pair and save results."""
    return await result_service.analyze_file_pair(str(file_a), str(file_b), cache)


@router.post(
    "/results/{result_id}/confirm",
    response_model=ResultItem,
    summary="Confirm plagiarism for a file pair",
    description="Mark both files in a pair as confirmed plagiarism.",
    responses={
        status.HTTP_200_OK: {
            "model": ResultItem,
            "description": "Files confirmed as plagiarism",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Result not found",
        },
    },
)
async def confirm_plagiarism(
    result_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Confirm plagiarism for a pair - marks both files as confirmed."""
    return await result_service.confirm_plagiarism(str(result_id), current_user)


@router.post(
    "/results/{result_id}/skip",
    response_model=ResultItem,
    summary="Skip a file pair",
    description="Mark a pair as reviewed but not confirmed (no plagiarism found).",
    responses={
        status.HTTP_200_OK: {
            "model": ResultItem,
            "description": "Pair marked as reviewed",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Result not found",
        },
    },
)
async def skip_pair(
    result_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Skip a pair - marks as reviewed but not confirmed."""
    return await result_service.skip_pair(str(result_id), current_user)


@router.post(
    "/assignments/{assignment_id}/bulk-confirm",
    response_model=BulkConfirmResponse,
    summary="Bulk confirm pairs above threshold",
    description="Confirm all pairs with similarity above a threshold. Admin only.",
    responses={
        status.HTTP_200_OK: {
            "model": BulkConfirmResponse,
            "description": "Bulk confirm completed",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Assignment not found",
        },
    },
)
async def bulk_confirm(
    assignment_id: uuid.UUID,
    threshold: float = Query(..., ge=0.0, le=1.0, description="Similarity threshold (0.0-1.0)"),
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Bulk confirm all pairs above threshold. Admin only."""
    return await result_service.bulk_confirm(str(assignment_id), threshold, current_user)


@router.post(
    "/assignments/{assignment_id}/bulk-clear",
    response_model=BulkConfirmResponse,
    summary="Bulk clear pairs",
    description="Clear all pairs (set as not plagiarized) above threshold. Admin only.",
    responses={
        status.HTTP_200_OK: {
            "model": BulkConfirmResponse,
            "description": "Pairs cleared successfully",
        },
    },
)
async def bulk_clear(
    assignment_id: uuid.UUID,
    threshold: float = Query(
        default=0.0, ge=0.0, le=1.0, description="Similarity threshold (0.0-1.0)"
    ),
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Bulk clear all pairs above threshold. Admin only."""
    return await result_service.bulk_clear(str(assignment_id), threshold, current_user)


@router.post(
    "/bulk-confirm",
    response_model=BulkConfirmResponse,
    summary="Global bulk confirm pairs above threshold",
    description="Confirm all pairs with similarity above a threshold across all accessible assignments.",
    responses={
        status.HTTP_200_OK: {
            "model": BulkConfirmResponse,
            "description": "Bulk confirm completed",
        },
    },
)
async def global_bulk_confirm(
    threshold: float = Query(..., ge=0.0, le=1.0, description="Similarity threshold (0.0-1.0)"),
    result_service: ResultService = Depends(get_result_service),
    assignment_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """Bulk confirm all pairs above threshold across all accessible assignments."""
    return await result_service.global_bulk_confirm(
        threshold, current_user, assignment_id=assignment_id
    )


@router.post(
    "/bulk-clear",
    response_model=BulkConfirmResponse,
    summary="Global bulk clear pairs",
    description="Clear all pairs (set as not plagiarized) above threshold across all accessible assignments.",
    responses={
        status.HTTP_200_OK: {
            "model": BulkConfirmResponse,
            "description": "Pairs cleared successfully",
        },
    },
)
async def global_bulk_clear(
    threshold: float = Query(
        default=0.0, ge=0.0, le=1.0, description="Similarity threshold (0.0-1.0)"
    ),
    result_service: ResultService = Depends(get_result_service),
    assignment_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """Bulk clear all pairs above threshold across all accessible assignments."""
    return await result_service.global_bulk_clear(
        threshold, current_user, assignment_id=assignment_id
    )


@router.get(
    "/assignments/{assignment_id}/review-queue",
    response_model=ReviewQueueResponse,
    summary="Get smart review queue for assignment",
    description="Get prioritized list of pairs to review, skipping confirmed files.",
    responses={
        status.HTTP_200_OK: {
            "model": ReviewQueueResponse,
            "description": "Review queue retrieved successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Assignment not found",
        },
    },
)
async def get_review_queue(
    assignment_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """Get smart review queue prioritized by unconfirmed files."""
    return await result_service.get_review_queue(
        str(assignment_id), limit, offset, current_user=current_user
    )


@router.get(
    "/review-queue",
    response_model=PaginatedResponse,
    summary="Get global review queue",
    description=(
        "Get paginated review queue across all accessible assignments. "
        "Optionally filter by assignment_id, status, and min_similarity. "
        "Subject to the caller's subject-access scope."
    ),
    responses={
        status.HTTP_200_OK: {
            "model": PaginatedResponse,
            "description": "Review queue retrieved successfully",
        },
    },
)
async def get_global_review_queue(
    result_service: ResultService = Depends(get_result_service),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    assignment_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(
        default=None,
        description="Filter by review status: all, unreviewed, plagiarism, bulk_confirmed, clear",
    ),
    min_similarity: float | None = Query(default=None, ge=0.0, le=1.0),
    search: str | None = Query(default=None, description="Filter by filename (case-insensitive)"),
    current_user: User = Depends(get_current_user),
):
    """Get global review queue across accessible assignments."""
    return await result_service.get_global_review_queue(
        current_user=current_user,
        limit=limit,
        offset=offset,
        assignment_id=assignment_id,
        status=status,
        min_similarity=min_similarity,
        search=search,
    )


@router.get(
    "/review-queue/count",
    summary="Get count of review-queue pairs matching filters",
    description=(
        "Return the total number of pairs matching the given filters. "
        "Accepts the same filter parameters as /review-queue but returns only the count."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Count retrieved successfully",
        },
    },
)
async def get_review_queue_count(
    result_service: ResultService = Depends(get_result_service),
    assignment_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(
        default=None,
        description="Filter by review status: all, unreviewed, plagiarism, bulk_confirmed, clear",
    ),
    min_similarity: float | None = Query(default=None, ge=0.0, le=1.0),
    search: str | None = Query(default=None, description="Filter by filename (case-insensitive)"),
    current_user: User = Depends(get_current_user),
):
    """Get count of review-queue pairs matching the given filters."""
    count = await result_service.get_review_queue_count(
        current_user=current_user,
        assignment_id=assignment_id,
        status=status,
        min_similarity=min_similarity,
        search=search,
    )
    return {"count": count}


@router.get(
    "/assignments/{assignment_id}/review-status",
    response_model=ReviewStatusSummary,
    summary="Get review status summary for assignment",
    description="Get counts of unreviewed, confirmed, bulk_confirmed, and cleared pairs.",
    responses={
        status.HTTP_200_OK: {
            "model": ReviewStatusSummary,
            "description": "Review status retrieved",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Assignment not found",
        },
    },
)
async def get_review_status(
    assignment_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Get review status summary for an assignment."""
    return await result_service.get_review_status(str(assignment_id), current_user=current_user)


@router.get(
    "/review-status",
    response_model=ReviewStatusSummary,
    summary="Get global review status summary",
    description=(
        "Get aggregated review status counts across all accessible assignments. "
        "If assignment_id is provided, scope to that assignment."
    ),
    responses={
        status.HTTP_200_OK: {
            "model": ReviewStatusSummary,
            "description": "Review status retrieved",
        },
    },
)
async def get_global_review_status(
    result_service: ResultService = Depends(get_result_service),
    assignment_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """Get aggregated review status counts across accessible assignments."""
    return await result_service.get_global_review_status(
        current_user=current_user, assignment_id=assignment_id
    )


@router.get(
    "/files/{file_id}/top-similar-pairs",
    response_model=PaginatedResponse,
    summary="Get top similar pairs for a file",
    description="Get top similar pairs for a file (for thorough checking).",
    responses={
        status.HTTP_200_OK: {
            "model": PaginatedResponse,
            "description": "Top similar pairs retrieved",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "File not found",
        },
    },
)
async def get_top_similar_pairs(
    file_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    limit: int = Query(default=5, ge=1, le=10),
    current_user: User = Depends(get_current_user),
):
    """Get top similar pairs for a file."""
    return await result_service.get_top_similar_pairs(str(file_id), limit)


@router.get(
    "/assignments/{assignment_id}/export-review",
    response_model=ReviewExportResponse,
    summary="Export review data as HTML",
    description="Generate an HTML report with file status, notes, and suspicious pair comparisons.",
    responses={
        status.HTTP_200_OK: {
            "model": ReviewExportResponse,
            "description": "HTML export generated successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Assignment not found",
        },
    },
)
async def export_review(
    assignment_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    threshold: float = Query(
        default=0.3, ge=0.0, le=1.0, description="Similarity threshold for suspicious pairs"
    ),
    current_user: User = Depends(get_current_user),
):
    """Export review data as HTML."""
    return await result_service.export_review_html(
        str(assignment_id), threshold, current_user=current_user
    )


@router.post(
    "/results/{result_id}/clear",
    response_model=ResultItem,
    summary="Clear a file pair",
    description="Mark a pair as reviewed and not plagiarism.",
    responses={
        status.HTTP_200_OK: {
            "model": ResultItem,
            "description": "Pair marked as cleared",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Result not found",
        },
    },
)
async def clear_pair(
    result_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Clear a pair - marks as reviewed but not plagiarism."""
    return await result_service.clear_pair(str(result_id), current_user)


@router.post(
    "/results/{result_id}/undo",
    response_model=ResultItem,
    summary="Undo a review",
    description="Reset a pair back to unreviewed state.",
    responses={
        status.HTTP_200_OK: {
            "model": ResultItem,
            "description": "Pair undo review",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Result not found",
        },
    },
)
async def undo_review(
    result_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Undo review - reset pair to unreviewed."""
    return await result_service.undo_review(str(result_id), current_user)


@router.get(
    "/assignments/{assignment_id}/cleared-pairs",
    response_model=PaginatedResponse,
    summary="Get cleared pairs",
    description="Get all cleared (reviewed-not-plagiarism) pairs for an assignment.",
)
async def get_cleared_pairs(
    assignment_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """Get cleared pairs for an assignment."""
    return await result_service.get_cleared_pairs(
        str(assignment_id), limit, offset, current_user=current_user
    )


@router.get(
    "/assignments/{assignment_id}/plagiarism-pairs",
    response_model=PaginatedResponse,
    summary="Get plagiarism pairs",
    description="Get all confirmed plagiarism pairs for an assignment.",
)
async def get_plagiarism_pairs(
    assignment_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """Get plagiarism pairs for an assignment."""
    return await result_service.get_plagiarism_pairs(
        str(assignment_id), limit, offset, current_user=current_user
    )


@router.get(
    "/assignments/{assignment_id}/pairs",
    response_model=PaginatedResponse,
    summary="Get pairs by status",
    description="Get all pairs for an assignment filtered by review status.",
)
async def get_pairs_by_status(
    assignment_id: uuid.UUID,
    status: str = Query(
        default="all",
        description="Filter by status: all, unreviewed, confirmed, bulk_confirmed, cleared",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Get pairs by status for an assignment."""
    return await result_service.get_pairs_by_status(
        str(assignment_id), status, limit, offset, current_user=current_user
    )


def sanitize_filename(name: str) -> str:
    """Sanitize filename to be safe for all filesystems (FAT, NTFS, etc.)."""
    import re

    # Remove or replace characters that are invalid in filenames
    # Invalid: < > : " / \ | ? *
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", name)
    # Remove any control characters
    sanitized = re.sub(r"[\x00-\x1f\x7f]", "", sanitized)
    # Limit length to avoid path issues
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized


@router.get("/assignments/{assignment_id}/reports/{result_id}/pdf")
async def export_single_pdf(
    assignment_id: uuid.UUID,
    result_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Export a single plagiarism report as PDF."""
    import logging

    logger = logging.getLogger(__name__)

    import io

    from fastapi.responses import StreamingResponse

    try:
        payload = await result_service.build_report_payload(
            str(assignment_id),
            str(result_id),
            current_user,
        )
        logger.info(f"PDF payload keys: {payload.keys()}")
        logger.info(f"PDF payload matches count: {len(payload.get('matches', []))}")

        from reports.generator import generate_report_pdf

        pdf_bytes = await generate_report_pdf(payload)
        logger.info(f"PDF generated: {len(pdf_bytes)} bytes")

        # Option 2: result_id + sanitized filenames (unique + human-readable)
        file_a_name = sanitize_filename(payload["file_a"]["filename"])
        file_b_name = sanitize_filename(payload["file_b"]["filename"])
        filename = f"{result_id}_{file_a_name}_vs_{file_b_name}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )
    except Exception as e:
        logger.error(f"PDF export error: {e}", exc_info=True)
        raise


@router.get("/assignments/{assignment_id}/reports/pdf-zip")
async def export_all_pdfs_zip(
    assignment_id: uuid.UUID,
    task_id: str | None = None,
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Export all confirmed plagiarism pairs for an assignment as a ZIP archive.
    Optionally filter by task_id to export only pairs from a specific task."""
    import io
    import logging
    import zipfile

    from fastapi.responses import StreamingResponse

    logger = logging.getLogger(__name__)

    # Build query - filter by assignment and confirmed status
    from shared.models import PlagiarismTask, SimilarityResult
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    query = (
        select(SimilarityResult)
        .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
        .where(PlagiarismTask.assignment_id == assignment_id)
        .where(SimilarityResult.review_disposition.in_(["plagiarism", "bulk_confirmed"]))
        .options(selectinload(SimilarityResult.file_a), selectinload(SimilarityResult.file_b))
    )

    # Filter by task_id if provided
    if task_id:
        from uuid import UUID

        try:
            task_uuid = UUID(task_id)
            query = query.where(SimilarityResult.task_id == task_uuid)
        except ValueError:
            logger.warning(f"Invalid task_id format: {task_id}")

    result = await result_service.db.execute(query)
    results = result.scalars().all()
    result_list = list(results)

    if not result_list:
        return StreamingResponse(
            io.BytesIO(b""),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="assignment_{assignment_id}_reports.zip'
            },
        )

    # Collect payloads and generate PDFs
    from reports.generator import generate_report_pdf

    pdf_list = []

    for result in result_list:
        try:
            logger.info(f"Processing result {result.id}")
            payload = await result_service.build_report_payload(
                str(assignment_id),
                str(result.id),
                current_user,
                file_a=result.file_a,
                file_b=result.file_b,
            )
            logger.info(f"Payload built for {result.id}")

            # Option 2: result.id + sanitized filenames (unique + human-readable)
            file_a_name = sanitize_filename(payload["file_a"]["filename"])
            file_b_name = sanitize_filename(payload["file_b"]["filename"])
            filename = f"{result.id}_{file_a_name}_vs_{file_b_name}.pdf"

            # Generate PDF using the appropriate backend
            logger.info(f"Generating PDF for {filename}")
            pdf_bytes = await generate_report_pdf(payload)
            logger.info(f"PDF generated: {len(pdf_bytes)} bytes")

            pdf_list.append((filename, pdf_bytes))
        except Exception as e:
            logger.error(f"Error generating PDF for {result.id}: {e}", exc_info=True)
            continue

    logger.info(f"Generated {len(pdf_list)} PDFs")

    # Create ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for filename, pdf_bytes in pdf_list:
            zip_file.writestr(filename, pdf_bytes)

    zip_buffer.seek(0)
    zip_content = zip_buffer.getvalue()

    # Determine filename for ZIP
    if task_id:
        zip_filename = f"task_{task_id}_reports.zip"
    else:
        zip_filename = f"assignment_{assignment_id}_reports.zip"

    logger.info(f"Returning ZIP: {zip_filename} ({len(zip_content)} bytes)")

    return StreamingResponse(
        io.BytesIO(zip_content),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "Content-Length": str(len(zip_content)),
        },
    )
