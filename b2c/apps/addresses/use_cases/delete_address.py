from uuid import UUID

from apps.addresses.errors import AddressNotFoundError
from apps.addresses.repositories import AddressRepository
from shared.auth_lib import AuthenticatedUserSchema


class DeleteAddressUseCase:
    """DELETE /buyers/me/addresses/{address_id}.

    Бизнес-правила:
    - Адрес должен принадлежать current_user — иначе 404.
    """

    def __init__(self, address_repository: AddressRepository):
        self.address_repository = address_repository

    async def __call__(self, address_id: UUID, current_user: AuthenticatedUserSchema) -> None:
        existing = await self.address_repository.get_or_none(address_id)
        if existing is None or existing.buyer_id != current_user.id:
            raise AddressNotFoundError()

        await self.address_repository.delete(address_id)
