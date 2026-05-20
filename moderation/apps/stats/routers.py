from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from apps.auth.schemas import ErrorResponseSchema
from apps.stats.schemas import (
    ModeratorStatsResponseSchema,
    StatsOverviewResponseSchema,
)
from apps.stats.use_cases import ModeratorsStatsUseCase, OverviewStatsUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole, require_role

router = APIRouter(prefix='/stats', tags=['Stats'])


error_responses = {
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
}


@router.get(
    '/overview',
    response_model=StatsOverviewResponseSchema,
    responses=error_responses,
)
@inject
async def get_overview(
    use_case: FromDishka[OverviewStatsUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.MODERATOR, UserRole.ADMIN)),
) -> StatsOverviewResponseSchema:
    """Сводка по тикетам. Доступно модераторам и админам."""
    _ = current_user
    return await use_case()


@router.get(
    '/moderators',
    response_model=list[ModeratorStatsResponseSchema],
    responses=error_responses,
)
@inject
async def get_moderators(
    use_case: FromDishka[ModeratorsStatsUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.MODERATOR, UserRole.ADMIN)),
) -> list[ModeratorStatsResponseSchema]:
    """Per-moderator аггрегаты. Доступно модераторам и админам."""
    _ = current_user
    return await use_case()
