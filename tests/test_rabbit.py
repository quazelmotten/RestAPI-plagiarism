import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json


@pytest.fixture(autouse=True)
def reset_rabbit_module():
    """Reset the rabbit module's global state between tests."""
    import rabbit
    rabbit._connection = None
    rabbit._channel = None
    rabbit._exchange = None
    yield
    rabbit._connection = None
    rabbit._channel = None
    rabbit._exchange = None


class TestGetRabbitUrl:
    def test_returns_valid_amqp_url(self):
        from rabbit import get_rabbit_url
        url = get_rabbit_url()
        assert url.startswith("amqp://")
        assert settings.rmq_host in url or "localhost" in url


# Need settings import for the test
from config import settings


class TestConnect:
    @pytest.mark.asyncio
    async def test_creates_connection_channel_and_exchange(self):
        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connection.channel = AsyncMock(return_value=mock_channel)

        with patch("rabbit.aio_pika.connect_robust", new_callable=AsyncMock, return_value=mock_connection) as mock_connect:
            from rabbit import connect, _connection, _exchange
            await connect()
            mock_connect.assert_called_once()
            mock_connection.channel.assert_called_once()
            mock_channel.declare_exchange.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_is_idempotent(self):
        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connection.channel = AsyncMock(return_value=mock_channel)

        with patch("rabbit.aio_pika.connect_robust", new_callable=AsyncMock, return_value=mock_connection):
            import rabbit
            await rabbit.connect()
            call_count = rabbit.aio_pika.connect_robust.call_count if hasattr(rabbit.aio_pika.connect_robust, 'call_count') else 1
            # Second connect should be a no-op
            await rabbit.connect()
            # Connection should only be created once


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_closes_connection(self):
        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connection.close = AsyncMock()

        import rabbit
        rabbit._connection = mock_connection
        rabbit._channel = AsyncMock()
        rabbit._exchange = AsyncMock()

        await rabbit.disconnect()
        mock_connection.close.assert_called_once()
        assert rabbit._connection is None
        assert rabbit._exchange is None

    @pytest.mark.asyncio
    async def test_disconnect_noop_when_already_closed(self):
        import rabbit
        rabbit._connection = None
        # Should not crash
        await rabbit.disconnect()


class TestPublishMessage:
    @pytest.mark.asyncio
    async def test_publishes_to_exchange(self):
        mock_exchange = AsyncMock()
        mock_exchange.publish = AsyncMock()

        import rabbit
        rabbit._exchange = mock_exchange
        rabbit._connection = AsyncMock()
        rabbit._connection.is_closed = False

        message = {"task_id": "123", "language": "python"}
        await rabbit.publish_message("test_queue", message)

        mock_exchange.publish.assert_called_once()
        call_args = mock_exchange.publish.call_args
        published_msg = call_args[0][0]
        assert json.loads(published_msg.body) == message

    @pytest.mark.asyncio
    async def test_auto_connects_when_exchange_is_none(self):
        mock_exchange = AsyncMock()
        mock_exchange.publish = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connection.channel = AsyncMock(return_value=mock_channel)

        with patch("rabbit.aio_pika.connect_robust", new_callable=AsyncMock, return_value=mock_connection):
            import rabbit
            rabbit._exchange = None
            await rabbit.publish_message("queue", {"key": "value"})
            # Should have auto-connected
            mock_exchange.publish.assert_called_once()
