from typing import Protocol


class DBSettingsProtocol(Protocol):
    """Минимум, что должен иметь сервисный Settings для работы с shared/db."""

    database_url: str
