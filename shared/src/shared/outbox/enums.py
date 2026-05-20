from enum import StrEnum


class OutboxStatus(StrEnum):
    PENDING = 'PENDING'
    SENT = 'SENT'
    FAILED = 'FAILED'
