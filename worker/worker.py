import json
import logging
from typing import TYPE_CHECKING

from crud import update_plagiarism_task

if TYPE_CHECKING:
    from pika.adapters.blocking_connection import BlockingChannel
    from pika.spec import Basic, BasicProperties

from config import settings
from rabbit import get_connection, create_channel

DEFAULT_LOG_FORMAT = "%(module)s:%(lineno)d %(levelname)-6s - %(message)s"


def configure_logging(
    level: int = logging.INFO,
    pika_log_level: int = logging.WARNING,
) -> None:
    logging.basicConfig(
        level=level,
        datefmt="%Y-%m-%d %H:%M:%S",
        format=DEFAULT_LOG_FORMAT,
    )
    logging.getLogger("pika").setLevel(pika_log_level)


def process_new_message(
    ch: "BlockingChannel",
    method: "Basic.Deliver",
    properties: "BasicProperties",
    body: bytes,
):
    log.info("[ ] Start processing plagiarism task")

    try:
        message = json.loads(body.decode())
        task_id = message.get("task_id")
        
        if not task_id:
            log.error("No task_id in message")
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
            return

        log.info(f"Processing task {task_id}")
        
        # Update status to processing
        update_plagiarism_task(
            task_id=task_id,
            status="processing"
        )
        
        # TODO: Implement actual plagiarism detection logic here
        # For now, simulate analysis with placeholder results
        # similarity, matches = analyze_plagiarism(file1, file2, language)
        
        # Placeholder results - replace with actual analysis
        similarity = 0.85  # Example: 85% similar
        matches = {
            "similarity_score": similarity,
            "matching_blocks": [
                {"line1": 1, "line2": 1, "similarity": 1.0},
                {"line1": 5, "line2": 5, "similarity": 0.9}
            ],
            "total_lines_file1": 20,
            "total_lines_file2": 25
        }
        
        # Update status to completed with results
        update_plagiarism_task(
            task_id=task_id,
            status="completed",
            similarity=similarity,
            matches=matches
        )
        
        log.info(f"+++ Finished processing task {task_id} with similarity {similarity}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except Exception as e:
        log.error(f"Error processing message: {e}")
        # Update status to failed
        if task_id:
            update_plagiarism_task(
                task_id=task_id,
                status="failed",
                error=str(e)
            )
        ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)

    log.info("[X] Finished processing task")


def consume_messages(ch: "BlockingChannel") -> None:
    log.info("[X] Waiting for plagiarism tasks ...")
    ch.basic_consume(
        queue=settings.rmq_queue_name,
        on_message_callback=process_new_message,
    )
    ch.basic_qos(prefetch_count=1)
    ch.start_consuming()


if __name__ == "__main__":
    configure_logging(level=logging.INFO)
    log = logging.getLogger(__name__)
    
    max_retries = 30
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            log.info(f"Connecting to RabbitMQ (attempt {attempt + 1}/{max_retries})...")
            with get_connection() as connection:
                with connection.channel() as channel:
                    create_channel(channel=channel)
                    log.info("Successfully connected to RabbitMQ")
                    consume_messages(ch=channel)
        except Exception as e:
            log.warning(f"Failed to connect to RabbitMQ: {e}")
            if attempt < max_retries - 1:
                log.info(f"Retrying in {retry_delay} seconds...")
                import time
                time.sleep(retry_delay)
            else:
                log.error("Max retries reached. Exiting.")
                raise
