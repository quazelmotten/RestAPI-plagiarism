"""
Unit tests for MessageHandler.
Tests message parsing, validation, and delegation to TaskService.
"""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from worker.message_handler import MessageHandler


class TestMessageHandler:

    @pytest.fixture
    def mock_task_service(self):
        return MagicMock()

    @pytest.fixture
    def handler(self, mock_task_service):
        return MessageHandler(mock_task_service)

    @pytest.fixture
    def mock_channel(self):
        ch = MagicMock()
        ch.basic_ack = MagicMock()
        ch.basic_nack = MagicMock()
        return ch

    @pytest.fixture
    def mock_method(self):
        method = MagicMock()
        method.delivery_tag = 42
        return method

    @pytest.fixture
    def mock_properties(self):
        return MagicMock()

    def test_parses_json_body_and_calls_process_task(
        self, handler, mock_task_service, mock_channel, mock_method, mock_properties, caplog
    ):
        caplog.set_level(logging.INFO)
        body = json.dumps({
            "task_id": "task-abc",
            "files": [{"file_hash": "h1", "file_path": "/f1.py"}],
            "language": "python",
        }).encode()

        handler.on_message(mock_channel, mock_method, mock_properties, body)

        mock_task_service.process_task.assert_called_once_with(
            "task-abc",
            [{"file_hash": "h1", "file_path": "/f1.py"}],
            "python",
            assignment_id=None,
            user_id=None,
        )

    def test_passes_assignment_id_through(
        self, handler, mock_task_service, mock_channel, mock_method, mock_properties
    ):
        body = json.dumps({
            "task_id": "task-abc",
            "files": [{"file_hash": "h1"}],
            "language": "python",
            "assignment_id": "assn-123",
        }).encode()

        handler.on_message(mock_channel, mock_method, mock_properties, body)

        mock_task_service.process_task.assert_called_once_with(
            "task-abc", [{"file_hash": "h1"}], "python", assignment_id="assn-123", user_id=None
        )

    def test_defaults_language_to_python_when_missing(
        self, handler, mock_task_service, mock_channel, mock_method, mock_properties
    ):
        body = json.dumps({
            "task_id": "task-abc",
            "files": [{"file_hash": "h1"}],
        }).encode()

        handler.on_message(mock_channel, mock_method, mock_properties, body)

        mock_task_service.process_task.assert_called_once_with(
            "task-abc", [{"file_hash": "h1"}], "python", assignment_id=None, user_id=None
        )

    def test_raises_value_error_when_task_id_missing(
        self, handler, mock_task_service, mock_channel, mock_method, mock_properties
    ):
        body = json.dumps({"files": [{"file_hash": "h1"}]}).encode()

        with pytest.raises(ValueError, match="Missing task_id"):
            handler.on_message(mock_channel, mock_method, mock_properties, body)

        # The task_service should never be called
        mock_task_service.process_task.assert_not_called()

    def test_raises_value_error_when_files_empty(
        self, handler, mock_task_service, mock_channel, mock_method, mock_properties
    ):
        body = json.dumps({"task_id": "t1", "files": []}).encode()

        with pytest.raises(ValueError, match="Need at least 1 file"):
            handler.on_message(mock_channel, mock_method, mock_properties, body)

        mock_task_service.process_task.assert_not_called()

    def test_raises_value_error_when_files_not_list(
        self, handler, mock_task_service, mock_channel, mock_method, mock_properties
    ):
        body = json.dumps({"task_id": "t1", "files": "not-a-list"}).encode()

        with pytest.raises(ValueError, match="Need at least 1 file"):
            handler.on_message(mock_channel, mock_method, mock_properties, body)

    def test_raises_on_invalid_json(
        self, handler, mock_task_service, mock_channel, mock_method, mock_properties, caplog
    ):
        caplog.set_level(logging.ERROR)
        body = b"{not-json!"

        with pytest.raises(json.JSONDecodeError):
            handler.on_message(mock_channel, mock_method, mock_properties, body)

        mock_task_service.process_task.assert_not_called()
        assert "Invalid JSON" in caplog.text

    def test_re_raises_service_exception(
        self, handler, mock_task_service, mock_channel, mock_method, mock_properties, caplog
    ):
        caplog.set_level(logging.ERROR)
        mock_task_service.process_task.side_effect = RuntimeError("boom")
        body = json.dumps({"task_id": "t1", "files": [{"file_hash": "h1"}]}).encode()

        with pytest.raises(RuntimeError, match="boom"):
            handler.on_message(mock_channel, mock_method, mock_properties, body)

        assert "Error processing message" in caplog.text

    def test_concurrent_messages_are_independent(
        self, handler, mock_task_service, mock_channel, mock_method, mock_properties
    ):
        body_a = json.dumps({"task_id": "t-A", "files": [{"file_hash": "ha"}]}).encode()
        body_b = json.dumps({"task_id": "t-B", "files": [{"file_hash": "hb"}]}).encode()

        # Call handler twice with different task ids — mocks track calls independently
        handler.on_message(mock_channel, mock_method, mock_properties, body_a)
        handler.on_message(mock_channel, mock_method, mock_properties, body_b)

        # Both calls forwarded with correct task identifiers
        assert mock_task_service.process_task.call_count == 2
        call_args = [c.args[0] for c in mock_task_service.process_task.call_args_list]
        assert "t-A" in call_args
        assert "t-B" in call_args

    def test_empty_body_json_decode_raises(
        self, handler, mock_task_service, mock_channel, mock_method, mock_properties
    ):
        with pytest.raises(json.JSONDecodeError):
            handler.on_message(mock_channel, mock_method, mock_properties, b"")

    def test_missing_task_id_logs_and_raises(
        self, handler, mock_task_service, mock_channel, mock_method, mock_properties, caplog
    ):
        caplog.set_level(logging.INFO)
        body = json.dumps({"files": [{"file_hash": "h1"}]}).encode()

        with pytest.raises(ValueError):
            handler.on_message(mock_channel, mock_method, mock_properties, body)

        assert "Received message" in caplog.text  # "Received message, processing..." logged before failure
