class TelegramClientError(Exception):
    """Base error for Telegram client failures."""


class TelegramConfigurationError(TelegramClientError):
    """Raised when the Telegram client configuration is invalid."""


class TelegramWorkspaceNotRegisteredError(TelegramClientError):
    """Raised when a workspace has no Telegram bot registered."""


class TelegramPermissionError(TelegramClientError):
    """Raised when a workspace attempts an action without sufficient permissions."""


class TelegramChannelBindingError(TelegramClientError):
    """Raised when the Telegram channel binding workflow fails."""
