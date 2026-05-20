"""Входящие события от внешних сервисов.

US-B2B-09: POST /api/v1/events/moderation — приём результата модерации
от Moderation-сервиса. Авторизация: X-Service-Key c direction `mod_to_b2b`.

Идемпотентность обеспечивается на уровне use-case через
shared.inbox.IdempotentHandler (см. apps/events/use_cases/apply_moderation_event.py).
Повторный вызов с тем же idempotency_key возвращает cached-ответ без побочных
эффектов.
"""

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.events.schemas import ModerationEventRequestSchema
from apps.events.use_cases import ApplyModerationEventUseCase
from settings import settings
from shared.inbox import make_verify_service_key
from shared.types import ServiceKeyDirection

router = APIRouter(prefix='/events')


verify_mod_to_b2b = make_verify_service_key(ServiceKeyDirection.MOD_TO_B2B, settings.mod_to_b2b_key)


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


@router.post(
    '/moderation',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses,
    dependencies=[Depends(verify_mod_to_b2b)],
)
@inject
async def apply_moderation_event(
    data: ModerationEventRequestSchema,
    use_case: FromDishka[ApplyModerationEventUseCase],
) -> Response:
    await use_case(data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
