from typing import Any

from saltbox_sdk.utilities import status


class SaltBoxBaseException(Exception):
    """
    Base class for all SaltBox errors.

    Attributes:
        extra_fields tuple[str, ...]: Names of fields to add to error output.
            Fields should exists and must be JSON serializable.
    """

    extra_fields: tuple[str, ...] = ()
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    # TODO: (a.karmanov) :: `message` is a more common name
    detail: str = 'An unexpected error occurred in the SaltBox service.'

    def __init__(self, detail: str | Exception | None = None, status_code: int | None = None) -> None:
        if detail:
            self.detail = str(detail)
        if status_code:
            self.status_code = status_code
        super().__init__(self.detail)

    def __str__(self) -> str:
        return f'{self.__class__.__name__}: {self.detail}'

    def get_extra_fields(self) -> dict[str, Any]:
        return {attr: getattr(self, attr, '** MISSING FIELD **') for attr in self.extra_fields}


class SaltBoxValidationException(SaltBoxBaseException):
    """Raised when there is a validation error in the SaltBox service."""

    status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail: str = 'Validation error occurred.'


class UserHeadersMissingException(SaltBoxBaseException):
    """Raised when user headers are missing from the gateway request."""

    status_code: int = status.HTTP_401_UNAUTHORIZED
    detail: str = 'Required user headers are missing from the request.'


class PermissionDeniedException(SaltBoxBaseException):
    """Raised when an operation is not allowed on a given resource."""

    status_code: int = status.HTTP_403_FORBIDDEN
    detail: str = 'Operation not allowed on this resource.'


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

    extra_fields = ('obj_type', 'query')
    status_code: int = status.HTTP_404_NOT_FOUND
    detail: str = 'Object not found.'
    detail_with_obj_type: str = 'Object "{obj_type}" not found.'
    detail_with_query: str = 'Object not found by query: {query}.'
    detail_with_full: str = 'Object "{obj_type}" not found {query}.'

    def __init__(self, detail: str | None = None, obj_type: str | None = None, query: dict | None = None) -> None:
        self.obj_type = obj_type
        self.query = query

        if detail:
            self.detail = detail
        elif obj_type and query:
            self.detail = self.detail_with_full.format(obj_type=obj_type, query=query)
        elif obj_type:
            self.detail = self.detail_with_obj_type.format(obj_type=obj_type)
        elif query:
            self.detail = self.detail_with_query.format(query=query)

        super().__init__(self.detail)


class MultipleObjectsFoundException(RepositoryException):
    """Raised when multiple objects are found when only one was expected."""

    extra_fields = ('obj_type', 'query')
    status_code: int = status.HTTP_409_CONFLICT
    detail: str = 'Multiple objects found.'

    def __init__(self, detail: str | None = None, obj_type: str | None = None, query: dict | None = None) -> None:
        self.obj_type = obj_type
        self.query = query

        if detail:
            self.detail = detail

        super().__init__(self.detail)


class DuplicateKeyException(RepositoryException):
    """Raised when a duplicate key is encountered in the repository."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = 'Duplicate key error.'

    def __init__(self, detail: str | None = None, key_value: dict | None = None) -> None:
        if detail:
            self.detail = detail
        if key_value:
            self.detail += ' Unique constraint failed for: ('
            for key, value in key_value.items():
                self.detail += f'{key}={value}, '
            self.detail = self.detail.rstrip(', ') + ')'
        super().__init__(self.detail)


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
