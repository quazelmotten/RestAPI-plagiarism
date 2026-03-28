"""
Worker lifecycle management using Pika's async SelectConnection.
Handles RabbitMQ connection setup, teardown, and message consumption with auto-reconnect.
"""

import functools
import logging
import signal
import time
from concurrent.futures import ThreadPoolExecutor

import pika

from worker.config import settings
from worker.dependencies import get_analysis_executor, get_redis_client

log = logging.getLogger(__name__)

DEFAULT_LOG_FORMAT = "%(module)s:%(lineno)d %(levelname)-6s - %(message)s"


class AsyncWorker:
    """Asynchronous worker using Pika SelectConnection with auto-reconnect."""

    def __init__(
        self, message_handler, worker_concurrency: int | None = None, log_level: int | None = None
    ):
        self.message_handler = message_handler
        self.worker_concurrency = worker_concurrency or getattr(settings, "worker_concurrency", 4)
        self.log_level = log_level or self._parse_log_level(getattr(settings, "log_level", "INFO"))

        self._connection: pika.SelectConnection | None = None
        self._channel: pika.channel.Channel | None = None
        self._consumer_tag: str | None = None
        self._closing = False
        self._stopping = False
        self._consuming = False
        self._should_reconnect = False
        self._reconnect_delay = 0

        self.executor: ThreadPoolExecutor | None = None

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _parse_log_level(self, level_str: str) -> int:
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        return levels.get(level_str.upper(), logging.INFO)

    def _handle_signal(self, signum, frame):
        log.info("Shutdown signal received")
        self._closing = True
        self.stop()

    def configure_logging(self) -> None:
        logging.basicConfig(
            level=self.log_level,
            datefmt="%Y-%m-%d %H:%M:%S",
            format=DEFAULT_LOG_FORMAT,
        )
        logging.getLogger("pika").setLevel(logging.CRITICAL)
        log.info(f"Logging configured at {logging.getLevelName(self.log_level)}")

    def initialize(self) -> bool:
        self.configure_logging()

        log.info("Connecting to Redis cache...")
        try:
            client = get_redis_client()
            client.ping()
            log.info("Redis cache connected")
        except Exception as e:
            log.warning(f"Redis cache unavailable: {e}. Caching disabled.")

        self.executor = get_analysis_executor()
        log.info(f"Thread pool shared ({self.worker_concurrency} workers)")
        return True

    def run(self) -> None:
        try:
            if not self.initialize():
                log.error("Failed to initialize worker")
                return
            self._run_loop()
        finally:
            self.shutdown()

    def _run_loop(self) -> None:
        while not self._closing:
            try:
                log.info("Connecting to RabbitMQ...")
                self._connection = self._connect()
                self._connection.ioloop.start()
            except KeyboardInterrupt:
                log.info("Keyboard interrupt received")
                self._closing = True
                break
            except Exception as e:
                log.error(f"Unexpected error in connection loop: {e}")

            if not self._closing:
                delay = self._get_reconnect_delay()
                log.info(f"Reconnecting in {delay} seconds...")
                time.sleep(delay)

    def _connect(self) -> pika.SelectConnection:
        parameters = pika.ConnectionParameters(
            host=settings.rmq_host,
            port=settings.rmq_port,
            credentials=pika.PlainCredentials(
                username=settings.rmq_user, password=settings.rmq_pass
            ),
            heartbeat=600,
            blocked_connection_timeout=300,
        )
        log.info(f"Connecting to {settings.rmq_host}:{settings.rmq_port}")
        return pika.SelectConnection(
            parameters=parameters,
            on_open_callback=self._on_connection_open,
            on_open_error_callback=self._on_connection_open_error,
            on_close_callback=self._on_connection_closed,
        )

    def _on_connection_open(self, connection):
        log.info("Connection opened")
        self._reconnect_delay = 0
        self._should_reconnect = False
        self._open_channel()

    def _on_connection_open_error(self, connection, err):
        log.error(f"Connection open failed: {err}")
        self._reconnect_delay = min(self._reconnect_delay + 1, 30)
        self._stop_ioloop()

    def _on_connection_closed(self, connection, reason):
        log.info(f"Connection closed: {reason}")
        self._channel = None
        self._consumer_tag = None
        self._consuming = False

        if self._closing:
            self._stop_ioloop()
        else:
            log.warning("Connection lost, will reconnect")
            self._should_reconnect = True
            self._stop_ioloop()

    def _open_channel(self):
        log.info("Opening channel...")
        self._connection.channel(on_open_callback=self._on_channel_open)

    def _on_channel_open(self, channel):
        log.info("Channel opened")
        self._channel = channel
        self._setup_channel()

    def _on_channel_closed(self, channel, reason):
        log.warning(f"Channel closed: {reason}")
        self._channel = None
        if self._closing:
            return
        self._should_reconnect = True
        if self._connection and not self._connection.is_closed:
            try:
                self._connection.close()
            except Exception:
                self._stop_ioloop()
        else:
            self._stop_ioloop()

    def _setup_channel(self):
        if not self._channel:
            return
        self._channel.exchange_declare(
            exchange=settings.rmq_queue_exchange,
            exchange_type="direct",
            durable=True,
            callback=functools.partial(
                self._on_exchange_declareok, exchange=settings.rmq_queue_exchange
            ),
        )

    def _on_exchange_declareok(self, _unused_frame, exchange: str):
        log.info(f"Exchange declared: {exchange}")
        self._channel.queue_declare(
            queue=settings.rmq_queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": settings.rmq_queue_dead_letter_exchange,
                "x-dead-letter-routing-key": settings.rmq_queue_routing_key_dead_letter,
            },
            callback=self._on_queue_declareok,
        )

    def _on_queue_declareok(self, _unused_frame):
        log.info(f"Queue declared: {settings.rmq_queue_name}")
        self._channel.queue_bind(
            queue=settings.rmq_queue_name,
            exchange=settings.rmq_queue_exchange,
            routing_key=settings.rmq_queue_routing_key,
            callback=self._on_bindok,
        )
        self._channel.exchange_declare(
            exchange=settings.rmq_queue_dead_letter_exchange,
            exchange_type="direct",
            durable=True,
            callback=functools.partial(
                self._on_dlx_exchange_declareok, exchange=settings.rmq_queue_dead_letter_exchange
            ),
        )

    def _on_dlx_exchange_declareok(self, _unused_frame, exchange: str):
        log.info(f"DLX exchange declared: {exchange}")
        self._channel.queue_declare(
            queue=settings.rmq_queue_dead_letter_name,
            durable=True,
            callback=self._on_dlx_queue_declareok,
        )

    def _on_dlx_queue_declareok(self, _unused_frame):
        log.info(f"DLX queue declared: {settings.rmq_queue_dead_letter_name}")
        self._channel.queue_bind(
            queue=settings.rmq_queue_dead_letter_name,
            exchange=settings.rmq_queue_dead_letter_exchange,
            routing_key=settings.rmq_queue_routing_key_dead_letter,
            callback=lambda _: log.info("DLQ bound"),
        )
        self._set_qos()

    def _on_bindok(self, _unused_frame):
        log.info("Queue bound")
        self._set_qos()

    def _set_qos(self):
        if not self._channel:
            return
        self._channel.basic_qos(
            prefetch_count=getattr(settings, "worker_prefetch_count", 1),
            callback=self._on_basic_qos_ok,
        )

    def _on_basic_qos_ok(self, _unused_frame):
        log.info(f"QoS set to {getattr(settings, 'worker_prefetch_count', 1)}")
        self._start_consuming()

    def _start_consuming(self):
        log.info("Starting to consume")
        self._channel.add_on_close_callback(self._on_channel_closed)
        self._channel.add_on_cancel_callback(self._on_consumer_cancelled)
        self._consumer_tag = self._channel.basic_consume(
            queue=settings.rmq_queue_name, on_message_callback=self._on_message_wrapper
        )
        self._consuming = True
        log.info(f"Consumer started with tag: {self._consumer_tag}")

    def _on_consumer_cancelled(self, method_frame):
        log.info(f"Consumer cancelled: {method_frame}")
        self._consuming = False
        if self._channel:
            self._channel.close()

    def _on_message_wrapper(self, channel, method, properties, body):
        """Submit message processing to thread pool."""
        if self.executor:
            self.executor.submit(self._process_message_thread, channel, method, properties, body)
        else:
            log.error("Thread pool executor not initialized!")

    def _process_message_thread(self, channel, method, properties, body):
        """Process message and ack/nack on the IOLoop thread."""
        try:
            self.message_handler.on_message(channel, method, properties, body)
            if self._connection and not self._connection.is_closed:
                self._connection.ioloop.add_callback_threadsafe(
                    functools.partial(channel.basic_ack, method.delivery_tag)
                )
        except Exception as e:
            log.error(f"Error processing message: {e}")
            if channel.is_open and self._connection and not self._connection.is_closed:
                self._connection.ioloop.add_callback_threadsafe(
                    functools.partial(channel.basic_nack, method.delivery_tag, False)
                )

    def stop(self):
        if self._stopping:
            return
        log.info("Stopping consumer...")
        self._stopping = True
        self._closing = True

        if self._channel and self._consuming:
            self._stop_consuming()
        elif (
            self._connection and not self._connection.is_closing and not self._connection.is_closed
        ):
            try:
                self._connection.close()
            except Exception:
                self._stop_ioloop()

    def _stop_consuming(self):
        if not self._channel or not self._consuming:
            return
        log.info("Sending Basic.Cancel")
        self._channel.basic_cancel(consumer_tag=self._consumer_tag, callback=self._on_cancelok)

    def _on_cancelok(self, _unused_frame):
        log.info("Consumer cancelled successfully")
        self._consuming = False
        if self._channel:
            self._channel.close()
            self._channel = None

    def _stop_ioloop(self):
        if self._connection and not self._connection.is_closed:
            try:
                self._connection.ioloop.stop()
            except Exception:
                log.error("Failed to stop IOLoop", exc_info=True)

    def shutdown(self):
        log.info("Shutting down worker...")
        self.stop()

        if self._connection:
            while not self._connection.is_closed and not self._closing:
                time.sleep(0.1)

        log.info("Worker shutdown complete")

    def _get_reconnect_delay(self) -> int:
        if self._should_reconnect:
            self._reconnect_delay = min(self._reconnect_delay + 1, 30)
        return self._reconnect_delay
