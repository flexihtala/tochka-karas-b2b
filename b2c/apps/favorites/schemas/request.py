from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AddFavoriteRequestSchema(BaseModel):
    """Тело POST /api/v1/favorites — { product_id }.

    user_id НЕ принимается от клиента: source-of-truth — JWT (защита от IDOR).
    Лишние поля игнорируются (ConfigDict extra='ignore').
    """

    model_config = ConfigDict(extra='ignore')

    product_id: UUID
