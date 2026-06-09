from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.queue.use_cases import ClaimTicketUseCase, ListQueueUseCase
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
    queue_priority: int | None = Query(default=None, ge=1, le=4),
    category_id: UUID | None = Query(default=None),
    seller_id: UUID | None = Query(default=None),
) -> TicketListResponseSchema:
    """Просмотр очереди (только PENDING). Сортировка: queue_priority ASC, created_at ASC."""
    _ = current_user
    return await use_case(
        limit=limit,
        offset=offset,
        queue_priority=queue_priority,
        category_id=category_id,
        seller_id=seller_id,
    )


@router.post(
    '/claim',
    response_model=TicketResponseSchema,
    responses={
        204: {'description': 'Очередь пуста'},
        **error_responses,
    },
)
@inject
async def claim_ticket(
    use_case: FromDishka[ClaimTicketUseCase],
    current_user: AuthenticatedUserSchema = Depends(get_current_user),
) -> Response | TicketResponseSchema:
    """Взять следующий PENDING-тикет. Если очередь пуста — 204 No Content (по спеке)."""
    ticket = await use_case(current_user.id)
    if ticket is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return ticket
