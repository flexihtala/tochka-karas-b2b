from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from apps.auth.schemas import ErrorResponseSchema
from apps.events.schemas import (
    EventAcceptedResponseSchema,
    IncomingB2BEventSchema,
)
from apps.events.use_cases import HandleB2BEventUseCase
from apps.inbox.models import ProcessedEvent
from settings import settings
from shared.db import SessionManager
from shared.inbox import IdempotentHandler, make_verify_service_key
from shared.types import ServiceKeyDirection, ServiceName

router = APIRouter(prefix='/b2b/events', tags=['B2B Events'])


_verify_b2b_to_mod = make_verify_service_key(
    direction=ServiceKeyDirection.B2B_TO_MOD,
    expected_key=settings.b2b_to_mod_key,
)


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
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
    idempotent_handler: FromDishka[IdempotentHandler[ProcessedEvent]],
    session_manager: FromDishka[SessionManager],
) -> JSONResponse:
    """POST /api/v1/b2b/events — приём событий о товарах от B2B-сервиса.

    Авторизация: X-Service-Key (направление b2b_to_mod).
    Идемпотентность: по (sender_service=b2b, idempotency_key) — повторный вызов
    вернёт кешированный результат без повторного выполнения use-case.
    """

    async with session_manager.get_session() as session:
        result = await idempotent_handler.handle(
            session=session,
            sender=ServiceName.B2B,
            key=event.idempotency_key,
            handler=lambda: use_case(event),
            result_to_payload=lambda r: r.model_dump(mode='json') if isinstance(r, EventAcceptedResponseSchema) else r,
        )
    # IdempotentHandler возвращает либо ResultT (использован handler), либо dict из cached.
    if isinstance(result, EventAcceptedResponseSchema):
        payload = result.model_dump(mode='json')
    else:
        payload = result  # cached dict
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=payload)
