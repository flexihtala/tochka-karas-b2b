from uuid import UUID

from pydantic import BaseModel, Field


class FieldReportSchema(BaseModel):
    """FieldReport — детальное замечание по полю товара. M2 пробрасывает его в payload
    события BLOCKED для B2B, чтобы продавец видел конкретику.

    field_name — допустимые значения из канона:
    title, description, product_images, category, sku_name, sku_image, sku_price.
    """

    field_name: str = Field(min_length=1, max_length=64)
    sku_id: UUID | None = None
    comment: str = Field(min_length=1, max_length=1000)


class BlockTicketRequestSchema(BaseModel):
    """POST /api/v1/tickets/{id}/block — тело запроса.

    hard_block выводится из выбранной причины (поле blocking_reason.hard_block), а не
    из request body — модератор не может «переопределить» жёсткость через API.
    """

    blocking_reason_id: UUID
    moderator_comment: str = Field(min_length=1, max_length=2000)
    field_reports: list[FieldReportSchema] | None = None
