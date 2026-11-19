class KinBeaconError(Exception):
    """Base exception for KinBeacon central server."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class EntityNotFoundError(KinBeaconError):
    def __init__(self, entity: str, identifier: str):
        super().__init__(f"{entity} '{identifier}' not found", status_code=404)


class ConflictError(KinBeaconError):
    def __init__(self, message: str):
        super().__init__(message, status_code=409)


class NoActiveAnchorsError(KinBeaconError):
    def __init__(self, message: str = "No active anchors available for search"):
        super().__init__(message, status_code=503)
