from apps.auth.repositories import UserRepository
from apps.buyers.errors import BuyerNotFoundError
from apps.buyers.schemas.response import BuyerResponseSchema
from shared.auth_lib import AuthenticatedUserSchema


class GetBuyerUseCase:
    """GET /buyers/me — возврат профиля текущего покупателя по JWT.id."""

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def __call__(self, current_user: AuthenticatedUserSchema) -> BuyerResponseSchema:
        user = await self.user_repository.get_or_none(current_user.id)
        if user is None:
            raise BuyerNotFoundError()

        return BuyerResponseSchema(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
