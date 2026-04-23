class APIError(Exception):
    def __init__(
        self, message: str, status_code: int = 500, details: str | None = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class NotFoundError(APIError):
    def __init__(self, message: str = "Resource not found", details: str | None = None):
        super().__init__(message, status_code=404, details=details)


class BadRequestError(APIError):
    def __init__(self, message: str = "Bad request", details: str | None = None):
        super().__init__(message, status_code=400, details=details)


class UnauthorizedError(APIError):
    def __init__(self, message: str = "Unauthorized", details: str | None = None):
        super().__init__(message, status_code=401, details=details)


class ForbiddenError(APIError):
    def __init__(self, message: str = "Forbidden", details: str | None = None):
        super().__init__(message, status_code=403, details=details)


class InternalServerError(APIError):
    def __init__(
        self, message: str = "Internal server error", details: str | None = None
    ):
        super().__init__(message, status_code=500, details=details)
