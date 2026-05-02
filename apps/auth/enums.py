from enum import StrEnum, auto


class UserRole(StrEnum):
    SELLER = auto()
    BUYER = auto()
    MODERATOR = auto()
    ADMIN = auto()
