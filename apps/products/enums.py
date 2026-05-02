from enum import StrEnum, auto


class ProductStatus(StrEnum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name

    CREATED = auto()
