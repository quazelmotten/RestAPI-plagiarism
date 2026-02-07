from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pathlib import Path
import uuid
import shutil
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_async_session
from models.models import PlagiarismTask
from rabbit import publish_message

router = APIRouter(prefix="/plagiarism", tags=["Plagiarism"])

# Use absolute path for uploads to ensure both API and worker can access files
UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@router.post("/check")
async def check_plagiarism(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    language: str = Form("python"),
    db: AsyncSession = Depends(get_async_session),
):
    print("POST /plagiarism/check called")
    task_id = str(uuid.uuid4())
    print(f"Generated task_id: {task_id}")

    path1 = UPLOAD_DIR / f"{task_id}_1_{file1.filename}"
    path2 = UPLOAD_DIR / f"{task_id}_2_{file2.filename}"

    with path1.open("wb") as f:
        shutil.copyfileobj(file1.file, f)

    with path2.open("wb") as f:
        shutil.copyfileobj(file2.file, f)

    # Create task record in database
    print(f"Creating task with ID: {task_id}")
    task = PlagiarismTask(
        id=task_id,
        status="queued",
        similarity=None,
        matches=None,
        error=None
    )
    db.add(task)
    print("Task added to session")
    await db.commit()
    print("Task committed to database")

    await publish_message(
        queue="plagiarism_queue",
        message={
            "task_id": task_id,
            "file1": str(path1),
            "file2": str(path2),
            "language": language,
        },
    )

    return {
        "task_id": task_id,
        "status": "queued"
    }

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
