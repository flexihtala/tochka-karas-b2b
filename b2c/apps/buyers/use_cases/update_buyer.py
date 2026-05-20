from apps.auth.repositories import UserRepository
from apps.auth.schemas.user import UserUpdateSchema
from apps.buyers.errors import BuyerNotFoundError
from apps.buyers.schemas.request import BuyerUpdateRequestSchema
from apps.buyers.schemas.response import BuyerResponseSchema
from shared.auth_lib import AuthenticatedUserSchema


class UpdateBuyerUseCase:
    """PATCH /buyers/me — частичное обновление профиля.

    Бизнес-правила:
    - id берётся из JWT, не из тела/URL (защита от IDOR).
    - email и password здесь не обновляются (отдельные endpoint'ы).
    """

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def __call__(
        self,
        data: BuyerUpdateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> BuyerResponseSchema:
        update_payload = data.model_dump(exclude_unset=True)
        if update_payload:
            updated = await self.user_repository.update(UserUpdateSchema(id=current_user.id, **update_payload))
            if updated is None:
                raise BuyerNotFoundError()
            user = updated
        else:
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
