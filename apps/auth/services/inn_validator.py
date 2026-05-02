class InnValidator:
    @staticmethod
    def is_valid(value: str) -> bool:
        if not value.isdigit() or len(value) not in {10, 12}:
            return False
        if len(value) == 10:
            return InnValidator._checksum_10(value)
        return InnValidator._checksum_12(value)

    @staticmethod
    def _checksum_10(value: str) -> bool:
        weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
        control = sum(int(value[index]) * weight for index, weight in enumerate(weights)) % 11 % 10
        return control == int(value[9])

    @staticmethod
    def _checksum_12(value: str) -> bool:
        weights_11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
        weights_12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
        control_11 = sum(int(value[index]) * weight for index, weight in enumerate(weights_11)) % 11 % 10
        control_12 = sum(int(value[index]) * weight for index, weight in enumerate(weights_12)) % 11 % 10
        return control_11 == int(value[10]) and control_12 == int(value[11])
