from uuid import UUID

from sqlalchemy import select, update

from apps.payment_methods.models import PaymentMethod
from apps.payment_methods.schemas.db import (
    PaymentMethodCreateSchema,
    PaymentMethodReadSchema,
    PaymentMethodUpdateSchema,
)
from shared.db import DBCrudRepository


class PaymentMethodRepository(
    DBCrudRepository[PaymentMethod, PaymentMethodCreateSchema, PaymentMethodReadSchema, PaymentMethodUpdateSchema]
):
    async def list_by_buyer(self, buyer_id: UUID) -> list[PaymentMethodReadSchema]:
        query = select(PaymentMethod).where(PaymentMethod.buyer_id == buyer_id).order_by(PaymentMethod.created_at.asc())

        async with self.session_manager.get_session() as session:
            models = (await session.execute(query)).scalars().all()

        return [self.model_validate(model) for model in models]

    async def unset_default_for_buyer(self, buyer_id: UUID, except_id: UUID | None = None) -> None:
        """Атомарно снимает is_default со всех платёжных методов покупателя."""
        query = update(PaymentMethod).where(PaymentMethod.buyer_id == buyer_id, PaymentMethod.is_default.is_(True))
        if except_id is not None:
            query = query.where(PaymentMethod.id != except_id)
        query = query.values(is_default=False)

        async with self.session_manager.get_session() as session:
            await session.execute(query)
