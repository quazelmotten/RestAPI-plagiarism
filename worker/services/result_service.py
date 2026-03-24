"""
Result service - persists plagiarism analysis results to database.

Responsible for:
- Storing similarity results (bulk insert)
- Updating task progress and status
- Finalizing completed tasks
"""

import logging
from typing import List, Dict, Any, Optional

from shared.interfaces import TaskRepository

logger = logging.getLogger(__name__)


class ResultService:
    """Handles result persistence and task lifecycle updates."""

    def __init__(self, repository: TaskRepository):
        """
        Initialize result service.

        Args:
            repository: Task repository for database operations
        """
        self.repository = repository

    def store_similarity_scores(
        self,
        task_id: str,
        pairs: List[tuple],
        batch_size: int = 100
    ) -> None:
        """
        Store similarity scores for candidate pairs.

        Args:
            task_id: Task identifier
            pairs: List of (file_a_dict, file_b_dict, similarity_score) tuples
            batch_size: Batch size for DB inserts
        """
        if not pairs:
            logger.info(f"[Task {task_id}] No pairs to store")
            return

        results = []
        for file_a, file_b, similarity in pairs:
            file_a_id = file_a.get('id')
            file_b_id = file_b.get('id')
            if not file_a_id or not file_b_id:
                continue

            results.append({
                'task_id': task_id,
                'file_a_id': file_a_id,
                'file_b_id': file_b_id,
                'ast_similarity': round(similarity, 6),
                'matches': {},
            })

        if not results:
            logger.info(f"[Task {task_id}] No valid pairs to store")
            return

        total = len(results)
        log_interval = max(batch_size, total // 20)  # every 5%

        for i in range(0, total, batch_size):
            batch = results[i:i+batch_size]
            self.repository.bulk_insert_results(batch)
            processed = min(i + batch_size, total)

            # Update progress
            self.repository.update_task(
                task_id=task_id,
                status="storing_results",
                processed_pairs=processed
            )

            if processed % log_interval < batch_size or processed == total:
                percent = processed / total * 100
                logger.info(f"[Task {task_id}] Stored {processed}/{total} ({percent:.0f}%)")

        logger.info(f"[Task {task_id}] Stored all {total} similarity results")

    def update_progress(
        self,
        task_id: str,
        processed: int,
        total: int
    ) -> None:
        """Update task processing progress."""
        self.repository.update_task(
            task_id=task_id,
            status="storing_results",
            processed_pairs=processed,
            total_pairs=total
        )

        if processed % 1000 == 0 or (total > 0 and processed % max(1, total // 10) == 0):
            percent = (processed / total * 100) if total > 0 else 0
            logger.info(f"[Task {task_id}] Progress: {processed}/{total} ({percent:.1f}%)")

    def finalize_task(
        self,
        task_id: str,
        total_pairs: int,
        processed_count: int
    ) -> None:
        """
        Mark task as completed.

        Args:
            task_id: Task identifier
            total_pairs: Total number of pairs to process
            processed_count: Number of pairs actually processed
        """
        max_sim = self.repository.get_max_similarity(task_id)

        self.repository.update_task(
            task_id=task_id,
            status="completed",
            similarity=max_sim,
            matches={
                "total_pairs": total_pairs,
                "processed_pairs": processed_count
            },
            total_pairs=total_pairs,
            processed_pairs=processed_count
        )

        logger.info(
            f"[Task {task_id}] COMPLETED: max_similarity={max_sim:.3f}, "
            f"processed={processed_count}/{total_pairs}"
        )

    def mark_failed(self, task_id: str, error: str) -> None:
        """Mark task as failed with error message."""
        self.repository.update_task(
            task_id=task_id,
            status="failed",
            error=error[:1000]  # Truncate long errors
        )
        logger.error(f"[Task {task_id}] FAILED: {error}")
