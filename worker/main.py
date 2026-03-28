"""
Worker entry point.

Thin startup script — all dependency wiring lives in dependencies.py.
"""

import os
import sys

worker_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(worker_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from worker.config import settings  # noqa: E402
from worker.dependencies import get_task_service, shutdown_dependencies  # noqa: E402
from worker.message_handler import MessageHandler  # noqa: E402
from worker.worker_lifecycle import AsyncWorker  # noqa: E402


def main():
    """Initialize and run the worker."""
    task_service = get_task_service()
    message_handler = MessageHandler(task_service)

    worker = AsyncWorker(
        message_handler=message_handler, worker_concurrency=settings.worker_concurrency
    )

    try:
        worker.run()
    finally:
        shutdown_dependencies()


if __name__ == "__main__":
    main()
