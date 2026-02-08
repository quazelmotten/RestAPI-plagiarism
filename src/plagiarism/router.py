from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import List
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_async_session
from models.models import PlagiarismTask, File as FileModel, SimilarityResult
from rabbit import publish_message
from s3_storage import s3_storage
from sqlalchemy import select, and_, func

router = APIRouter(prefix="/plagiarism", tags=["Plagiarism"])

BUCKET_NAME = "plagiarism-files"

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
    """Get all plagiarism tasks with their results."""
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
    }


@router.get("/{task_id}/results")
async def get_plagiarism_results(
    task_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """Get detailed similarity results for all file pairs in a task."""
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
    
    # Format results
    formatted_results = []
    for result in results:
        formatted_results.append({
            "file_a": {
                "id": str(result.file_a_id),
                "filename": file_map.get(str(result.file_a_id), "Unknown")
            },
            "file_b": {
                "id": str(result.file_b_id),
                "filename": file_map.get(str(result.file_b_id), "Unknown")
            },
            "token_similarity": result.token_similarity,
            "ast_similarity": result.ast_similarity,
            "matches": result.matches,
            "created_at": str(result.created_at) if result.created_at else None
        })
    
    return {
        "task_id": task_id,
        "status": task.status,
        "total_pairs": len(formatted_results),
        "files": [{"id": str(f.id), "filename": f.filename} for f in files],
        "results": formatted_results
    }
