from apps.addresses.repositories import AddressRepository
from apps.addresses.schemas.db import AddressCreateSchema
from apps.addresses.schemas.request import AddressCreateRequestSchema
from apps.addresses.schemas.response import AddressResponseSchema
from shared.auth_lib import AuthenticatedUserSchema


class CreateAddressUseCase:
    """POST /buyers/me/addresses — создание адреса.

    Бизнес-правила:
    - buyer_id берётся из JWT (защита от IDOR).
    - При is_default=True сначала снимаются дефолты с других адресов покупателя.
    """

    def __init__(self, address_repository: AddressRepository):
        self.address_repository = address_repository

    async def __call__(
        self,
        data: AddressCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> AddressResponseSchema:
        if data.is_default:
            await self.address_repository.unset_default_for_buyer(current_user.id)

        address = await self.address_repository.create(
            AddressCreateSchema(
                buyer_id=current_user.id,
                country=data.country,
                city=data.city,
                street=data.street,
                postal_code=data.postal_code,
                comment=data.comment,
                is_default=data.is_default,
            )
        )
        return AddressResponseSchema.model_validate(address)
