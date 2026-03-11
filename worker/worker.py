"""
Minimal worker entry point.
Single responsibility: Initialize services and start the worker.
"""

import os
import sys
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

# Use spawn method to avoid file descriptor inheritance issues
# This must be done before any other multiprocessing usage
multiprocessing.set_start_method('spawn', force=True)

# Add project root to sys.path to allow imports from cli, src, etc.
worker_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(worker_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from worker_lifecycle import AsyncWorker
from services.plagiarism_service import PlagiarismService
from services.processor_service import ProcessorService
from services.result_service import ResultService
from services.task_orchestrator import TaskOrchestrator
from message_handler import MessageHandler


def main():
    """Initialize and run the worker."""
    from config import settings

    # Create shared analysis executor with limited processes
    # Use min(2, worker_concurrency) to limit total processes across all workers
    # Each process can be CPU-intensive; 2-3 processes per worker is usually sufficient
    analysis_max_workers = min(2, settings.worker_concurrency)
    analysis_executor = ProcessPoolExecutor(max_workers=analysis_max_workers)

    # Initialize services with shared executor
    plagiarism_service = PlagiarismService(analysis_executor=analysis_executor)
    processor_service = ProcessorService(plagiarism_service)
    result_service = ResultService(plagiarism_service)

    task_orchestrator = TaskOrchestrator(
        plagiarism_service=plagiarism_service,
        processor_service=processor_service,
        result_service=result_service
    )

    message_handler = MessageHandler(task_orchestrator)

    # Create and run worker (pass worker_concurrency and analysis_executor)
    worker = AsyncWorker(
        message_handler=message_handler,
        worker_concurrency=settings.worker_concurrency,
        analysis_executor=analysis_executor
    )
    try:
        worker.run()
    finally:
        # Ensure analysis executor is shut down
        analysis_executor.shutdown(wait=True)


if __name__ == "__main__":
    main()
