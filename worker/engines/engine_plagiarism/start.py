from worker.rabbit import consume
from worker.database import SessionLocal
from worker.models import PlagiarismTask
from worker.plagiarism.analyzer import analyze_plagiarism

def handle_message(message):
    db = SessionLocal()
    task_id = message["task_id"]

    try:
        similarity, matches = analyze_plagiarism(
            message["file1"],
            message["file2"],
            message.get("language", "python"),
        )

        task = db.query(PlagiarismTask).get(task_id)
        task.status = "DONE"
        task.similarity = similarity
        task.matches = matches  # JSONB column
        db.commit()

    except Exception as e:
        task = db.query(PlagiarismTask).get(task_id)
        task.status = "ERROR"
        task.error = str(e)
        db.commit()
        raise  # triggers DLQ
