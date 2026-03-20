"""
Worker entry point - new service-oriented architecture.

Initializes all services with dependency injection and starts the async worker.
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor

worker_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(worker_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from worker.worker_lifecycle import AsyncWorker
from worker.message_handler import MessageHandler
from worker.config import settings

# Import new services
from worker.services.analysis_service import AnalysisService
from worker.services.fingerprint_service import FingerprintService
from worker.services.indexing_service import IndexingService
from worker.services.candidate_service import CandidateService
from worker.services.result_service import ResultService
from worker.services.task_service import TaskService

# Import infrastructure
from worker.dependencies import get_cache, get_index, get_repository


def main():
    """Initialize and run the worker."""
    analysis_executor = ThreadPoolExecutor(max_workers=settings.worker_concurrency)

    try:
        # Get shared infrastructure (singletons)
        cache = get_cache()
        index = get_index()
        repository = get_repository()

        # Build service graph with dependency injection
        analysis_service = AnalysisService(cache, analysis_executor)
        fingerprint_service = FingerprintService(cache)
        indexing_service = IndexingService(index, cache, fingerprint_service)
        candidate_service = CandidateService(index)
        result_service = ResultService(repository)

        task_service = TaskService(
            fingerprint_service=fingerprint_service,
            indexing_service=indexing_service,
            candidate_service=candidate_service,
            analysis_service=analysis_service,
            result_service=result_service,
            repository=repository
        )

        message_handler = MessageHandler(task_service)

        worker = AsyncWorker(
            message_handler=message_handler,
            worker_concurrency=settings.worker_concurrency,
            analysis_executor=analysis_executor
        )

        worker.run()

    finally:
        analysis_executor.shutdown(wait=True)


if __name__ == "__main__":
    main()
