from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query

from apps.auth.schemas import ErrorResponseSchema
from apps.queue.use_cases import ClaimTicketUseCase, ListQueueUseCase
from apps.tickets.enums import TicketStatus
from apps.tickets.schemas import TicketListResponseSchema, TicketResponseSchema
from shared.auth_lib import AuthenticatedUserSchema, get_current_user

router = APIRouter(prefix='/queue')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


@router.get(
    '',
    response_model=TicketListResponseSchema,
    responses=error_responses,
)
@inject
async def list_queue(
    use_case: FromDishka[ListQueueUseCase],
    current_user: AuthenticatedUserSchema = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: TicketStatus | None = Query(default=None),
) -> TicketListResponseSchema:
    """Список тикетов очереди. Доступно модератору и админу."""
    _ = current_user
    return await use_case(limit=limit, offset=offset, status=status)


@router.post(
    '/claim',
    response_model=TicketResponseSchema,
    responses=error_responses,
)
@inject
async def claim_ticket(
    use_case: FromDishka[ClaimTicketUseCase],
    current_user: AuthenticatedUserSchema = Depends(get_current_user),
) -> TicketResponseSchema:
    """Взять следующий PENDING-тикет. SELECT FOR UPDATE SKIP LOCKED предотвращает гонки."""
    return await use_case(current_user.id)
