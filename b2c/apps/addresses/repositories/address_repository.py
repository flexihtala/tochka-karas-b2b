from uuid import UUID

from sqlalchemy import select, update

from apps.addresses.models import Address
from apps.addresses.schemas.db import AddressCreateSchema, AddressReadSchema, AddressUpdateSchema
from shared.db import DBCrudRepository


class AddressRepository(DBCrudRepository[Address, AddressCreateSchema, AddressReadSchema, AddressUpdateSchema]):
    async def list_by_buyer(self, buyer_id: UUID) -> list[AddressReadSchema]:
        query = select(Address).where(Address.buyer_id == buyer_id).order_by(Address.created_at.asc())

        async with self.session_manager.get_session() as session:
            models = (await session.execute(query)).scalars().all()

        return [self.model_validate(model) for model in models]

    async def unset_default_for_buyer(self, buyer_id: UUID, except_id: UUID | None = None) -> None:
        """Атомарно снимает is_default со всех адресов покупателя.

        except_id — если задан, этот адрес исключается (например, при установке его как дефолтного).
        """
        query = update(Address).where(Address.buyer_id == buyer_id, Address.is_default.is_(True))
        if except_id is not None:
            query = query.where(Address.id != except_id)
        query = query.values(is_default=False)

        async with self.session_manager.get_session() as session:
            await session.execute(query)
