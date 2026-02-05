from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update

from models import Results, PlagiarismTask
from database import get_session


def insert_result(
    result_uuid: UUID,
    engine: str,
    stdout: bytes,
    stderr: bytes,
    params: str,
) -> None:
    end_time = datetime.utcnow()
    session = next(get_session())
    query = Results(
        result_uuid=result_uuid,
        stdout=stdout,
        stderr=stderr,
        params=params,
        engine=engine,
        end_at=end_time
    )
    session.add(query)
    session.commit()


def select_result_uuid(result_uuid: UUID) -> UUID:
    session = next(get_session())
    query = select(Results.result_uuid).filter(Results.result_uuid == result_uuid).limit(1)
    result = session.execute(query)
    return result


def update_plagiarism_task(
    task_id: str,
    status: str,
    similarity: float = None,
    matches: dict = None,
    error: str = None,
) -> None:
    session = next(get_session())
    stmt = (
        update(PlagiarismTask)
        .where(PlagiarismTask.id == task_id)
        .values(
            status=status,
            similarity=similarity,
            matches=matches,
            error=error
        )
    )
    session.execute(stmt)
    session.commit()
