from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from apps.auth.schemas import ErrorResponseSchema
from apps.moderators.schemas import (
    ModeratorCreateRequestSchema,
    ModeratorListResponseSchema,
    ModeratorResponseSchema,
    ModeratorUpdateRequestSchema,
)
from apps.moderators.use_cases import (
    CreateModeratorUseCase,
    GetModeratorUseCase,
    ListModeratorsUseCase,
    UpdateModeratorUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema, UserRole, get_current_user, require_role

router = APIRouter(prefix='/moderators')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
    409: {'model': ErrorResponseSchema},
}


@router.get(
    '',
    response_model=ModeratorListResponseSchema,
    responses=error_responses,
)
@inject
async def list_moderators(
    use_case: FromDishka[ListModeratorsUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.ADMIN)),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    is_active: bool | None = Query(default=None),
) -> ModeratorListResponseSchema:
    """Admin-only: список модераторов с пагинацией и фильтром по активности."""
    _ = current_user
    return await use_case(limit=limit, offset=offset, is_active=is_active)


@router.get(
    '/me',
    response_model=ModeratorResponseSchema,
    responses=error_responses,
)
@inject
async def get_me(
    use_case: FromDishka[GetModeratorUseCase],
    current_user: AuthenticatedUserSchema = Depends(get_current_user),
) -> ModeratorResponseSchema:
    """Профиль текущего модератора (доступен любой аутентифицированной роли)."""
    return await use_case(current_user.id)


@router.get(
    '/{moderator_id}',
    response_model=ModeratorResponseSchema,
    responses=error_responses,
)
@inject
async def get_moderator(
    moderator_id: UUID,
    use_case: FromDishka[GetModeratorUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.ADMIN)),
) -> ModeratorResponseSchema:
    """Admin-only: карточка модератора."""
    _ = current_user
    return await use_case(moderator_id)


@router.post(
    '',
    status_code=status.HTTP_201_CREATED,
    response_model=ModeratorResponseSchema,
    responses=error_responses,
)
@inject
async def create_moderator(
    data: ModeratorCreateRequestSchema,
    use_case: FromDishka[CreateModeratorUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.ADMIN)),
) -> ModeratorResponseSchema:
    """Admin-only: создание нового модератора/админа. Публичной /register нет — это сознательно."""
    _ = current_user
    return await use_case(data)


@router.patch(
    '/{moderator_id}',
    response_model=ModeratorResponseSchema,
    responses=error_responses,
)
@inject
async def update_moderator(
    moderator_id: UUID,
    data: ModeratorUpdateRequestSchema,
    use_case: FromDishka[UpdateModeratorUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.ADMIN)),
) -> ModeratorResponseSchema:
    """Admin-only: обновление модератора."""
    _ = current_user
    return await use_case(moderator_id, data)
