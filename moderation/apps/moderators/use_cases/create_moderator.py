from apps.auth.repositories import ModeratorRepository
from apps.auth.schemas.moderator import ModeratorCreateSchema
from apps.moderators.errors import EmailAlreadyExistsError
from apps.moderators.schemas.request import ModeratorCreateRequestSchema
from apps.moderators.schemas.response import ModeratorResponseSchema
from shared.auth_lib import PasswordHasher


class CreateModeratorUseCase:
    """POST /api/v1/moderators — admin-only создание модератора/админа.

    Bootstrap-admin создаётся вручную (миграция/seed), не через этот эндпоинт.
    """

    def __init__(
        self,
        moderator_repository: ModeratorRepository,
        password_hasher: PasswordHasher,
    ):
        self.moderator_repository = moderator_repository
        self.password_hasher = password_hasher

    async def __call__(self, data: ModeratorCreateRequestSchema) -> ModeratorResponseSchema:
        if await self.moderator_repository.get_by_email(data.email):
            raise EmailAlreadyExistsError()

        moderator = await self.moderator_repository.create(
            ModeratorCreateSchema(
                email=data.email,
                password_hash=self.password_hasher.hash(data.password),
                role=data.role,
                first_name=data.first_name,
                last_name=data.last_name,
            )
        )
        return ModeratorResponseSchema.model_validate(moderator)
