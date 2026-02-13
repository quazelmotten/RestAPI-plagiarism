import json
import logging
import sys
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Set, Tuple

from crud import update_plagiarism_task, save_similarity_result, get_all_files

from plagiarism.analyzer import analyze_plagiarism_cached, tokenize_with_tree_sitter, winnow_fingerprints, compute_fingerprints
from redis_cache import cache, connect_cache
from inverted_index import inverted_index


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

        # Get all existing files from other tasks for cross-task comparison
        log.info("Fetching existing files from other tasks for cross-task comparison...")
        existing_files = get_all_files(exclude_task_id=task_id)
        log.info(f"Found {len(existing_files)} existing files from other tasks")
        
        # Index fingerprints for all new files in the inverted index
        # This enables fast candidate lookup for future tasks
        log.info("Indexing fingerprints for new files in inverted index...")
        for file_info in files:
            file_hash = file_info.get('hash') or file_info.get('file_hash')
            file_path = file_info.get('path') or file_info.get('file_path')
            
            if not file_hash or not file_path:
                continue
                
            try:
                # Check if already in inverted index
                if inverted_index.get_file_fingerprints(file_hash, language):
                    log.debug(f"File {file_info.get('filename')} already in inverted index")
                    continue
                
                # Compute fingerprints
                tokens = tokenize_with_tree_sitter(file_path, language)
                fingerprints = winnow_fingerprints(compute_fingerprints(tokens))
                
                # Add to inverted index
                inverted_index.add_file_fingerprints(file_hash, fingerprints, language)
                log.debug(f"Indexed {len(fingerprints)} fingerprints for {file_info.get('filename')}")
            except Exception as e:
                log.warning(f"Failed to index file {file_info.get('filename')}: {e}")
        
        log.info("Finished indexing fingerprints for new files")

        # PHASE 1: Count all pairs upfront
        log.info("=" * 70)
        log.info("PHASE 1: Counting total candidate pairs...")
        log.info("=" * 70)
        
        intra_task_pairs: List[Tuple[dict, dict]] = []
        cross_task_pairs: List[Tuple[dict, dict]] = []
        
        # 1. Count intra-task pairs (within the new task)
        for file_a, file_b in combinations(files, 2):
            intra_task_pairs.append((file_a, file_b))
        
        log.info(f"Intra-task pairs (within this task): {len(intra_task_pairs)}")
        
        # 2. Count cross-task pairs (against existing files using inverted index)
        if existing_files:
            for new_file in files:
                new_file_hash = new_file.get('hash') or new_file.get('file_hash')
                new_file_path = new_file.get('path') or new_file.get('file_path')
                
                if not new_file_hash or not new_file_path:
                    continue
                
                try:
                    # Get fingerprints for the new file
                    fingerprints = cache.get_fingerprints(new_file_hash)
                    if fingerprints is None:
                        tokens = tokenize_with_tree_sitter(new_file_path, language)
                        fingerprints = winnow_fingerprints(compute_fingerprints(tokens))
                        cache.cache_fingerprints(new_file_hash, fingerprints, [], tokens)
                    
                    # Find candidate files using inverted index
                    candidate_hashes = inverted_index.find_candidate_files(fingerprints, language)
                    
                    if not candidate_hashes:
                        log.info(f"  {new_file.get('filename')}: 0 candidates (all {len(existing_files)} files filtered out)")
                        continue
                    
                    # Get candidate files
                    candidate_files = [
                        f for f in existing_files 
                        if (f.get('hash') or f.get('file_hash')) in candidate_hashes
                    ]
                    
                    # Add pairs to cross-task list
                    for existing_file in candidate_files:
                        cross_task_pairs.append((new_file, existing_file))
                    
                    skipped = len(existing_files) - len(candidate_files)
                    log.info(f"  {new_file.get('filename')}: {len(candidate_files)} candidates (filtered {skipped} files)")
                    
                except Exception as e:
                    log.error(f"Error counting candidates for {new_file.get('filename')}: {e}")
                    # Fallback: count all existing files as candidates
                    for existing_file in existing_files:
                        cross_task_pairs.append((new_file, existing_file))
                    log.warning(f"  {new_file.get('filename')}: Fallback to {len(existing_files)} candidates")
        
        log.info(f"Cross-task pairs (filtered candidates): {len(cross_task_pairs)}")
        
        # Calculate total
        total_pairs_count = len(intra_task_pairs) + len(cross_task_pairs)
        
        log.info("=" * 70)
        log.info(f"TOTAL CANDIDATE PAIRS TO ANALYZE: {total_pairs_count}")
        log.info(f"  - Intra-task: {len(intra_task_pairs)}")
        log.info(f"  - Cross-task: {len(cross_task_pairs)}")
        log.info("=" * 70)
        
        # Store total_pairs in database
        update_plagiarism_task(
            task_id=task_id,
            status="processing",
            total_pairs=total_pairs_count,
            processed_pairs=0
        )
        
        # PHASE 2: Process all pairs
        log.info("")
        log.info("=" * 70)
        log.info("PHASE 2: Processing pairs with progress tracking...")
        log.info("=" * 70)
        
        processed_count = 0
        
        def process_pair(file_a, file_b, is_cross_task=False):
            """Process a single pair of files and update progress."""
            nonlocal processed_count
            
            file_a_id = file_a.get("id")
            file_b_id = file_b.get("id")
            file_a_path = file_a.get("path") or file_a.get("file_path")
            file_b_path = file_b.get("path") or file_b.get("file_path")

            if not file_a_id or not file_b_id or not file_a_path or not file_b_path:
                log.warning(f"Skipping pair due to missing file info: {file_a}, {file_b}")
                return

            try:
                task_type = "cross" if is_cross_task else "intra"
                progress_pct = (processed_count / total_pairs_count * 100) if total_pairs_count > 0 else 0
                log.info(f"[{task_type}] ({processed_count}/{total_pairs_count} - {progress_pct:.1f}%) "
                        f"{file_a.get('filename')} vs {file_b.get('filename')}")

                # Get file hashes for caching
                file_a_hash = file_a.get('hash') or file_a.get('file_hash')
                file_b_hash = file_b.get('hash') or file_b.get('file_hash')

                # Run plagiarism analysis with caching
                result = analyze_plagiarism_cached(
                    file_a_path, file_b_path,
                    file_a_hash, file_b_hash,
                    cache=cache,
                    language=language
                )
                
                # Handle different return formats
                if len(result) == 3:
                    token_similarity, ast_similarity, raw_matches = result
                else:
                    ast_similarity, raw_matches = result
                    token_similarity = ast_similarity
                
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

                processed_count += 1
                
                # Update progress in database every 10 pairs or at milestones
                if processed_count % 10 == 0 or processed_count == total_pairs_count:
                    update_plagiarism_task(
                        task_id=task_id,
                        status="processing",
                        processed_pairs=processed_count
                    )
                
                log.info(f"  ✓ Saved result {result_id}: token={token_similarity:.4f}, ast={ast_similarity:.4f}")
                
            except Exception as e:
                log.error(f"  ✗ Error comparing files {file_a_id} vs {file_b_id}: {e}")
                import traceback
                log.error(traceback.format_exc())
                # Save failed result
                save_similarity_result(
                    task_id=task_id,
                    file_a_id=file_a_id,
                    file_b_id=file_b_id,
                    error=str(e)
                )
                processed_count += 1

        # Process intra-task pairs
        if intra_task_pairs:
            log.info(f"\nProcessing {len(intra_task_pairs)} intra-task pairs...")
            for file_a, file_b in intra_task_pairs:
                process_pair(file_a, file_b, is_cross_task=False)
        
        # Process cross-task pairs
        if cross_task_pairs:
            log.info(f"\nProcessing {len(cross_task_pairs)} cross-task pairs...")
            for new_file, existing_file in cross_task_pairs:
                process_pair(new_file, existing_file, is_cross_task=True)
        
        # Update status to completed
        update_plagiarism_task(
            task_id=task_id,
            status="completed",
            similarity=None,
            matches={"total_pairs": total_pairs_count, "processed_pairs": processed_count},
            total_pairs=total_pairs_count,
            processed_pairs=processed_count
        )
        
        log.info("")
        log.info("=" * 70)
        log.info(f"+++ Task {task_id} COMPLETED: {processed_count}/{total_pairs_count} pairs analyzed")
        log.info("=" * 70)
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except Exception as e:
        log.error(f"Error processing message: {e}")
        import traceback
        log.error(traceback.format_exc())
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

    # Connect to Redis cache
    log.info("Connecting to Redis cache...")
    redis_connected = connect_cache()
    if redis_connected:
        log.info("✓ Redis cache connected and ready")
    else:
        log.warning("⚠ Redis cache unavailable, running without caching")
    
    # Check inverted index stats
    try:
        stats = inverted_index.get_stats()
        log.info(f"Inverted index stats: {stats['indexed_files']} files indexed, "
                f"{stats['unique_hashes']} unique hashes, "
                f"threshold={stats['min_overlap_threshold']:.0%}")
    except Exception as e:
        log.warning(f"⚠ Could not get inverted index stats: {e}")

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
