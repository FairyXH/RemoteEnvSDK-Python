class RemoteEnvError(Exception):
    """Base exception for RemoteEnvSDK."""


class RemoteEnvConnectionError(RemoteEnvError):
    pass


class RemoteEnvAuthenticationError(RemoteEnvError):
    pass


class RemoteEnvTimeoutError(RemoteEnvError):
    pass


class RemoteEnvProtocolError(RemoteEnvError):
    pass


class RemoteEnvUploadError(RemoteEnvError):
    pass


class RemoteEnvSubscriptionError(RemoteEnvError):
    pass


class RemoteEnvServerError(RemoteEnvError):
    pass


class RemoteEnvValidationError(RemoteEnvError, ValueError):
    pass
