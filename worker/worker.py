import json
import logging
import sys
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING

from crud import update_plagiarism_task, save_similarity_result

from plagiarism.redis_analyzer import analyze_plagiarism_redis


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
        
        # Extract file paths and language from message
        files = message.get("files", [])
        language = message.get("language", "python")
        
        if len(files) < 2:
            log.error("Need at least 2 files for plagiarism check")
            update_plagiarism_task(
                task_id=task_id,
                status="failed",
                error="Need at least 2 files for plagiarism check"
            )
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
            return
        
        # Update status to processing
        update_plagiarism_task(
            task_id=task_id,
            status="processing"
        )
        
        # Process all pairs of files
        total_pairs = 0
        processed_pairs = 0
        
        # Generate all combinations of file pairs
        for file_a, file_b in combinations(files, 2):
            total_pairs += 1
            
            file_a_id = file_a.get("id")
            file_b_id = file_b.get("id")
            file_a_path = file_a.get("path")
            file_b_path = file_b.get("path")
            
            if not file_a_id or not file_b_id or not file_a_path or not file_b_path:
                log.warning(f"Skipping pair due to missing file info: {file_a}, {file_b}")
                continue
            
            try:
                log.info(f"Comparing {file_a.get('filename')} vs {file_b.get('filename')}")
                
                # Get file hashes for Redis lookup
                file_a_hash = file_a.get('hash')
                file_b_hash = file_b.get('hash')
                
                # Run plagiarism analysis using Redis
                token_similarity, ast_similarity, raw_matches = analyze_plagiarism_redis(
                    file_a_path, file_b_path, file_a_hash, file_b_hash, language
                )
                
                # Convert matches to JSON-serializable format
                matches_data = []
                for match in raw_matches:
                    matches_data.append({
                        "file_a_start_line": match["file1"]["start_line"],
                        "file_a_end_line": match["file1"]["end_line"],
                        "file_b_start_line": match["file2"]["start_line"],
                        "file_b_end_line": match["file2"]["end_line"]
                    })
                
                # Save result to database
                result_id = save_similarity_result(
                    task_id=task_id,
                    file_a_id=file_a_id,
                    file_b_id=file_b_id,
                    token_similarity=token_similarity,
                    ast_similarity=ast_similarity,
                    matches=matches_data
                )
                
                processed_pairs += 1
                log.info(f"Saved similarity result {result_id}: token_sim={token_similarity:.4f}, ast_sim={ast_similarity:.4f}")
                
            except Exception as e:
                log.error(f"Error comparing files {file_a_id} vs {file_b_id}: {e}")
                import traceback
                log.error(traceback.format_exc())
                # Save failed result
                save_similarity_result(
                    task_id=task_id,
                    file_a_id=file_a_id,
                    file_b_id=file_b_id,
                    error=str(e)
                )
        
        # Update status to completed
        update_plagiarism_task(
            task_id=task_id,
            status="completed",
            similarity=None,  # No longer storing here, results are in similarity_results table
            matches={"total_pairs": total_pairs, "processed_pairs": processed_pairs}
        )
        
        log.info(f"+++ Finished processing task {task_id}: {processed_pairs}/{total_pairs} pairs analyzed")
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
