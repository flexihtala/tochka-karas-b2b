"""Общие типы для всей платформы."""

from enum import StrEnum


class ServiceName(StrEnum):
    """Идентификаторы сервисов NeoMarket."""

    B2B = 'b2b'
    MODERATION = 'moderation'
    B2C = 'b2c'


class ServiceKeyDirection(StrEnum):
    """4 направления service-to-service auth.

    Имя направления = `<отправитель>_to_<получатель>`. Каждый ключ конфигурируется
    отдельной env-переменной (например, B2B_TO_MOD_KEY).
    """

    B2B_TO_MOD = 'b2b_to_mod'
    MOD_TO_B2B = 'mod_to_b2b'
    B2C_TO_B2B = 'b2c_to_b2b'
    B2B_TO_B2C = 'b2b_to_b2c'
