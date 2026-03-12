"""
Orchestrates the plagiarism detection task workflow.
Coordinates between services to process a complete task.
"""

import json
import logging
import time
from typing import List, Dict, Tuple, Optional, Any

from crud import update_plagiarism_task, get_all_files

log = logging.getLogger(__name__)


class TaskOrchestrator:
    """Orchestrates the plagiarism detection task workflow."""
    
    def __init__(
        self,
        plagiarism_service,
        processor_service,
        result_service
    ):
        """
        Initialize task orchestrator.
        
        Args:
            plagiarism_service: PlagiarismService instance
            processor_service: ProcessorService instance
            result_service: ResultService instance
        """
        self.plagiarism_service = plagiarism_service
        self.processor_service = processor_service
        self.result_service = result_service
    
    def process_task(
        self,
        body: bytes,
        channel: Optional[Any] = None,
        delivery_tag: Optional[int] = None
    ) -> None:
        """
        Process a plagiarism detection task with detailed timing logs.
        
        Args:
            body: Raw message body bytes
            channel: RabbitMQ channel (for ack/reject)
            delivery_tag: Message delivery tag for ack/reject
        """
        task_id = None
        
        try:
            message = json.loads(body.decode())
            task_id = message.get("task_id")
            start_time = time.time()
            log.info(f"[Task {task_id}] ============ TASK START ============")
            
            # Initialize timing accumulators
            index_time = 0.0
            pair_gen_time = 0.0
            analysis_elapsed = 0.0

            if not task_id:
                log.error("No task_id in message")
                raise ValueError("No task_id in message")
            
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
                raise ValueError("Need at least 2 files for plagiarism check")
            
            # Mark task as processing
            update_plagiarism_task(
                task_id=task_id,
                status="processing"
            )
            
            # Get existing files from other tasks
            log.info(f"[Task {task_id}] Fetching existing files from other tasks...")
            existing_files = get_all_files(exclude_task_id=task_id)
            log.info(f"[Task {task_id}] Found {len(existing_files)} existing files from other tasks")
            
            # Index fingerprints for all relevant files
            index_start = time.time()
            self.processor_service.ensure_files_indexed(
                files=files,
                language=language,
                task_id=task_id,
                existing_files=existing_files
            )
            index_end = time.time()
            index_time = index_end - index_start
            log.info(f"[Task {task_id}] Timing: ensure_files_indexed took {index_time:.2f}s")
            
            # Generate candidate pairs
            pair_gen_start = time.time()
            intra_task_pairs = self.processor_service.find_intra_task_pairs(
                files=files,
                language=language,
                task_id=task_id
            )
            
            cross_task_pairs = self.processor_service.find_cross_task_pairs(
                new_files=files,
                existing_files=existing_files,
                language=language,
                task_id=task_id
            )
            pair_gen_end = time.time()
            pair_gen_time = pair_gen_end - pair_gen_start
            log.info(f"[Task {task_id}] Timing: find_cross_task_pairs took {pair_gen_time:.2f}s")
            
            # Combine all pairs for concurrent processing
            all_pairs = []
            all_pairs.extend(intra_task_pairs)
            all_pairs.extend(cross_task_pairs)
            
            total_pairs_count = len(all_pairs)
            
            log.info(f"[Task {task_id}] TOTAL PAIRS TO ANALYZE: {total_pairs_count}")
            
            # Update task with total pairs count
            update_plagiarism_task(
                task_id=task_id,
                status="processing",
                total_pairs=total_pairs_count,
                processed_pairs=0
            )
            
            processed_count = 0
            result_buffer = []
            
            # Get executor from plagiarism service
            executor = self.plagiarism_service.analysis_executor
            
            analysis_start_time = time.time()
            
            if executor is None:
                # Fallback to sequential processing if no executor
                log.warning(f"[Task {task_id}] No analysis executor available, processing sequentially")
                for file_a, file_b in all_pairs:
                    result = self.result_service.process_pair(
                        file_a=file_a,
                        file_b=file_b,
                        language=language,
                        task_id=task_id
                    )
                    processed_count += 1
                    result_buffer.append(result)
                    
                    # Flush results every 50 pairs
                    if len(result_buffer) >= 50:
                        self.result_service.flush_results(task_id, result_buffer)
                        self.result_service.update_task_progress_batch(
                            task_id=task_id,
                            processed=processed_count,
                            total=total_pairs_count
                        )
            else:
                # Concurrent processing with batches
                BATCH_SIZE = 50
                log.info(f"[Task {task_id}] Processing {len(all_pairs)} pairs concurrently using {executor._max_workers} workers...")
                
                for batch_start in range(0, len(all_pairs), BATCH_SIZE):
                    batch_end = min(batch_start + BATCH_SIZE, len(all_pairs))
                    batch = all_pairs[batch_start:batch_end]
                    
                    # Submit all tasks in the batch
                    futures = []
                    for file_a, file_b in batch:
                        future = executor.submit(
                            self.result_service.process_pair,
                            file_a=file_a,
                            file_b=file_b,
                            language=language,
                            task_id=task_id
                        )
                        futures.append(future)
                    
                    # Collect results as they complete
                    for future in futures:
                        try:
                            result = future.result()
                            processed_count += 1
                            result_buffer.append(result)
                        except Exception as e:
                            log.error(f"[Task {task_id}] Future failed: {e}")
                            processed_count += 1
                            result_buffer.append({
                                'task_id': task_id,
                                'file_a_id': None,
                                'file_b_id': None,
                                'ast_similarity': None,
                                'matches': {'error': str(e)},
                            })
                        
                        # Flush if buffer reaches BATCH_SIZE
                        if len(result_buffer) >= 50:
                            self.result_service.flush_results(task_id, result_buffer)
                            self.result_service.update_task_progress_batch(
                                task_id=task_id,
                                processed=processed_count,
                                total=len(all_pairs)
                             )
             
            analysis_elapsed = time.time() - analysis_start_time
            log.info(f"[Task {task_id}] Timing: analysis (pair processing) took {analysis_elapsed:.2f}s")
            
            # Final flush of any remaining results
            self.result_service.flush_results(task_id, result_buffer, force=True)

             # Finalize task
            self.result_service.finalize_task(
                task_id=task_id,
                total_pairs=total_pairs_count,
                processed_count=processed_count
            )

            # Log phase summary
            log.info(f"[Task {task_id}] Phase summary: indexing={index_time:.2f}s, pair_gen={pair_gen_time:.2f}s, analysis={analysis_elapsed:.2f}s")

            duration = time.time() - start_time
            pairs_per_sec = total_pairs_count / duration if duration > 0 else 0
            log.info(f"[Task {task_id}] COMPLETED: {processed_count}/{total_pairs_count} pairs analyzed "
                    f"in {duration:.2f}s ({pairs_per_sec:.2f} pairs/sec)")

            # Message will be auto-acked by the worker thread wrapper on successful completion

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
            raise  # Re-raise to let worker nack the message

