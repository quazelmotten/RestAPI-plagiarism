"""
Unit tests for AsyncWorker.
Tests worker lifecycle: executor dispatch, message thread routing, ack/nack, shutdown, reconnect.
"""

import functools
import logging
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import ANY, MagicMock, patch

import pytest
import pika
from worker.worker_lifecycle import AsyncWorker


class TestAsyncWorker:
    """Test AsyncWorker lifecycle operations."""

    @pytest.fixture
    def mock_message_handler(self):
        return MagicMock()

    @pytest.fixture
    def mock_executor(self):
        exec_mock = MagicMock(spec=ThreadPoolExecutor)
        future_mock = MagicMock()
        exec_mock.submit.return_value = future_mock
        return exec_mock

    @pytest.fixture
    def worker(self, mock_message_handler):
        return AsyncWorker(message_handler=mock_message_handler, worker_concurrency=4)

    def test_on_message_wrapper_submits_to_executor(self, worker, mock_message_handler, mock_executor):
        worker.executor = mock_executor
        channel = MagicMock()
        method = MagicMock()
        properties = MagicMock()
        body = b"test"

        with patch.object(worker, "_process_message_thread") as mock_process:
            worker._on_message_wrapper(channel, method, properties, body)

        # patch.object replaces the bound method with a MagicMock, so use ANY for arg 0
        mock_executor.submit.assert_called_once_with(
            ANY, channel, method, properties, body
        )

    def test_on_message_wrapper_errors_when_no_executor(
        self, worker, mock_message_handler, caplog
    ):
        caplog.set_level(logging.ERROR)
        worker.executor = None
        channel = MagicMock()
        method = MagicMock()
        properties = MagicMock()
        body = b"test"

        worker._on_message_wrapper(channel, method, properties, body)
        assert "Thread pool executor not initialized" in caplog.text

    def test_process_message_thread_acks_on_success(
        self, worker, mock_message_handler, mock_executor
    ):
        channel = MagicMock()
        channel.is_open = True
        method = MagicMock()
        method.delivery_tag = 7
        properties = MagicMock()
        body = b"test"

        mock_connection = MagicMock()
        mock_connection.is_closed = False
        worker._connection = mock_connection

        mock_executor.return_value = MagicMock()

        # No exception from handler
        worker._process_message_thread(channel, method, properties, body)

        # ack added via ioloop callback — verify add_callback_threadsafe was called
        channel.basic_ack.assert_not_called()  # not called directly
        mock_connection.ioloop.add_callback_threadsafe.assert_called_once()
        cb = mock_connection.ioloop.add_callback_threadsafe.call_args[0][0]
        # The callback is a functools.partial wrapping basic_ack
        cb()

    def test_process_message_thread_nacks_on_failure(
        self, worker, mock_message_handler, mock_executor
    ):
        channel = MagicMock()
        channel.is_open = True
        method = MagicMock()
        method.delivery_tag = 7
        properties = MagicMock()
        body = b"test"

        mock_message_handler.on_message.side_effect = RuntimeError("fail")
        mock_connection = MagicMock()
        mock_connection.is_closed = False
        worker._connection = mock_connection

        worker._process_message_thread(channel, method, properties, body)

        # nack added via ioloop callback
        mock_connection.ioloop.add_callback_threadsafe.assert_called_once()
        cb = mock_connection.ioloop.add_callback_threadsafe.call_args[0][0]
        cb()

    def test_process_message_thread_no_ack_when_connection_closed(
        self, worker, mock_message_handler
    ):
        channel = MagicMock()
        method = MagicMock()
        properties = MagicMock()
        body = b"test"

        mock_connection = MagicMock()
        mock_connection.is_closed = True
        worker._connection = mock_connection

        worker._process_message_thread(channel, method, properties, body)
        # No ioloop callback scheduled because connection is closed
        mock_connection.ioloop.add_callback_threadsafe.assert_not_called()

    def test_shutdown_sets_flags(self, worker):
        mock_channel = MagicMock()
        mock_channel.is_open = True
        worker._channel = mock_channel
        worker._consuming = True

        worker.shutdown()  # calls stop() → _stop_consuming() → basic_cancel

        assert worker._closing is True
        assert worker._stopping is True
        mock_channel.basic_cancel.assert_called_once()  # shutdown → stop → _stop_consuming

    def test_stop_cancels_consumption(self, worker):
        mock_channel = MagicMock()
        mock_channel.is_open = True
        worker._channel = mock_channel
        worker._consuming = True

        worker.stop()

        assert worker._stopping is True
        assert worker._closing is True
        mock_channel.basic_cancel.assert_called_once()

    def test_stop_closes_connection_when_no_channel(self, worker):
        mock_connection = MagicMock()
        mock_connection.is_closing = False
        mock_connection.is_closed = False
        worker._connection = mock_connection
        worker._channel = None

        worker.stop()

        assert worker._stopping is True
        mock_connection.close.assert_called_once()

    def test_reconnect_delay_increments(self, worker):
        assert worker._get_reconnect_delay() == 0
        worker._should_reconnect = True
        assert worker._get_reconnect_delay() == 1
        worker._should_reconnect = True
        assert worker._get_reconnect_delay() == 2

    def test_reconnect_delay_caps_at_30(self, worker):
        worker._should_reconnect = True
        for _ in range(35):
            delay = worker._get_reconnect_delay()
            assert delay <= 30

    def test_on_connection_closed_triggers_reconnect(self, worker):
        mock_connection = MagicMock()
        worker._connection = mock_connection
        worker._closing = False

        worker._on_connection_closed(mock_connection, "error")
        assert worker._should_reconnect is True

    def test_on_connection_closed_does_not_reconnect_when_closing(self, worker):
        mock_connection = MagicMock()
        worker._connection = mock_connection
        worker._closing = True

        worker._on_connection_closed(mock_connection, "error")
        assert worker._should_reconnect is False

    @patch("worker.worker_lifecycle.get_redis_client")
    @patch("worker.worker_lifecycle.get_analysis_executor")
    def test_initialize_sets_up_executor_and_checks_redis(
        self, mock_get_executor, mock_get_redis, worker, mock_message_handler
    ):
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_get_redis.return_value = mock_redis
        mock_executor = MagicMock()
        mock_get_executor.return_value = mock_executor

        result = worker.initialize()

        assert result is True
        mock_redis.ping.assert_called_once()
        assert worker.executor is mock_executor

    @patch("worker.worker_lifecycle.get_redis_client")
    def test_initialize_continues_if_redis_unavailable(self, mock_get_redis, worker):
        mock_get_redis.side_effect = Exception("Redis down")
        mock_executor = MagicMock()

        with patch("worker.worker_lifecycle.get_analysis_executor", return_value=mock_executor):
            result = worker.initialize()

        assert result is True
        assert worker.executor is mock_executor

    def test_start_consuming_sets_consuming_flag(self, worker):
        mock_channel = MagicMock()
        mock_channel.basic_consume.return_value = "consumer-tag-1"
        worker._channel = mock_channel

        worker._start_consuming()

        assert worker._consuming is True
        assert worker._consumer_tag == "consumer-tag-1"
        mock_channel.basic_consume.assert_called_once()

    def test_on_consumer_cancelled_closes_channel(self, worker):
        mock_channel = MagicMock()
        worker._channel = mock_channel
        worker._consuming = True

        worker._on_consumer_cancelled(MagicMock())

        assert worker._consuming is False
        mock_channel.close.assert_called_once()

    def test_parse_log_level_defaults_info(self):
        w = AsyncWorker(message_handler=MagicMock())
        assert w._parse_log_level("INFO") == logging.INFO

    def test_parse_log_level_case_insensitive(self):
        w = AsyncWorker(message_handler=MagicMock())
        assert w._parse_log_level("debug") == logging.DEBUG

    def test_index_error_in_process_message_thread_schedules_nack(
        self, worker, mock_message_handler
    ):
        """Regression: IndexError (or any unhandled exception) must be caught by
        _process_message_thread and result in a basic_nack — never a silent swallow."""
        mock_channel = MagicMock()
        mock_channel.is_open = True
        mock_message_handler.on_message.side_effect = IndexError("list index out of range")

        mock_connection = MagicMock()
        mock_connection.is_closed = False
        mock_connection.ioloop = MagicMock()
        worker._connection = mock_connection

        worker._process_message_thread(mock_channel, MagicMock(), MagicMock(), b"test")

        # Exception must NOT bubble up — it's caught inside the thread function
        # Instead, a nack callback is scheduled on the IOLoop
        mock_connection.ioloop.add_callback_threadsafe.assert_called_once()
        cb = mock_connection.ioloop.add_callback_threadsafe.call_args[0][0]
        cb()
        mock_channel.basic_nack.assert_called_once()
