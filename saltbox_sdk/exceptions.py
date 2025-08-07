from saltbox_sdk.utilities import status


class SaltBoxBaseException(Exception):
    """Base class for all SaltBox errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = 'An unexpected error occurred in the SaltBox service.'

    def __init__(self, detail: str | Exception | None = None, status_code: int | None = None) -> None:
        if detail:
            self.detail = str(detail)
        if status_code:
            self.status_code = status_code
        super().__init__(self.detail)

    def __str__(self) -> str:
        return f'{self.__class__.__name__}: {self.detail}'


class SaltBoxValidationException(SaltBoxBaseException):
    """Raised when there is a validation error in the SaltBox service."""

    status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail: str = 'Validation error occurred.'


class UserHeadersMissingException(SaltBoxBaseException):
    """Raised when user headers are missing from the gateway request."""

    status_code: int = status.HTTP_401_UNAUTHORIZED
    detail: str = 'Required user headers are missing from the request.'


# Base exceptions
class NotFoundException(SaltBoxBaseException):
    """Raised when a requested resource is not found."""

    status_code: int = status.HTTP_404_NOT_FOUND
    detail: str = 'Requested resource not found.'


# Repository errors
class RepositoryException(SaltBoxBaseException):
    """Base class for repository-related exceptions."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = 'An unexpected error occurred in the repository.'


class ObjectNotFoundException(RepositoryException):
    """Raised when an object is not found in the repository."""

    status_code: int = status.HTTP_404_NOT_FOUND
    detail: str = 'Object not found.'

    def __init__(self, detail: str | None = None, obj_type: str | None = None, query: dict | None = None) -> None:
        if detail:
            self.detail = detail
        if obj_type:
            self.detail += f' Type: {obj_type}.'
        if query:
            self.detail += f' Query: {query}.'

        super().__init__(self.detail)


class MultipleObjectsFoundException(RepositoryException):
    """Raised when multiple objects are found when only one was expected."""

    status_code: int = status.HTTP_409_CONFLICT
    detail: str = 'Multiple objects found.'


class DuplicateKeyException(RepositoryException):
    """Raised when a duplicate key is encountered in the repository."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = 'Duplicate key error.'


class ObjectCreateException(RepositoryException):
    """Raised when an object cannot be created in the repository."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = 'Object not created.'


class ObjectUpdateException(RepositoryException):
    """Raised when an object cannot be updated in the repository."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = 'Object not updated.'


class ObjectDeleteException(RepositoryException):
    """Raised when an object cannot be deleted from the repository."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = 'Object not deleted.'


class MongoPipelineException(RepositoryException):
    """Raised when there is an error building a MongoDB pipeline."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = 'Error in MongoDB pipeline execution.'


# Taskiq errors
class TaskiqException(SaltBoxBaseException):
    """Base class for Taskiq-related exceptions."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = 'An unexpected error occurred in task.'


class TaskiqTimeoutException(TaskiqException):
    """Exception raised when a Taskiq operation times out."""

    status_code: int = status.HTTP_408_REQUEST_TIMEOUT
    detail: str = 'The Taskiq operation timed out.'
