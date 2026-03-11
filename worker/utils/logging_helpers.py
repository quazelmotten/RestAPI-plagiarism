"""
Logging helper functions.
"""

import logging
from typing import Optional

log = logging.getLogger(__name__)


def log_task_start(task_id: str) -> None:
    """Log task start."""
    log.info(f"[Task {task_id}] Start processing plagiarism task")


def log_task_progress(task_id: str, current: int, total: int) -> None:
    """
    Log task progress.
    
    Args:
        task_id: Task ID
        current: Current progress count
        total: Total count
    """
    if total > 0:
        progress_pct = (current / total) * 100
        log.info(f"[Task {task_id}] Progress: {current}/{total} ({progress_pct:.1f}%)")


def log_task_complete(task_id: str, processed: int, total: int) -> None:
    """Log task completion."""
    log.info(f"[Task {task_id}] COMPLETED: {processed}/{total} pairs analyzed")


def log_file_indexing(task_id: str, filename: str, count: int, is_new: bool = True) -> None:
    """Log file indexing progress."""
    action = "Indexed" if is_new else "Added existing"
    log.debug(f"[Task {task_id}] {action} {count} fingerprints for {filename}")
