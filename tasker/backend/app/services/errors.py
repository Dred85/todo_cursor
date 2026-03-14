class TaskError(Exception):
    pass


class TaskValidationError(TaskError):
    pass


class TaskPermissionError(TaskError):
    pass

