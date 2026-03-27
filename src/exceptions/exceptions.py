class NotFoundError(Exception):
    def __init__(self, message: str = "Resource not found"):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message


class ValidationError(Exception):
    def __init__(self, message: str = "Validation error"):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message


class ExchangeNotFound(Exception):
    def __str__(self):
        return "exchange not found"
