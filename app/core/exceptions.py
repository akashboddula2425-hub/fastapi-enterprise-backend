from fastapi import status


class AppException(Exception):
    """Base class for domain exceptions.

    Subclasses set `status_code` and pass a human-readable message. Handlers
    in main.py translate these into the standard error envelope.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message: str = "Internal server error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)
        self.message = message or self.default_message


class NotFoundError(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    default_message = "Resource not found"


class BusinessLogicError(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_message = "Request violates business rules"


class AuthorizationError(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    default_message = "Not authorized to perform this action"


class ConflictError(AppException):
    status_code = status.HTTP_409_CONFLICT
    default_message = "Resource conflict"
