from saltbox_sdk.exceptions import SaltBoxBaseException
from saltbox_sdk.utilities import status


class DiscoveryClientException(SaltBoxBaseException):
    """Base class for DiscoveryClient exceptions."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = 'An unexpected error occurred in the Discovery Client.'


class DiscoveryServiceUnavailableException(DiscoveryClientException):
    """Raised when the Discovery service is unavailable."""

    status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE
    detail: str = 'The Discovery service is currently unavailable.'
