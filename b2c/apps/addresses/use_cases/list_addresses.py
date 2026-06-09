from apps.addresses.repositories import AddressRepository
from apps.addresses.schemas.response import AddressResponseSchema
from shared.auth_lib import AuthenticatedUserSchema


class ListAddressesUseCase:
    """GET /buyers/me/addresses — список адресов покупателя.

    buyer_id берётся из JWT.
    """

    def __init__(self, address_repository: AddressRepository):
        self.address_repository = address_repository

    async def __call__(self, current_user: AuthenticatedUserSchema) -> list[AddressResponseSchema]:
        addresses = await self.address_repository.list_by_buyer(current_user.id)
        return [AddressResponseSchema.model_validate(address) for address in addresses]
