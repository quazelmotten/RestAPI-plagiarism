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


class ExchangeNotFoundError(Exception):
    def __str__(self):
        return "exchange not found"
