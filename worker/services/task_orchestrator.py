"""
Orchestrates the plagiarism detection task workflow.
Coordinates between services to process a complete task.
"""

import json
import logging
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
            
            if not task_id:
                log.error("No task_id in message")
                self._reject_message(channel, delivery_tag, False)
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
                self._reject_message(channel, delivery_tag, False)
                return
            
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
            if intra_task_pairs:
                log.info(f"[Task {task_id}] Processing {len(intra_task_pairs)} intra-task pairs...")
                for file_a, file_b in intra_task_pairs:
                    success, processed_count = self.result_service.process_pair(
                        file_a=file_a,
                        file_b=file_b,
                        language=language,
                        task_id=task_id,
                        total_pairs=total_pairs_count,
                        processed_count=processed_count
                    )
            
            # Process cross-task pairs
            if cross_task_pairs:
                log.info(f"[Task {task_id}] Processing {len(cross_task_pairs)} cross-task pairs...")
                for new_file, existing_file in cross_task_pairs:
                    success, processed_count = self.result_service.process_pair(
                        file_a=new_file,
                        file_b=existing_file,
                        language=language,
                        task_id=task_id,
                        total_pairs=total_pairs_count,
                        processed_count=processed_count
                    )
            
            # Finalize task
            self.result_service.finalize_task(
                task_id=task_id,
                total_pairs=total_pairs_count,
                processed_count=processed_count
            )
            
            log.info(f"[Task {task_id}] COMPLETED: {processed_count}/{total_pairs_count} pairs analyzed")
            
            # Acknowledge message
            self._ack_message(channel, delivery_tag)
            
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
            self._reject_message(channel, delivery_tag, False)
    
    def _ack_message(self, channel, delivery_tag: int) -> None:
        """Acknowledge a message from RabbitMQ."""
        if channel and channel.is_open:
            channel.basic_ack(delivery_tag=delivery_tag)
        else:
            log.warning(f"Channel closed or None, cannot ack message {delivery_tag}")
    
    def _reject_message(self, channel, delivery_tag: int, requeue: bool = False) -> None:
        """Reject a message from RabbitMQ."""
        if channel and channel.is_open:
            channel.basic_reject(delivery_tag=delivery_tag, requeue=requeue)
        else:
            log.warning(f"Channel closed or None, cannot reject message {delivery_tag}")
