from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from apps.auth.schemas import ErrorResponseSchema
from apps.events.schemas import (
    EventAcceptedResponseSchema,
    IncomingB2BEventSchema,
)
from apps.events.use_cases import HandleB2BEventUseCase
from settings import settings
from shared.inbox import make_verify_service_key
from shared.types import ServiceKeyDirection

router = APIRouter(prefix='/b2b/events', tags=['B2B Events'])


_verify_b2b_to_mod = make_verify_service_key(
    direction=ServiceKeyDirection.B2B_TO_MOD,
    expected_key=settings.b2b_to_mod_key,
)


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
    409: {'model': ErrorResponseSchema},
}


@router.post(
    '',
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EventAcceptedResponseSchema,
    responses=error_responses,
    dependencies=[Depends(_verify_b2b_to_mod)],
)
@inject
async def receive_b2b_event(
    event: IncomingB2BEventSchema,
    use_case: FromDishka[HandleB2BEventUseCase],
) -> EventAcceptedResponseSchema:
    """POST /api/v1/b2b/events — приём событий о товарах от B2B-сервиса.

    Авторизация: X-Service-Key (направление b2b_to_mod).
    Идемпотентность: idempotency_key фиксируется в processed_events
    (UNIQUE(sender_service, idempotency_key)) ДО мутаций тикетов; повтор события
    с тем же ключом (TTL 24h) → 409 DUPLICATE_EVENT без побочных эффектов.

    - PRODUCT_CREATED → новый тикет (PENDING).
    - PRODUCT_EDITED  → сброс активного тикета в PENDING; HARD_BLOCKED игнорируется.
    - PRODUCT_DELETED → архивирование всех тикетов товара (включая HARD_BLOCKED).
    """
    return await use_case(event)
