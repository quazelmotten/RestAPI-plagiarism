"""
Unit tests for FileService.
Tests move_file, delete_file, exist, review note CRUD interactions.
"""

import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from files.service import FileService
from shared.models import PlagiarismTask, ReviewNote

# src/ must be on sys.path so `from files.service` / `from constants` etc. work
_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db


@pytest.fixture
def service(mock_db):
    """FileService with a mock db and a fresh AsyncMock repo."""
    svc = FileService(db=mock_db)
    svc.repo = AsyncMock()
    return svc


# ---------------------------------------------------------------------------
# get_all_files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_all_files_delegates_to_repo(service):
    expected = [MagicMock(), MagicMock()]
    service.repo.get_all_files.return_value = expected

    result = await service.get_all_files()

    service.repo.get_all_files.assert_called_once()
    assert result == expected


# ---------------------------------------------------------------------------
# get_files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_files_passes_through_kwargs(service):
    from schemas.common import PaginatedResponse

    mock_result = MagicMock(spec=PaginatedResponse)
    service.repo.get_files.return_value = mock_result

    result = await service.get_files(limit=10, offset=20, filename="foo")

    service.repo.get_files.assert_called_once_with(
        limit=10, offset=20, filename="foo",
        language=None, status=None, task_id=None,
        assignment_id=None, subject_id=None,
        similarity_min=None, similarity_max=None,
        submitted_after=None, submitted_before=None,
    )
    assert result == mock_result


@pytest.mark.asyncio
async def test_get_files_parses_date_filters(service):
    from schemas.common import PaginatedResponse

    mock_result = MagicMock(spec=PaginatedResponse)
    service.repo.get_files.return_value = mock_result

    await service.get_files(submitted_after="2024-01-01", submitted_before="2024-12-31")

    call_kwargs = service.repo.get_files.call_args[1]
    assert call_kwargs["submitted_after"] is not None
    assert call_kwargs["submitted_before"] is not None
    assert call_kwargs["submitted_before"].hour == 23
    assert call_kwargs["submitted_before"].minute == 59
    assert call_kwargs["submitted_before"].second == 59


# ---------------------------------------------------------------------------
# get_file_content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_file_content_returns_none_when_file_missing(service):
    service.repo.get_file.return_value = None

    result = await service.get_file_content("missing", MagicMock())
    assert result is None


@pytest.mark.asyncio
async def test_get_file_content_returns_none_when_s3_empty(service):
    mock_file = MagicMock(file_path="s3://bucket/path/file.py")
    service.repo.get_file.return_value = mock_file

    mock_storage = MagicMock()
    mock_storage.download_file_async = AsyncMock(return_value=None)

    result = await service.get_file_content("file-1", mock_storage)
    assert result is None


@pytest.mark.asyncio
async def test_get_file_content_downloads_and_returns_response(service):
    mock_file = MagicMock(
        id="f1", filename="app.py", language="python",
        file_path="s3://bucket/uploads/app.py",
    )
    service.repo.get_file.return_value = mock_file

    mock_storage = MagicMock()
    mock_storage.download_file_async = AsyncMock(return_value=b"print('hello')")

    result = await service.get_file_content("f1", mock_storage)

    assert result.id == "f1"
    assert result.filename == "app.py"
    assert result.content == "print('hello')"
    assert result.language == "python"
    # S3 key should be the path segment after BUCKET_NAME
    mock_storage.download_file_async.assert_called_once()


# ---------------------------------------------------------------------------
# get_file_similarities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_file_similarities_delegates_to_repo(service):
    from schemas.common import PaginatedResponse

    mock_paginated = MagicMock(spec=PaginatedResponse)
    service.repo.get_file_similarities.return_value = mock_paginated

    result = await service.get_file_similarities("file-abc")
    service.repo.get_file_similarities.assert_called_once_with("file-abc")
    assert result == mock_paginated


# ---------------------------------------------------------------------------
# get_file_notes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_file_notes_raises_not_found_when_file_missing(service):
    service.repo.get_file.return_value = None

    from exceptions.exceptions import NotFoundError

    with pytest.raises(NotFoundError, match="File not found"):
        await service.get_file_notes("no-file")


@pytest.mark.asyncio
async def test_get_file_notes_returns_notes_for_file(service):
    mock_file = MagicMock(id="file-1")
    service.repo.get_file.return_value = mock_file

    mock_note = MagicMock(
        id="n1",
        file_id="file-1",
        assignment_id="asgn-1",
        content="check this",
        created_at=MagicMock(isoformat=MagicMock(return_value="2024-01-01T00:00:00")),
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_note]
    service.db.execute = AsyncMock(return_value=mock_result)

    result = await service.get_file_notes("file-1")

    assert len(result) == 1
    assert result[0].id == "n1"
    assert result[0].content == "check this"
    assert result[0].created_at == "2024-01-01T00:00:00"


@pytest.mark.asyncio
async def test_get_file_notes_handles_null_created_at(service):
    mock_file = MagicMock(id="file-1")
    service.repo.get_file.return_value = mock_file

    mock_note = MagicMock(
        id="n1", file_id="file-1", assignment_id="a1",
        content="t", created_at=None,
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_note]
    service.db.execute = AsyncMock(return_value=mock_result)

    result = await service.get_file_notes("file-1")
    assert result[0].created_at == ""


# ---------------------------------------------------------------------------
# add_file_note
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_file_note_raises_not_found_when_file_missing(service):
    service.repo.get_file.return_value = None

    from exceptions.exceptions import NotFoundError

    with pytest.raises(NotFoundError, match="File not found"):
        await service.add_file_note("no-file", "content")


@pytest.mark.asyncio
async def test_add_file_note_raises_not_found_when_no_task_id(service):
    mock_file = MagicMock(id="f1", task_id=None)
    service.repo.get_file.return_value = mock_file

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_file
    service.db.execute = AsyncMock(return_value=mock_result)

    from exceptions.exceptions import NotFoundError

    with pytest.raises(NotFoundError, match="File has no associated task"):
        await service.add_file_note("f1", "content")


@pytest.mark.asyncio
async def test_add_file_note_raises_not_found_when_no_assignment(service):
    from exceptions.exceptions import NotFoundError

    mock_file = MagicMock(id="f1", task_id="task-1")
    service.repo.get_file.return_value = mock_file

    mock_file_with_task = MagicMock(id="f1", task_id="task-1")
    mock_task = MagicMock(id="task-1", assignment_id=None)
    service.db.get.return_value = mock_task

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_file_with_task
    service.db.execute = AsyncMock(return_value=mock_result)
    service.db.get.return_value = mock_task

    with pytest.raises(NotFoundError, match="File has no associated assignment"):
        await service.add_file_note("f1", "content")


@pytest.mark.asyncio
async def test_add_file_note_creates_and_returns_note(service):
    mock_file = MagicMock(id="f1", task_id="task-1")
    service.repo.get_file.return_value = mock_file

    mock_file_with_task = MagicMock(id="f1", task_id="task-1")
    mock_task = MagicMock(id="task-1", assignment_id="asgn-1")
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.return_value = mock_file_with_task
    service.db.execute = AsyncMock(return_value=mock_db_result)
    service.db.get = AsyncMock(return_value=mock_task)
    service.db.flush = AsyncMock()
    service.db.refresh = AsyncMock()

    created_note = MagicMock(
        id="note-1", file_id="f1", assignment_id="asgn-1",
        content="test note",
        created_at=MagicMock(isoformat=MagicMock(return_value="2024-01-01T00:00:00")),
    )
    service.db.refresh.return_value = created_note
    service.db.add = MagicMock()

    # Intercept the ReviewNote constructor via patch
    import files.service as svc_mod

    created_note_copy = MagicMock(
        id="note-1", file_id="f1", assignment_id="asgn-1",
        content="test note",
        created_at=MagicMock(isoformat=MagicMock(return_value="2024-01-01T00:00:00")),
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(svc_mod, "ReviewNote", MagicMock(return_value=created_note_copy))
        result = await service.add_file_note("f1", "test note")

    assert result.content == "test note"
    service.db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# unconfirm_file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unconfirm_file_raises_not_found_when_missing(service):
    service.repo.get_file.return_value = None

    from exceptions.exceptions import NotFoundError

    with pytest.raises(NotFoundError, match="File not found"):
        await service.unconfirm_file("no-file")


@pytest.mark.asyncio
async def test_unconfirm_file_sets_is_confirmed_false(service):
    mock_file = MagicMock(
        id="f1", filename="t.py", language="python",
        is_confirmed=True, max_similarity=0.9, created_at=None,
        task_id="task-1",
    )
    service.repo.get_file.return_value = mock_file
    service.db.commit = AsyncMock()
    service.db.refresh = AsyncMock()

    result = await service.unconfirm_file("f1")

    assert mock_file.is_confirmed is False
    service.db.commit.assert_called_once()
    service.db.refresh.assert_called_once_with(mock_file)
    assert result.is_confirmed is False


# ---------------------------------------------------------------------------
# move_file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_move_file_updates_task_id(service):
    target_task_id = uuid.uuid4()
    file_id = "file-123"
    expected_file = MagicMock(
        id=file_id, task_id=target_task_id, filename="a.py",
        language="python", is_confirmed=False, max_similarity=None,
        created_at=None,
    )
    service.repo.get_file.return_value = expected_file
    service.repo.move_file.return_value = expected_file

    mock_target_task = MagicMock(spec=PlagiarismTask)
    mock_target_task.status = "completed"
    service.db.get = AsyncMock(return_value=mock_target_task)

    result = await service.move_file(file_id, target_task_id)

    service.repo.get_file.assert_called_once_with(file_id)
    service.repo.move_file.assert_called_once_with(file_id, target_task_id)
    assert result.id == file_id


@pytest.mark.asyncio
async def test_move_file_raises_not_found_when_file_missing(service):
    service.repo.get_file.return_value = None

    from exceptions.exceptions import NotFoundError

    with pytest.raises(NotFoundError, match="File not found"):
        await service.move_file("missing-file", uuid.uuid4())


@pytest.mark.asyncio
async def test_move_file_raises_not_found_when_target_missing(service):
    mock_file = MagicMock(task_id="old-task")
    service.repo.get_file.return_value = mock_file
    service.db.get = AsyncMock(return_value=None)

    from exceptions.exceptions import NotFoundError

    with pytest.raises(NotFoundError, match="Target upload not found"):
        await service.move_file("file-1", uuid.uuid4())


@pytest.mark.asyncio
async def test_move_file_returns_correct_response_fields(service):
    target_id = uuid.uuid4()
    mock_file = MagicMock(
        id="file-1", filename="test.py", language="python",
        is_confirmed=False, max_similarity=0.95, created_at=None, task_id=target_id,
    )
    service.repo.get_file.return_value = mock_file
    service.repo.move_file.return_value = mock_file

    mock_target = MagicMock(spec=PlagiarismTask)
    mock_target.status = "completed"
    service.db.get = AsyncMock(return_value=mock_target)

    result = await service.move_file("file-1", target_id)

    assert str(result.id) == "file-1"
    assert result.filename == "test.py"
    assert result.language == "python"
    assert result.task_id == str(target_id)


@pytest.mark.asyncio
async def test_move_file_similarity_is_none_when_no_max(service):
    target_id = uuid.uuid4()
    mock_file = MagicMock(
        id="file-1", filename="a.py", language="python",
        is_confirmed=False, max_similarity=None, created_at=None, task_id=target_id,
    )
    service.repo.get_file.return_value = mock_file
    service.repo.move_file.return_value = mock_file

    mock_target = MagicMock(spec=PlagiarismTask)
    mock_target.status = "queued"
    service.db.get = AsyncMock(return_value=mock_target)

    result = await service.move_file("file-1", target_id)
    assert result.similarity is None


@pytest.mark.asyncio
async def test_move_file_raises_not_found_when_repo_move_returns_none(service):
    mock_file = MagicMock(task_id="old-task")
    service.repo.get_file.return_value = mock_file
    service.repo.move_file.return_value = None

    mock_target = MagicMock(spec=PlagiarismTask)
    service.db.get = AsyncMock(return_value=mock_target)

    from exceptions.exceptions import NotFoundError

    with pytest.raises(NotFoundError, match="File not found"):
        await service.move_file("file-1", uuid.uuid4())


@pytest.mark.asyncio
async def test_move_file_accepts_uuid_string_target_task_id(service):
    """target_task_id may be a UUID instance; repo.move_file should receive it."""
    target_uuid = uuid.uuid4()
    file_id = "file-123"

    dt_mock = MagicMock()
    dt_mock.isoformat.return_value = "2024-01-01T00:00:00"

    mock_file = MagicMock(
        id=file_id, task_id=target_uuid,
        created_at=dt_mock,
        filename="a.py", language="python",
        is_confirmed=False, max_similarity=None,
    )
    service.repo.get_file.return_value = mock_file
    service.repo.move_file.return_value = mock_file

    mock_target = MagicMock(spec=PlagiarismTask)
    mock_target.status = "completed"
    service.db.get = AsyncMock(return_value=mock_target)

    await service.move_file(file_id, target_uuid)
    _, actual_target = service.repo.move_file.call_args[0]
    assert actual_target == target_uuid


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_file_soft_deletes(service):
    service.repo.delete_file.return_value = True

    await service.delete_file("file-123")

    service.repo.delete_file.assert_called_once_with("file-123")


@pytest.mark.asyncio
async def test_delete_file_raises_not_found_when_missing(service):
    service.repo.delete_file.return_value = False

    from exceptions.exceptions import NotFoundError

    with pytest.raises(NotFoundError, match="File not found"):
        await service.delete_file("missing-file")


# ---------------------------------------------------------------------------
# exist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exist_returns_repo_result(service):
    service.repo.exist.return_value = True
    assert await service.exist("file-abc") is True
    service.repo.exist.assert_called_once_with("file-abc")

    service.repo.exist.return_value = False
    assert await service.exist("file-abc") is False


# ---------------------------------------------------------------------------
# get_all_file_info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_all_file_info_delegates_to_repo(service):
    from schemas.common import PaginatedResponse

    mock_info_page = MagicMock(spec=PaginatedResponse)
    service.repo.get_all_file_info.return_value = mock_info_page

    result = await service.get_all_file_info()
    service.repo.get_all_file_info.assert_called_once()
    assert result == mock_info_page


# ---------------------------------------------------------------------------
# delete_note
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_note_raises_not_found_when_missing(service):
    mock_exec = MagicMock()
    mock_exec.scalar_one_or_none.return_value = None
    service.db.execute = AsyncMock(return_value=mock_exec)

    from exceptions.exceptions import NotFoundError

    with pytest.raises(NotFoundError, match="Note not found"):
        await service.delete_note("no-note")


@pytest.mark.asyncio
async def test_delete_note_hard_deletes_and_commits(service):
    mock_note = MagicMock(id="n1")
    mock_exec = MagicMock()
    mock_exec.scalar_one_or_none.return_value = mock_note
    service.db.execute = AsyncMock(return_value=mock_exec)
    service.db.delete = AsyncMock()
    service.db.commit = AsyncMock()

    await service.delete_note("n1")

    service.db.execute.assert_called_once()
    service.db.delete.assert_called_once_with(mock_note)
    service.db.commit.assert_called_once()
