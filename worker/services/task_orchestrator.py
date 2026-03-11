"""
Orchestrates the plagiarism detection task workflow.
Coordinates between services to process a complete task.
"""

import json
import logging
import time
from typing import List, Dict, Tuple

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
        channel = None,
        delivery_tag: int = None
    ) -> None:
        """
        Process a plagiarism detection task.
        
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
            self.processor_service.ensure_files_indexed(
                files=files,
                language=language,
                task_id=task_id,
                existing_files=existing_files
            )
            
            # Generate candidate pairs
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
            
            total_pairs_count = len(intra_task_pairs) + len(cross_task_pairs)
            log.info(f"[Task {task_id}] TOTAL PAIRS TO ANALYZE: {total_pairs_count}")
            
            # Update task with total pairs count
            update_plagiarism_task(
                task_id=task_id,
                status="processing",
                total_pairs=total_pairs_count,
                processed_pairs=0
            )
            
            # Process intra-task pairs
            processed_count = 0
            result_buffer = []
            if intra_task_pairs:
                log.info(f"[Task {task_id}] Processing {len(intra_task_pairs)} intra-task pairs...")
                for file_a, file_b in intra_task_pairs:
                    success, processed_count, result_buffer = self.result_service.process_pair(
                        file_a=file_a,
                        file_b=file_b,
                        language=language,
                        task_id=task_id,
                        total_pairs=total_pairs_count,
                        processed_count=processed_count,
                        result_buffer=result_buffer
                    )
                    # Flush results every 50 pairs
                    if len(result_buffer) >= 50:
                        self.result_service.flush_results(task_id, result_buffer)
                        # Update progress after flush
                        self.result_service.update_task_progress_batch(
                            task_id=task_id,
                            processed=processed_count,
                            total=total_pairs_count
                        )

            # Process cross-task pairs
            if cross_task_pairs:
                log.info(f"[Task {task_id}] Processing {len(cross_task_pairs)} cross-task pairs...")
                for new_file, existing_file in cross_task_pairs:
                    success, processed_count, result_buffer = self.result_service.process_pair(
                        file_a=new_file,
                        file_b=existing_file,
                        language=language,
                        task_id=task_id,
                        total_pairs=total_pairs_count,
                        processed_count=processed_count,
                        result_buffer=result_buffer
                    )
                    # Flush results every 50 pairs
                    if len(result_buffer) >= 50:
                        self.result_service.flush_results(task_id, result_buffer)
                        # Update progress after flush
                        self.result_service.update_task_progress_batch(
                            task_id=task_id,
                            processed=processed_count,
                            total=total_pairs_count
                        )
            
            # Final flush of any remaining results
            self.result_service.flush_results(task_id, result_buffer, force=True)

            # Finalize task
            self.result_service.finalize_task(
                task_id=task_id,
                total_pairs=total_pairs_count,
                processed_count=processed_count
            )

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

