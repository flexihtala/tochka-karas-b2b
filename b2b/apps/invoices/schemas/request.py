from uuid import UUID

from pydantic import BaseModel, Field


class InvoiceItemCreateRequestSchema(BaseModel):
    sku_id: UUID
    quantity: int = Field(ge=1)


class InvoiceCreateRequestSchema(BaseModel):
    """Тело запроса POST /api/v1/invoices.

    Согласно протоколу `InvoiceCreate` минимум 1 позиция обязательна.
    Проверка пустого `items` дополнительно выполняется на уровне use-case
    (см. ADR в PR-описании) — это единая точка применения бизнес-правила,
    защищающая от обхода через альтернативные входы.
    """

    items: list[InvoiceItemCreateRequestSchema] = Field(default_factory=list)
