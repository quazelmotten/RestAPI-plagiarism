"""
Tests for schema models - importing directly from domain modules.
"""

import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "src"))

from files.schemas import FileContentResponse, FileResponse, FileUploadInfo
from results.schemas import ResultItem, ResultsListResponse, TaskResultsResponse
from tasks.schemas import (
    TaskCreate,
    TaskCreateResponse,
    TaskListResponse,
    TaskProgress,
    TaskResponse,
)


class TestTaskSchemas:
    def test_task_progress_defaults(self):
        """Test TaskProgress default values."""
        progress = TaskProgress()
        assert progress.completed == 0
        assert progress.total == 0
        assert progress.percentage == 0.0
        assert progress.display == "0/0"

    def test_task_progress_from_dict(self):
        """Test TaskProgress from dict."""
        progress = TaskProgress(completed=5, total=10, percentage=50.0, display="5/10")
        assert progress.completed == 5
        assert progress.total == 10
        assert progress.percentage == 50.0
        assert progress.display == "5/10"

    def test_task_create_defaults(self):
        """Test TaskCreate default values."""
        task = TaskCreate()
        assert task.language == "python"

    def test_task_create_with_language(self):
        """Test TaskCreate with custom language."""
        task = TaskCreate(language="javascript")
        assert task.language == "javascript"

    def test_task_response_from_attributes(self):
        """Test TaskResponse from attributes."""
        task = TaskResponse(
            task_id="123",
            status="queued",
            progress=TaskProgress(completed=0, total=0, percentage=0.0, display="0/0"),
        )
        assert task.task_id == "123"
        assert task.status == "queued"

    def test_task_list_response(self):
        """Test TaskListResponse."""
        task = TaskListResponse(
            task_id="123",
            status="completed",
            similarity=0.85,
            progress=TaskProgress(completed=10, total=10, percentage=100.0, display="10/10"),
        )
        assert task.task_id == "123"
        assert task.similarity == 0.85

    def test_task_create_response(self):
        """Test TaskCreateResponse."""
        response = TaskCreateResponse(task_id="abc-123", status="queued", files_count=3)
        assert response.task_id == "abc-123"
        assert response.status == "queued"
        assert response.files_count == 3


class TestFileSchemas:
    def test_file_upload_info(self):
        """Test FileUploadInfo."""
        info = FileUploadInfo(
            id="file-123", path="s3://bucket/file.py", hash="abc123", filename="test.py"
        )
        assert info.id == "file-123"
        assert info.filename == "test.py"

    def test_file_response(self):
        """Test FileResponse."""
        file = FileResponse(
            id="file-123",
            filename="test.py",
            language="python",
            task_id="task-123",
            status="completed",
            similarity=0.75,
        )
        assert file.id == "file-123"
        assert file.similarity == 0.75

    def test_file_content_response(self):
        """Test FileContentResponse."""
        content = FileContentResponse(
            id="file-123",
            filename="test.py",
            content="print('hello')",
            language="python",
            file_path="s3://bucket/test.py",
        )
        assert content.id == "file-123"
        assert "hello" in content.content


class TestResultSchemas:
    def test_result_item(self):
        """Test ResultItem."""
        item = ResultItem(
            file_a={"id": "file-1", "filename": "a.py"},
            file_b={"id": "file-2", "filename": "b.py"},
            ast_similarity=0.85,
            matches=[
                {
                    "file1": {"start_line": 1, "start_col": 0, "end_line": 5, "end_col": 10},
                    "file2": {"start_line": 1, "start_col": 0, "end_line": 5, "end_col": 10},
                    "kgram_count": 3,
                }
            ],
        )
        assert item.ast_similarity == 0.85
        assert item.file_a.filename == "a.py"

    def test_results_list_response(self):
        """Test ResultsListResponse."""
        response = ResultsListResponse(
            id="result-123",
            file_a={"id": "file-1", "filename": "a.py"},
            file_b={"id": "file-2", "filename": "b.py"},
            ast_similarity=0.85,
            task_id="task-123",
            task_progress={"status": "completed", "total_pairs": 10},
        )
        assert response.task_id == "task-123"
        assert response.task_progress["status"] == "completed"

    def test_task_results_response(self):
        """Test TaskResultsResponse."""
        response = TaskResultsResponse(
            task_id="task-123",
            status="completed",
            progress={"completed": 10, "total": 10, "percentage": 100.0, "display": "10/10"},
            total_pairs=10,
            files=[{"id": "file-1", "filename": "a.py"}],
            results=[],
        )
        assert response.task_id == "task-123"
        assert len(response.files) == 1
