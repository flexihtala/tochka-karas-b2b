from uuid import UUID

from apps.addresses.errors import AddressNotFoundError
from apps.addresses.repositories import AddressRepository
from apps.addresses.schemas.db import AddressUpdateSchema
from apps.addresses.schemas.request import AddressUpdateRequestSchema
from apps.addresses.schemas.response import AddressResponseSchema
from shared.auth_lib import AuthenticatedUserSchema


class UpdateAddressUseCase:
    """PATCH /buyers/me/addresses/{address_id}.

    Бизнес-правила:
    - Адрес должен принадлежать current_user — иначе 404 (наружу не светим существование).
    - При is_default=True снимаем дефолт с остальных адресов покупателя.
    """

    def __init__(self, address_repository: AddressRepository):
        self.address_repository = address_repository

    async def __call__(
        self,
        address_id: UUID,
        data: AddressUpdateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> AddressResponseSchema:
        existing = await self.address_repository.get_or_none(address_id)
        if existing is None or existing.buyer_id != current_user.id:
            raise AddressNotFoundError()

        update_payload = data.model_dump(exclude_unset=True)
        if data.is_default is True:
            await self.address_repository.unset_default_for_buyer(current_user.id, except_id=address_id)

        if not update_payload:
            return AddressResponseSchema.model_validate(existing)

        updated = await self.address_repository.update(AddressUpdateSchema(id=address_id, **update_payload))
        if updated is None:
            raise AddressNotFoundError()
        return AddressResponseSchema.model_validate(updated)
