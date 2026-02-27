import functools
import json
import logging
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

from crud import update_plagiarism_task, save_similarity_result, get_all_files

from redis_cache import cache, connect_cache
from inverted_index import inverted_index


if TYPE_CHECKING:
    from pika.adapters.blocking_connection import BlockingChannel
    from pika.spec import Basic, BasicProperties
    import pika

from src.config import settings
from rabbit import get_connection, create_channel

DEFAULT_LOG_FORMAT = "%(module)s:%(lineno)d %(levelname)-6s - %(message)s"

CLI_PATH = Path(__file__).parent.parent / "src" / "plagiarism" / "cli.py"

connection: Optional["pika.BlockingConnection"] = None
executor: Optional[ThreadPoolExecutor] = None
log = logging.getLogger(__name__)


def run_cli_analyze(file1_path: str, file2_path: str, language: str = "python") -> Dict:
    """
    Run plagiarism analysis via CLI subprocess.
    DEPRECATED: Use Redis-based similarity calculation instead.
    Kept for backwards compatibility and debugging.
    Returns parsed JSON result.
    """
    cmd = [
        sys.executable,
        str(CLI_PATH),
        "analyze",
        file1_path,
        file2_path,
        "--language", language
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"CLI error: {result.stderr}")
    
    return json.loads(result.stdout)


def run_cli_fingerprint(file_path: str, language: str = "python") -> Dict:
    """
    Run fingerprint extraction via CLI subprocess.
    Returns parsed JSON result with fingerprints and ast_hashes.
    """
    cmd = [
        sys.executable,
        str(CLI_PATH),
        "fingerprint",
        file_path,
        "--language", language
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"CLI error: {result.stderr}")
    
    return json.loads(result.stdout)


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


def ack_message(channel: "BlockingChannel", delivery_tag: int) -> None:
    """
    Acknowledge a message from RabbitMQ.
    Must be called from the connection's thread via add_callback_threadsafe.
    """
    if channel.is_open:
        channel.basic_ack(delivery_tag=delivery_tag)
    else:
        log.warning(f"Channel closed, cannot ack message {delivery_tag}")


def reject_message(channel: "BlockingChannel", delivery_tag: int, requeue: bool = False) -> None:
    """
    Reject a message from RabbitMQ.
    Must be called from the connection's thread via add_callback_threadsafe.
    """
    if channel.is_open:
        channel.basic_reject(delivery_tag=delivery_tag, requeue=requeue)
    else:
        log.warning(f"Channel closed, cannot reject message {delivery_tag}")


def process_task(
    body: bytes,
    channel: "BlockingChannel",
    delivery_tag: int,
) -> None:
    """
    Process a plagiarism detection task in a worker thread.
    
    Args:
        body: Raw message body
        channel: RabbitMQ channel (for ack/reject via callback)
        delivery_tag: Message delivery tag for ack/reject
    """
    task_id = None

    try:
        message = json.loads(body.decode())
        task_id = message.get("task_id")
        
        if not task_id:
            log.error("No task_id in message")
            if connection:
                connection.add_callback_threadsafe(
                    functools.partial(reject_message, channel, delivery_tag, False)
                )
            return

        log.info(f"[Task {task_id}] Start processing plagiarism task")
        
        files = message.get("files", [])
        language = message.get("language", "python")
        
        if len(files) < 2:
            log.error(f"[Task {task_id}] Need at least 2 files for plagiarism check")
            update_plagiarism_task(
                task_id=task_id,
                status="failed",
                error="Need at least 2 files for plagiarism check"
            )
            if connection:
                connection.add_callback_threadsafe(
                    functools.partial(reject_message, channel, delivery_tag, False)
                )
            return
        
        update_plagiarism_task(
            task_id=task_id,
            status="processing"
        )

        log.info(f"[Task {task_id}] Fetching existing files from other tasks...")
        existing_files = get_all_files(exclude_task_id=task_id)
        log.info(f"[Task {task_id}] Found {len(existing_files)} existing files from other tasks")
        
        log.info(f"[Task {task_id}] Indexing fingerprints for new files...")
        for file_info in files:
            file_hash = file_info.get('hash') or file_info.get('file_hash')
            file_path = file_info.get('path') or file_info.get('file_path')
            
            if not file_hash or not file_path:
                continue
                
            try:
                if inverted_index.get_file_fingerprints(file_hash, language):
                    log.debug(f"[Task {task_id}] File {file_info.get('filename')} already in inverted index")
                    continue
                
                fp_result = run_cli_fingerprint(file_path, language)
                fingerprints = fp_result.get("fingerprints", [])
                ast_hashes = fp_result.get("ast_hashes", [])
                
                fingerprints_for_index = [
                    {
                        "hash": fp["hash"],
                        "start": tuple(fp["start"]),
                        "end": tuple(fp["end"])
                    }
                    for fp in fingerprints
                ]
                
                inverted_index.add_file_fingerprints(file_hash, fingerprints_for_index, language)
                log.debug(f"[Task {task_id}] Indexed {len(fingerprints)} fingerprints for {file_info.get('filename')}")
                
                tokens_serializable = fp_result.get("tokens", [])
                tokens = [(t["type"], tuple(t["start"]), tuple(t["end"])) for t in tokens_serializable]
                cache.cache_fingerprints(file_hash, fingerprints_for_index, ast_hashes, tokens)
                
            except Exception as e:
                log.warning(f"[Task {task_id}] Failed to index file {file_info.get('filename')}: {e}")
        
        log.info(f"[Task {task_id}] Finished indexing fingerprints")

        log.info(f"[Task {task_id}] Counting total candidate pairs...")
        
        intra_task_pairs: List[Tuple[dict, dict]] = []
        cross_task_pairs: List[Tuple[dict, dict]] = []
        
        for file_a, file_b in combinations(files, 2):
            intra_task_pairs.append((file_a, file_b))
        
        log.info(f"[Task {task_id}] Intra-task pairs: {len(intra_task_pairs)}")
        
        if existing_files:
            for new_file in files:
                new_file_hash = new_file.get('hash') or new_file.get('file_hash')
                new_file_path = new_file.get('path') or new_file.get('file_path')
                
                if not new_file_hash or not new_file_path:
                    continue
                
                try:
                    fingerprints = cache.get_fingerprints(new_file_hash)
                    if fingerprints is None:
                        fp_result = run_cli_fingerprint(new_file_path, language)
                        fingerprints = [
                            {
                                "hash": fp["hash"],
                                "start": tuple(fp["start"]),
                                "end": tuple(fp["end"])
                            }
                            for fp in fp_result.get("fingerprints", [])
                        ]
                        ast_hashes = fp_result.get("ast_hashes", [])
                        tokens_serializable = fp_result.get("tokens", [])
                        tokens = [(t["type"], tuple(t["start"]), tuple(t["end"])) for t in tokens_serializable]
                        cache.cache_fingerprints(new_file_hash, fingerprints, ast_hashes, tokens)
                    
                    candidate_hashes = inverted_index.find_candidate_files(fingerprints, language)
                    
                    if not candidate_hashes:
                        log.info(f"[Task {task_id}] {new_file.get('filename')}: 0 candidates")
                        continue
                    
                    candidate_files = [
                        f for f in existing_files 
                        if (f.get('hash') or f.get('file_hash')) in candidate_hashes
                    ]
                    
                    for existing_file in candidate_files:
                        cross_task_pairs.append((new_file, existing_file))
                    
                    skipped = len(existing_files) - len(candidate_files)
                    log.info(f"[Task {task_id}] {new_file.get('filename')}: {len(candidate_files)} candidates")
                    
                except Exception as e:
                    log.error(f"[Task {task_id}] Error counting candidates for {new_file.get('filename')}: {e}")
                    for existing_file in existing_files:
                        cross_task_pairs.append((new_file, existing_file))
        
        log.info(f"[Task {task_id}] Cross-task pairs: {len(cross_task_pairs)}")
        
        total_pairs_count = len(intra_task_pairs) + len(cross_task_pairs)
        
        log.info(f"[Task {task_id}] TOTAL PAIRS TO ANALYZE: {total_pairs_count}")
        
        update_plagiarism_task(
            task_id=task_id,
            status="processing",
            total_pairs=total_pairs_count,
            processed_pairs=0
        )
        
        processed_count = 0
        
        def process_pair(file_a, file_b, is_cross_task=False):
            nonlocal processed_count
            
            file_a_id = file_a.get("id")
            file_b_id = file_b.get("id")
            file_a_hash = file_a.get('hash') or file_a.get('file_hash')
            file_b_hash = file_b.get('hash') or file_b.get('file_hash')
            file_a_path = file_a.get("path") or file_a.get("file_path")
            file_b_path = file_b.get("path") or file_b.get("file_path")

            if not file_a_id or not file_b_id or not file_a_path or not file_b_path:
                log.warning(f"[Task {task_id}] Skipping pair due to missing file info")
                return
            
            if not file_a_hash or not file_b_hash:
                log.warning(f"[Task {task_id}] Skipping pair due to missing file hash")
                return

            try:
                task_type = "cross" if is_cross_task else "intra"
                progress_pct = (processed_count / total_pairs_count * 100) if total_pairs_count > 0 else 0
                log.info(f"[Task {task_id}] [{task_type}] ({processed_count}/{total_pairs_count} - {progress_pct:.1f}%) "
                        f"{file_a.get('filename')} vs {file_b.get('filename')}")

                cached_result = cache.get_cached_similarity(file_a_hash, file_b_hash)
                if cached_result:
                    log.info(f"[Task {task_id}]   Using cached similarity result")
                    ast_similarity = cached_result['ast_similarity']
                    matches_data = cached_result['matches']
                else:
                    if not cache.has_ast_fingerprints(file_a_hash):
                        fp_result_a = run_cli_fingerprint(file_a_path, language)
                        fingerprints_a = [
                            {
                                "hash": fp["hash"],
                                "start": tuple(fp["start"]),
                                "end": tuple(fp["end"])
                            }
                            for fp in fp_result_a.get("fingerprints", [])
                        ]
                        ast_hashes_a = fp_result_a.get("ast_hashes", [])
                        tokens_a = [(t["type"], tuple(t["start"]), tuple(t["end"])) for t in fp_result_a.get("tokens", [])]
                        cache.cache_fingerprints(file_a_hash, fingerprints_a, ast_hashes_a, tokens_a)
                    
                    if not cache.has_ast_fingerprints(file_b_hash):
                        fp_result_b = run_cli_fingerprint(file_b_path, language)
                        fingerprints_b = [
                            {
                                "hash": fp["hash"],
                                "start": tuple(fp["start"]),
                                "end": tuple(fp["end"])
                            }
                            for fp in fp_result_b.get("fingerprints", [])
                        ]
                        ast_hashes_b = fp_result_b.get("ast_hashes", [])
                        tokens_b = [(t["type"], tuple(t["start"]), tuple(t["end"])) for t in fp_result_b.get("tokens", [])]
                        cache.cache_fingerprints(file_b_hash, fingerprints_b, ast_hashes_b, tokens_b)

                    ast_similarity = cache.calculate_ast_similarity(file_a_hash, file_b_hash)
                    log.info(f"[Task {task_id}]   AST similarity (Redis): {ast_similarity:.4f}")

                    cache.cache_similarity_result(file_a_hash, file_b_hash, ast_similarity)

                result_id = save_similarity_result(
                    task_id=task_id,
                    file_a_id=file_a_id,
                    file_b_id=file_b_id,
                    ast_similarity=ast_similarity
                )

                processed_count += 1
                
                if processed_count % 10 == 0 or processed_count == total_pairs_count:
                    update_plagiarism_task(
                        task_id=task_id,
                        status="processing",
                        processed_pairs=processed_count
                    )
                
                log.info(f"[Task {task_id}]   Saved result {result_id}: ast={ast_similarity:.4f}")
                
            except Exception as e:
                log.error(f"[Task {task_id}]   Error comparing files {file_a_id} vs {file_b_id}: {e}")
                import traceback
                log.error(traceback.format_exc())
                save_similarity_result(
                    task_id=task_id,
                    file_a_id=file_a_id,
                    file_b_id=file_b_id,
                    error=str(e)
                )
                processed_count += 1

        if intra_task_pairs:
            log.info(f"[Task {task_id}] Processing {len(intra_task_pairs)} intra-task pairs...")
            for file_a, file_b in intra_task_pairs:
                process_pair(file_a, file_b, is_cross_task=False)
        
        if cross_task_pairs:
            log.info(f"[Task {task_id}] Processing {len(cross_task_pairs)} cross-task pairs...")
            for new_file, existing_file in cross_task_pairs:
                process_pair(new_file, existing_file, is_cross_task=True)
        
        update_plagiarism_task(
            task_id=task_id,
            status="completed",
            similarity=0.0,
            matches={"total_pairs": total_pairs_count, "processed_pairs": processed_count},
            total_pairs=total_pairs_count,
            processed_pairs=processed_count
        )
        
        log.info(f"[Task {task_id}] COMPLETED: {processed_count}/{total_pairs_count} pairs analyzed")
        
        if connection:
            connection.add_callback_threadsafe(
                functools.partial(ack_message, channel, delivery_tag)
            )
        
    except Exception as e:
        log.error(f"Error processing message: {e}")
        import traceback
        log.error(traceback.format_exc())
        if task_id:
            update_plagiarism_task(
                task_id=task_id,
                status="failed",
                error=str(e)
            )
        if connection:
            connection.add_callback_threadsafe(
                functools.partial(reject_message, channel, delivery_tag, False)
            )


def on_message(
    ch: "BlockingChannel",
    method: "Basic.Deliver",
    properties: "BasicProperties",
    body: bytes,
) -> None:
    """
    Callback for incoming RabbitMQ messages.
    Submits the task to the thread pool for processing.
    The main thread returns immediately to handle heartbeats.
    """
    log.info(f"Received message, submitting to thread pool...")
    if executor:
        executor.submit(
            process_task,
            body,
            ch,
            method.delivery_tag,
        )
    else:
        log.error("Thread pool executor not initialized!")


def consume_messages(ch: "BlockingChannel") -> None:
    """
    Start consuming messages from RabbitMQ.
    The prefetch_count controls how many messages can be processed concurrently.
    """
    log.info("[X] Waiting for plagiarism tasks...")
    ch.basic_qos(prefetch_count=settings.worker_concurrency)
    ch.basic_consume(
        queue=settings.rmq_queue_name,
        on_message_callback=on_message,
    )
    ch.start_consuming()


if __name__ == "__main__":
    configure_logging(level=logging.INFO)

    log.info("Connecting to Redis cache...")
    redis_connected = connect_cache()
    if redis_connected:
        log.info("Redis cache connected and ready")
    else:
        log.warning("Redis cache unavailable, running without caching")
    
    try:
        stats = inverted_index.get_stats()
        log.info(f"Inverted index stats: {stats['indexed_files']} files indexed, "
                f"{stats['unique_hashes']} unique hashes, "
                f"threshold={stats['min_overlap_threshold']:.0%}")
    except Exception as e:
        log.warning(f"Could not get inverted index stats: {e}")

    max_workers = getattr(settings, 'worker_concurrency', 4)
    executor = ThreadPoolExecutor(max_workers=max_workers)
    log.info(f"Thread pool executor started with {max_workers} workers")

    max_retries = 30
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            log.info(f"Connecting to RabbitMQ (attempt {attempt + 1}/{max_retries})...")
            connection = get_connection()
            with connection:
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
                executor.shutdown(wait=False)
                raise
