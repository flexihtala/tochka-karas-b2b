from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.blocking_reasons.schemas import (
    BlockingReasonCreateRequestSchema,
    BlockingReasonResponseSchema,
    BlockingReasonUpdateRequestSchema,
)
from apps.blocking_reasons.use_cases import (
    CreateBlockingReasonUseCase,
    DeleteBlockingReasonUseCase,
    ListBlockingReasonsUseCase,
    UpdateBlockingReasonUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema, UserRole, get_current_user, require_role

router = APIRouter(prefix='/blocking-reasons')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
    409: {'model': ErrorResponseSchema},
}


@router.get(
    '',
    response_model=list[BlockingReasonResponseSchema],
    responses=error_responses,
)
@inject
async def list_blocking_reasons(
    use_case: FromDishka[ListBlockingReasonsUseCase],
    current_user: AuthenticatedUserSchema = Depends(get_current_user),
    hard_block: bool | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> list[BlockingReasonResponseSchema]:
    """Список причин блокировки — массив прямо в response (по спеке).

    Доступен любому аутентифицированному модератору/админу.
    """
    _ = current_user
    return await use_case(hard_block=hard_block, is_active=is_active)


@router.post(
    '',
    status_code=status.HTTP_201_CREATED,
    response_model=BlockingReasonResponseSchema,
    responses=error_responses,
)
@inject
async def create_blocking_reason(
    data: BlockingReasonCreateRequestSchema,
    use_case: FromDishka[CreateBlockingReasonUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.ADMIN)),
) -> BlockingReasonResponseSchema:
    """Admin-only: добавить причину блокировки в справочник."""
    _ = current_user
    return await use_case(data)


@router.patch(
    '/{reason_id}',
    response_model=BlockingReasonResponseSchema,
    responses=error_responses,
)
@inject
async def update_blocking_reason(
    reason_id: UUID,
    data: BlockingReasonUpdateRequestSchema,
    use_case: FromDishka[UpdateBlockingReasonUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.ADMIN)),
) -> BlockingReasonResponseSchema:
    """Admin-only: частичное обновление причины (включая deactivation через is_active=false)."""
    _ = current_user
    return await use_case(reason_id, data)


@router.delete(
    '/{reason_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses,
)
@inject
async def delete_blocking_reason(
    reason_id: UUID,
    use_case: FromDishka[DeleteBlockingReasonUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.ADMIN)),
) -> Response:
    """Admin-only: soft-delete (is_active=false) — чтобы не сломать FK у старых тикетов."""
    _ = current_user
    await use_case(reason_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
