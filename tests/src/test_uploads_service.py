"""
Unit tests for UploadService.delete_file pair-count reset.
"""

import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from shared.models import File as FileModel
from shared.models import PlagiarismTask

_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


@pytest.fixture
def upload_service(mock_db):
    from uploads.service import UploadService

    svc = UploadService(db=mock_db)
    svc.repo = MagicMock()
    return svc


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.mark.asyncio
async def test_delete_file_resets_pair_counts_when_task_becomes_empty(upload_service, mock_db):
    """After deleting the last file, the source task's counts are reset via FileRepository."""
    task_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())

    mock_file = MagicMock(spec=FileModel)
    mock_file.id = file_id
    mock_file.filename = "a.py"
    mock_file.file_path = "/tmp/a.py"
    mock_file.file_hash = "hash"
    mock_file.task_id = task_id

    mock_task = MagicMock(spec=PlagiarismTask)
    mock_task.assignment_id = None
    mock_task.total_pairs = 18447
    mock_task.processed_pairs = 18447
    mock_task.progress = 1.0

    # db.get is called three times: file, task_obj, then task again inside the reset helper
    mock_db.get = AsyncMock(side_effect=[mock_file, mock_task, mock_task])
    upload_service.repo.delete_file = AsyncMock(return_value=True)

    sim_delete = MagicMock()
    sim_delete.rowcount = 0
    count_result = MagicMock()
    count_result.scalar_one = MagicMock(return_value=0)
    mock_db.execute = AsyncMock(side_effect=[sim_delete, count_result])
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    fake_event = MagicMock()
    fake_event.id = uuid.uuid4()
    fake_event.assignment_id = None
    fake_event.task_id = task_id
    fake_event.event_type = "file_deleted"
    fake_event.event_metadata = {}
    fake_event.created_at = None

    with patch("uploads.service.FileEvent", return_value=fake_event):
        await upload_service.delete_file(file_id)

    assert mock_task.total_pairs == 0
    assert mock_task.processed_pairs == 0
    assert mock_task.progress == 0.0


@pytest.mark.asyncio
async def test_delete_file_returns_error_when_file_not_found(upload_service, mock_db):
    mock_db.get = AsyncMock(return_value=None)

    result = await upload_service.delete_file("missing-file")

    assert result["success"] is False
    assert result["error"] == "File not found"
