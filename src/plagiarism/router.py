from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import List, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_async_session
from models.models import PlagiarismTask, File as FileModel, SimilarityResult
from rabbit import publish_message
from s3_storage import s3_storage
from sqlalchemy import select, and_, func

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'worker'))
from redis_cache import cache as redis_cache

router = APIRouter(prefix="/plagiarism", tags=["Plagiarism"])

BUCKET_NAME = "plagiarism-files"


def calculate_matches(file_a_hash: str, file_b_hash: str) -> List[dict]:
    """Calculate matching regions on-demand using Redis cache."""
    if not redis_cache.is_connected:
        return []
    
    try:
        raw_matches = redis_cache.find_matching_regions(file_a_hash, file_b_hash)
        if not raw_matches:
            return []
        
        merged_matches = redis_cache.merge_adjacent_matches(raw_matches)
        
        return [
            {
                "file_a_start_line": match["file1"]["start_line"],
                "file_a_end_line": match["file1"]["end_line"],
                "file_b_start_line": match["file2"]["start_line"],
                "file_b_end_line": match["file2"]["end_line"]
            }
            for match in merged_matches
        ]
    except Exception:
        return []

@router.post("/check")
async def check_plagiarism(
    files: List[UploadFile] = File(..., description="Multiple files to check for plagiarism"),
    language: str = Form("python"),
    db: AsyncSession = Depends(get_async_session),
):
    print("POST /plagiarism/check called")
    task_id_str = str(uuid.uuid4())
    print(f"Generated task_id: {task_id_str}")

    # Create task record in database
    print(f"Creating task with ID: {task_id_str}")
    task = PlagiarismTask(
        id=task_id_str,
        status="queued",
        similarity=None,
        matches=None,
        error=None
    )
    db.add(task)
    print("Task added to session")
    await db.commit()
    print("Task committed to database")

    # Process each file - upload to S3 and store metadata
    file_paths = []
    for upload_file in files:
        if not upload_file.filename:
            continue
            
        # Reset file pointer to beginning
        upload_file.file.seek(0)
        
        # Upload to S3 storage
        s3_result = s3_storage.upload_file(
            bucket_name=BUCKET_NAME,
            file_data=upload_file.file,
            filename=upload_file.filename
        )
        
        # Generate file ID
        file_id_str = str(uuid.uuid4())
        
        # Store file metadata in database
        file_record = FileModel(
            id=file_id_str,
            task_id=task_id_str,
            filename=upload_file.filename,
            file_path=s3_result["path"],
            file_hash=s3_result["hash"],
            language=language
        )
        db.add(file_record)
        await db.flush()  # Flush to get the ID assigned
        
        file_paths.append({
            "id": file_id_str,
            "path": s3_result["path"],
            "hash": s3_result["hash"],
            "filename": upload_file.filename
        })
        print(f"Uploaded {upload_file.filename} to S3 with hash {s3_result['hash']}, id={file_id_str}")
    
    await db.commit()
    print(f"Stored metadata for {len(file_paths)} files")

    # Publish message to RabbitMQ with all file paths
    await publish_message(
        queue="plagiarism_queue",
        message={
            "task_id": task_id_str,
            "files": file_paths,
            "language": language,
        },
    )

    return {
        "task_id": task_id_str,
        "status": "queued",
        "files_count": len(files)
    }

@router.get("/tasks")
async def get_all_tasks(
    db: AsyncSession = Depends(get_async_session),
):
    """Get all plagiarism tasks with their results and progress."""
    result = await db.execute(
        select(PlagiarismTask).order_by(PlagiarismTask.id)
    )
    tasks = result.scalars().all()
    
    return [
        {
            "task_id": str(task.id),
            "status": task.status,
            "similarity": task.similarity,
            "matches": task.matches,
            "error": task.error,
            "created_at": str(task.created_at) if task.created_at else None,
            "progress": {
                "completed": task.processed_pairs or 0,
                "total": task.total_pairs or 0,
                "percentage": round((task.progress or 0) * 100, 1),
                "display": f"{task.processed_pairs or 0}/{task.total_pairs or 0}"
            }
        }
        for task in tasks
    ]


@router.get("/files/all")
async def get_all_files(
    db: AsyncSession = Depends(get_async_session),
):
    """Get all files with their max similarity from all comparisons."""
    print("GET /files/all called")
    try:
        # Get all files with task info
        files_result = await db.execute(
            select(
                FileModel.id,
                FileModel.filename,
                FileModel.language,
                FileModel.created_at,
                PlagiarismTask.id.label("task_id"),
                PlagiarismTask.status,
            )
            .join(PlagiarismTask, FileModel.task_id == PlagiarismTask.id)
            .order_by(FileModel.created_at.desc())
        )
        
        files = files_result.all()
        print(f"Found {len(files)} files")
        
        # Get max similarity for each file
        file_ids = [row.id for row in files]
        
        # Query to get max similarity per file
        similarity_result = await db.execute(
            select(
                SimilarityResult.file_a_id,
                SimilarityResult.file_b_id,
                func.max(SimilarityResult.ast_similarity).label("max_similarity")
            )
            .where(
                (SimilarityResult.file_a_id.in_(file_ids)) | 
                (SimilarityResult.file_b_id.in_(file_ids))
            )
            .group_by(SimilarityResult.file_a_id, SimilarityResult.file_b_id)
        )
        
        # Build a map of file_id -> max_similarity
        max_similarities = {}
        for row in similarity_result.all():
            sim = row.max_similarity or 0
            # Update max for file_a
            if row.file_a_id not in max_similarities or sim > max_similarities[row.file_a_id]:
                max_similarities[row.file_a_id] = sim
            # Update max for file_b
            if row.file_b_id not in max_similarities or sim > max_similarities[row.file_b_id]:
                max_similarities[row.file_b_id] = sim
        
        response_data = [
            {
                "id": str(row.id),
                "filename": row.filename,
                "language": row.language,
                "created_at": str(row.created_at) if row.created_at else None,
                "task_id": str(row.task_id),
                "status": row.status,
                "similarity": max_similarities.get(row.id),
            }
            for row in files
        ]
        print(f"Returning {len(response_data)} files")
        return response_data
    except Exception as e:
        print(f"Error in get_all_files: {e}")
        import traceback
        traceback.print_exc()
        raise


@router.get("/{task_id}")
async def get_plagiarism_result(
    task_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    task = await db.get(PlagiarismTask, task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": str(task.id),
        "status": task.status,
        "similarity": task.similarity,
        "matches": task.matches,
        "error": task.error,
        "progress": {
            "completed": task.processed_pairs or 0,
            "total": task.total_pairs or 0,
            "percentage": float(round((task.progress or 0) * 100, 1)),
            "display": f"{task.processed_pairs or 0}/{task.total_pairs or 0}"
        }
    }


@router.get("/results/all")
async def get_all_results(
    db: AsyncSession = Depends(get_async_session),
):
    """Get all similarity results across all tasks with file details and progress."""
    try:
        # Get all tasks with their progress
        tasks_result = await db.execute(
            select(
                PlagiarismTask.id,
                PlagiarismTask.status,
                PlagiarismTask.total_pairs,
                PlagiarismTask.processed_pairs,
                PlagiarismTask.progress
            )
        )
        tasks_map = {
            str(row.id): {
                "status": row.status,
                "total_pairs": row.total_pairs or 0,
                "processed_pairs": row.processed_pairs or 0,
                "progress_pct": float(round((row.progress or 0) * 100, 1)),
                "progress_display": f"{row.processed_pairs or 0}/{row.total_pairs or 0}"
            }
            for row in tasks_result.all()
        }
        
        # Get all similarity results with file details
        results_result = await db.execute(
            select(
                SimilarityResult.id,
                SimilarityResult.file_a_id,
                SimilarityResult.file_b_id,
                SimilarityResult.ast_similarity,
                SimilarityResult.created_at,
                PlagiarismTask.id.label("task_id"),
                FileModel.filename.label("file_a_filename"),
                FileModel.file_hash.label("file_a_hash"),
            )
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .join(FileModel, SimilarityResult.file_a_id == FileModel.id)
            .order_by(SimilarityResult.ast_similarity.desc())
        )
        
        results = results_result.all()
        
        # Get file_b info in a separate query
        file_b_ids = [row.file_b_id for row in results]
        files_result = await db.execute(
            select(FileModel.id, FileModel.filename, FileModel.file_hash)
            .where(FileModel.id.in_(file_b_ids))
        )
        file_b_map = {str(row.id): {"filename": row.filename, "file_hash": row.file_hash} for row in files_result.all()}
        
        formatted_results = []
        for result in results:
            task_id = str(result.task_id)
            task_progress = tasks_map.get(task_id, {})
            
            file_a_hash = result.file_a_hash
            file_b_info = file_b_map.get(str(result.file_b_id), {})
            file_b_hash = file_b_info.get("file_hash")
            
            matches = []
            if file_a_hash and file_b_hash and result.ast_similarity and result.ast_similarity >= 0.15:
                matches = calculate_matches(file_a_hash, file_b_hash)
            
            formatted_results.append({
                "id": str(result.id),
                "file_a": {
                    "id": str(result.file_a_id),
                    "filename": result.file_a_filename
                },
                "file_b": {
                    "id": str(result.file_b_id),
                    "filename": file_b_info.get("filename", "Unknown")
                },
                "ast_similarity": result.ast_similarity,
                "matches": matches,
                "created_at": str(result.created_at) if result.created_at else None,
                "task_id": task_id,
                "task_progress": task_progress
            })
        
        return formatted_results
    except Exception as e:
        print(f"Error in get_all_results: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch results: {str(e)}")


@router.get("/{task_id}/results")
async def get_plagiarism_results(
    task_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """Get detailed similarity results for all file pairs in a task with progress."""
    # Check if task exists
    task = await db.get(PlagiarismTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get all files for this task
    files_result = await db.execute(
        select(FileModel).where(FileModel.task_id == task_id)
    )
    files = files_result.scalars().all()
    
    # Create a mapping of file_id to filename
    file_map = {str(f.id): f.filename for f in files}
    
    # Get all similarity results for this task
    results_result = await db.execute(
        select(SimilarityResult).where(SimilarityResult.task_id == task_id)
    )
    results = results_result.scalars().all()
    
    # Get all file IDs from the results (both file_a and file_b, which might be from different tasks for cross-task comparison)
    file_ids = set()
    for result in results:
        file_ids.add(str(result.file_a_id))
        file_ids.add(str(result.file_b_id))
    
    # Get all files that appear in results (across all tasks for cross-task comparison)
    if file_ids:
        files_result = await db.execute(
            select(FileModel).where(FileModel.id.in_(file_ids))
        )
        all_files = files_result.scalars().all()
        file_map = {str(f.id): {"filename": f.filename, "file_hash": f.file_hash} for f in all_files}
    else:
        file_map = {}
    
    # Format results
    formatted_results = []
    for result in results:
        file_a_info = file_map.get(str(result.file_a_id), {})
        file_b_info = file_map.get(str(result.file_b_id), {})
        
        matches = []
        file_a_hash = file_a_info.get("file_hash")
        file_b_hash = file_b_info.get("file_hash")
        if file_a_hash and file_b_hash and result.ast_similarity and result.ast_similarity >= 0.15:
            matches = calculate_matches(file_a_hash, file_b_hash)
        
        formatted_results.append({
            "file_a": {
                "id": str(result.file_a_id),
                "filename": file_a_info.get("filename", "Unknown")
            },
            "file_b": {
                "id": str(result.file_b_id),
                "filename": file_b_info.get("filename", "Unknown")
            },
            "ast_similarity": result.ast_similarity,
            "matches": matches,
            "created_at": str(result.created_at) if result.created_at else None
        })
    
    # Use task.total_pairs if available, otherwise fall back to results count
    actual_total_pairs = task.total_pairs if task.total_pairs else len(formatted_results)
    
    return {
        "task_id": task_id,
        "status": task.status,
        "created_at": str(task.created_at) if task.created_at else None,
        "progress": {
            "completed": task.processed_pairs or len(formatted_results),
            "total": actual_total_pairs,
            "percentage": round(((task.processed_pairs or len(formatted_results)) / max(actual_total_pairs, 1)) * 100, 1),
            "display": f"{task.processed_pairs or len(formatted_results)}/{actual_total_pairs}"
        },
        "total_pairs": actual_total_pairs,
        "files": [{"id": str(f.id), "filename": f.filename} for f in files],
        "results": formatted_results
    }


@router.get("/files/{file_id}/content")
async def get_file_content(
    file_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """Get file content by file ID."""
    # Get file metadata
    file_result = await db.get(FileModel, file_id)
    if not file_result:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Download from S3 storage
    try:
        # The file_path is stored as full path, but download_file expects key
        # We need to extract the key part (relative to bucket)
        key = file_result.file_path.split(f"{BUCKET_NAME}/")[-1]
        
        content = s3_storage.download_file(bucket_name=BUCKET_NAME, key=key)
        
        if content is None:
            raise HTTPException(status_code=404, detail="File content not found in storage")
        
        return {
            "id": str(file_result.id),
            "filename": file_result.filename,
            "content": content.decode('utf-8'),
            "language": file_result.language,
            "file_path": file_result.file_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")
