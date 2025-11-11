"""Custom exceptions for Azoula Smart Hub operations."""


class AzoulaGatewayError(Exception):
    """Base exception for Azoula Smart Hub operations."""

    def __init__(self, message: str, gateway_id: str):
        """Initialize the exception with an optional gateway serial number."""
        super().__init__(message)
        self.gateway_id = gateway_id
