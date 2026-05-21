from enum import StrEnum

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query

from apps.auth.schemas import ErrorResponseSchema
from apps.stats.schemas import (
    ModeratorStatsResponseSchema,
    StatsOverviewResponseSchema,
)
from apps.stats.use_cases import ModeratorsStatsUseCase, OverviewStatsUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole, require_role

router = APIRouter(prefix='/stats', tags=['Stats'])


class StatsPeriodEnum(StrEnum):
    TODAY = 'today'
    WEEK = 'week'
    MONTH = 'month'


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
    period: StatsPeriodEnum = Query(default=StatsPeriodEnum.TODAY),
) -> StatsOverviewResponseSchema:
    """Сводка по тикетам. Доступно модераторам и админам.

    period (today|week|month, default today) — задел на агрегацию за период (M4).
    """
    _ = current_user
    return await use_case(period=period.value)


@router.get(
    '/moderators',
    response_model=list[ModeratorStatsResponseSchema],
    responses=error_responses,
)
@inject
async def get_moderators(
    use_case: FromDishka[ModeratorsStatsUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.MODERATOR, UserRole.ADMIN)),
    period: StatsPeriodEnum = Query(default=StatsPeriodEnum.WEEK),
) -> list[ModeratorStatsResponseSchema]:
    """Per-moderator аггрегаты. Доступно модераторам и админам.

    period (today|week|month, default week) — задел на агрегацию за период (M4).
    """
    _ = current_user
    return await use_case(period=period.value)
