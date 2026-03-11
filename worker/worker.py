"""
Minimal worker entry point.
Single responsibility: Initialize services and start the worker.
"""

import os
import sys

# Add project root to sys.path to allow imports from cli, src, etc.
worker_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(worker_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from worker_lifecycle import WorkerLifecycle
from services.plagiarism_service import PlagiarismService
from services.processor_service import ProcessorService
from services.result_service import ResultService
from services.task_orchestrator import TaskOrchestrator
from message_handler import MessageHandler


def main():
    """Initialize and run the worker."""
    # Initialize services
    plagiarism_service = PlagiarismService()
    processor_service = ProcessorService(plagiarism_service)
    result_service = ResultService(plagiarism_service)
    
    task_orchestrator = TaskOrchestrator(
        plagiarism_service=plagiarism_service,
        processor_service=processor_service,
        result_service=result_service
    )
    
    message_handler = MessageHandler(task_orchestrator)
    
    # Create and run worker
    worker = WorkerLifecycle(message_handler=message_handler)
    worker.run()


if __name__ == "__main__":
    main()
