class DiscoveryClientError(Exception):
    """Base class for DiscoveryClient exceptions."""

    status_code = 500
    detail: str = 'An unexpected error occurred in the Discovery Client.'


class DiscoveryServiceUnavailableError(DiscoveryClientError):
    """Raised when the Discovery service is unavailable."""

    status_code = 503

    def __init__(self) -> None:
        self.detail = 'The Discovery service is currently unavailable.'
        super().__init__(self.detail)
