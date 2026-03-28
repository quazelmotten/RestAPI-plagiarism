"""
Services - re-exports from domain service modules.

Domain-specific services live in their respective modules:
- tasks.service (TaskService)
- files.service (FileService)
- results.service (ResultService)
"""


def get_task_service():
    from tasks.service import TaskService

    return TaskService


def get_file_service():
    from files.service import FileService

    return FileService


def get_result_service():
    from results.service import ResultService

    return ResultService
