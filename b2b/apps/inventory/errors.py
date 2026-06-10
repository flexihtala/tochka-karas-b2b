"""Доменные ошибки inventory.

`InventoryConflictError` поднимается use-case'ом при провале all-or-nothing
резервирования. error-handler конвертирует его в 409 с телом
`{code: RESERVE_FAILED, message, details: {failed_items: [...]}}`.
"""

from typing import Any

from apps.errors import AppError


class InventoryError(AppError):
    pass


class InventoryConflictError(InventoryError):
    """409 RESERVE_FAILED — хотя бы один SKU не может быть зарезервирован.

    failed_items: список словарей вида `{sku_id, requested, available, reason}`.
    Передаётся в details ответа.
    """

    def __init__(
        self,
        failed_items: list[dict[str, Any]],
        message: str = 'Не удалось зарезервировать SKU',
    ):
        super().__init__(
            code='RESERVE_FAILED',
            message=message,
            status_code=409,
            details={'failed_items': failed_items},
        )
        self.failed_items = failed_items
