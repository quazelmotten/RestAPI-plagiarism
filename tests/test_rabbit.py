"""
Tests for RabbitMQ client (RabbitMQ class from clients.rabbit_client).
"""

import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "src"))

import json
from unittest.mock import AsyncMock, MagicMock, patch

from clients.rabbit_client import RabbitMQ, get_rabbit_url


class TestGetRabbitUrl:
    def test_returns_valid_amqp_url(self):
        from config import settings

        url = get_rabbit_url()
        assert url.startswith("amqp://")
        assert settings.rmq_host in url


class TestRabbitMQ:
    async def test_creates_connection_channel_and_exchange(self):
        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connection.channel = AsyncMock(return_value=mock_channel)

        with patch(
            "clients.rabbit_client.aio_pika.connect_robust",
            new_callable=AsyncMock,
            return_value=mock_connection,
        ):
            client = RabbitMQ()
            await client.connect()

            assert client._connection is mock_connection
            assert client._channel is mock_channel
            assert client._exchange is mock_exchange

    async def test_connect_is_idempotent(self):
        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connection.channel = AsyncMock(return_value=mock_channel)

        with patch(
            "clients.rabbit_client.aio_pika.connect_robust",
            new_callable=AsyncMock,
            return_value=mock_connection,
        ) as mock_connect:
            client = RabbitMQ()
            await client.connect()
            first_call_count = mock_connect.call_count
            await client.connect()
            assert mock_connect.call_count == first_call_count

    async def test_disconnect_closes_connection(self):
        client = RabbitMQ()
        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connection.close = AsyncMock()

        client._connection = mock_connection
        client._channel = AsyncMock()
        client._exchange = AsyncMock()

        await client.disconnect()
        mock_connection.close.assert_called_once()
        assert client._connection is None
        assert client._exchange is None

    async def test_disconnect_noop_when_already_closed(self):
        client = RabbitMQ()
        client._connection = None
        await client.disconnect()

    async def test_publishes_to_exchange(self):
        client = RabbitMQ()
        mock_exchange = AsyncMock()
        mock_exchange.publish = AsyncMock()

        client._exchange = mock_exchange
        client._connection = AsyncMock()
        client._connection.is_closed = False

        message = {"task_id": "123", "language": "python"}
        await client.publish_message("test_queue", message)

        mock_exchange.publish.assert_called_once()
        call_args = mock_exchange.publish.call_args
        published_msg = call_args[0][0]
        assert json.loads(published_msg.body) == message

    async def test_auto_connects_when_exchange_is_none(self):
        mock_exchange = AsyncMock()
        mock_exchange.publish = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connection.channel = AsyncMock(return_value=mock_channel)

        with patch(
            "clients.rabbit_client.aio_pika.connect_robust",
            new_callable=AsyncMock,
            return_value=mock_connection,
        ):
            client = RabbitMQ()
            client._exchange = None
            await client.publish_message("queue", {"key": "value"})
            mock_exchange.publish.assert_called_once()

    def test_is_connected_property(self):
        client = RabbitMQ()
        assert client.is_connected is False

        mock_conn = MagicMock()
        mock_conn.is_closed = False
        client._connection = mock_conn
        assert client.is_connected is True

        mock_conn.is_closed = True
        assert client.is_connected is False
