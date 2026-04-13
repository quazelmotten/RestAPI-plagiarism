class NotFoundError(Exception):
    def __init__(self, message: str = "Resource not found"):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message


class PlagiarismValidationError(Exception):
    def __init__(self, message: str = "Validation error"):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message


class ForbiddenError(Exception):
    def __init__(self, message: str = "Access forbidden"):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message


class NoAccessError(Exception):
    def __init__(self, message: str = "You don't have access to this resource"):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message
