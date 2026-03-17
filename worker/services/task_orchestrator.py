"""
Orchestrates the plagiarism detection task workflow.
Coordinates between services to process a complete task.
"""

import json
import logging
import time
from typing import Any, Optional

from worker.crud import update_plagiarism_task, get_all_files

log = logging.getLogger(__name__)


class TaskOrchestrator:
    """Orchestrates the plagiarism detection task workflow."""

    def __init__(self, plagiarism_service, processor_service, result_service):
        self.plagiarism_service = plagiarism_service
        self.processor_service = processor_service
        self.result_service = result_service

    def process_task(
        self,
        body: bytes,
        channel: Optional[Any] = None,
        delivery_tag: Optional[int] = None
    ) -> None:
        """Process a plagiarism detection task from a RabbitMQ message."""
        task_id = None

        try:
            message = json.loads(body.decode())
            task_id = message.get("task_id")
            start_time = time.time()
            log.info(f"[Task {task_id}] ============ TASK START ============")

            if not task_id:
                raise ValueError("No task_id in message")

            files = message.get("files", [])
            language = message.get("language", "python")

            if len(files) < 2:
                update_plagiarism_task(
                    task_id=task_id,
                    status="failed",
                    error="Need at least 2 files for plagiarism check"
                )
                raise ValueError("Need at least 2 files for plagiarism check")

            update_plagiarism_task(task_id=task_id, status="processing")

            # Fetch existing files from other tasks
            existing_files = get_all_files(exclude_task_id=task_id)
            log.info(f"[Task {task_id}] Found {len(existing_files)} existing files")

            # Index fingerprints for all files
            index_start = time.time()
            fingerprint_map = self.processor_service.ensure_files_indexed(
                files=files,
                language=language,
                task_id=task_id,
                existing_files=existing_files
            )
            log.info(f"[Task {task_id}] Indexing took {time.time() - index_start:.2f}s")

            # Generate candidate pairs
            pair_start = time.time()
            intra_task_pairs = self.processor_service.find_intra_task_pairs(
                files=files,
                language=language,
                task_id=task_id,
                fingerprint_map=fingerprint_map
            )
            cross_task_pairs = self.processor_service.find_cross_task_pairs(
                new_files=files,
                existing_files=existing_files,
                language=language,
                task_id=task_id,
                fingerprint_map=fingerprint_map
            )
            log.info(f"[Task {task_id}] Pair generation took {time.time() - pair_start:.2f}s")

            all_pairs = intra_task_pairs + cross_task_pairs
            total_pairs_count = len(all_pairs)

            log.info(f"[Task {task_id}] Total pairs: {total_pairs_count}")

            update_plagiarism_task(
                task_id=task_id,
                status="processing",
                total_pairs=total_pairs_count,
                processed_pairs=0
            )

            # Store overlap percentages
            self.result_service.store_similarity_percentages(task_id, all_pairs)

            # Finalize task
            self.result_service.finalize_task(
                task_id=task_id,
                total_pairs=total_pairs_count,
                processed_count=total_pairs_count
            )

            duration = time.time() - start_time
            log.info(f"[Task {task_id}] COMPLETED: {total_pairs_count} pairs in {duration:.2f}s")

        except Exception as e:
            log.error(f"Error processing message: {e}")
            if task_id:
                update_plagiarism_task(
                    task_id=task_id,
                    status="failed",
                    error=str(e)
                )
            raise
