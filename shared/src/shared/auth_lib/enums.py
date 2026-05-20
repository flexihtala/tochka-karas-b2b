from enum import StrEnum, auto


class UserRole(StrEnum):
    """Роли пользователей NeoMarket. В каждом сервисе используется подмножество.

    - SELLER — продавец в B2B
    - BUYER — покупатель в B2C
    - MODERATOR — модератор в Moderation
    - ADMIN — суперпользователь, общий для всех сервисов
    """

    SELLER = auto()
    BUYER = auto()
    MODERATOR = auto()
    ADMIN = auto()
