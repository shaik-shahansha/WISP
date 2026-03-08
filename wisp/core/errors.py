"""WISP core errors."""


class WispError(Exception):
    """Base exception for all WISP errors."""


class ConfigurationError(WispError):
    """Raised when configuration is invalid or missing."""


class HardwareError(WispError):
    """Raised when hardware interaction fails."""


class AIError(WispError):
    """Raised when the AI provider returns an error."""


class TransportError(WispError):
    """Raised when a transport (Telegram, HTTP, etc.) fails."""


class CapabilityError(WispError):
    """Raised when a capability cannot be resolved or executed."""
