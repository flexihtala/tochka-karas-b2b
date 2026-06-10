from pydantic import BaseModel


class ProductEventResponseSchema(BaseModel):
    """Ответ POST /api/v1/events/product — см. canon Flow B2C-12."""

    accepted: bool = True
