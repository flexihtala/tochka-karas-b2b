"""Inventory enums."""

from enum import StrEnum


class ReserveFailureReason(StrEnum):
    """Причина отказа в резервировании конкретного SKU (см. канон b2b-flows.md)."""

    OUT_OF_STOCK = 'OUT_OF_STOCK'  # active_quantity = 0
    INSUFFICIENT_STOCK = 'INSUFFICIENT_STOCK'  # active_quantity > 0, но < requested
    NOT_FOUND = 'NOT_FOUND'  # SKU не существует


class InventoryEventType(StrEnum):
    """Outbox event_type'ы, которые отправляет inventory."""

    SKU_OUT_OF_STOCK = 'SKU_OUT_OF_STOCK'
