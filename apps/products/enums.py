from enum import StrEnum, auto


class ProductStatus(StrEnum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name

    CREATED = auto()
    ON_MODERATION = auto()
    MODERATED = auto()
    BLOCKED = auto()
    HARD_BLOCKED = auto()
