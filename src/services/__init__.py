# Lazy imports to avoid circular dependencies during testing
def get_task_service():
    from .task_service import TaskService
    return TaskService

def get_file_service():
    from .file_service import FileService
    return FileService

def get_result_service():
    from .result_service import ResultService
    return ResultService
