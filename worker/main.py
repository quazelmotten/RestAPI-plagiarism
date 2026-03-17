"""
Worker entry point.
Initializes services and starts the async worker.
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor

worker_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(worker_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from worker.worker_lifecycle import AsyncWorker
from worker.services.plagiarism_service import PlagiarismService
from worker.services.processor_service import ProcessorService
from worker.services.result_service import ResultService
from worker.services.task_orchestrator import TaskOrchestrator
from worker.message_handler import MessageHandler
from worker.config import settings


def main():
    """Initialize and run the worker."""
    analysis_max_workers = max(8, settings.worker_concurrency * 4)
    analysis_executor = ThreadPoolExecutor(max_workers=analysis_max_workers)

    plagiarism_service = PlagiarismService(analysis_executor=analysis_executor)
    processor_service = ProcessorService(plagiarism_service)
    result_service = ResultService(plagiarism_service)

    task_orchestrator = TaskOrchestrator(
        plagiarism_service=plagiarism_service,
        processor_service=processor_service,
        result_service=result_service
    )

    message_handler = MessageHandler(task_orchestrator)

    worker = AsyncWorker(
        message_handler=message_handler,
        worker_concurrency=settings.worker_concurrency,
        analysis_executor=analysis_executor
    )
    try:
        worker.run()
    finally:
        analysis_executor.shutdown(wait=True)


if __name__ == "__main__":
    main()
