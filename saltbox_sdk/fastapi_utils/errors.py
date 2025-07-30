from fastapi import status


class SaltBoxBaseError(Exception):
    """Base class for all SaltBox errors."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = 'An unexpected error occurred in the SaltBox service.'

    def __str__(self) -> str:
        return f'{self.__class__.__name__}: {self.detail}'


class UserHeadersMissingError(SaltBoxBaseError):
    """Raised when user headers are missing from the gateway request."""

    status_code = status.HTTP_401_UNAUTHORIZED
    detail = 'Required user headers are missing from the request.'
