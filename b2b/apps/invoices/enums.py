from enum import StrEnum


class InvoiceStatus(StrEnum):
    """Статусы накладной (см. neomarket-protocols InvoiceStatus).

    CREATED — накладная только что создана продавцом, ожидает приёмки.
    PARTIALLY_ACCEPTED — приёмка завершена, часть позиций не доехала.
    ACCEPTED — все позиции приняты в полном объёме.
    CANCELLED — накладная отменена.
    """

    CREATED = 'CREATED'
    PARTIALLY_ACCEPTED = 'PARTIALLY_ACCEPTED'
    ACCEPTED = 'ACCEPTED'
    CANCELLED = 'CANCELLED'
