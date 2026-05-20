from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Header, Request, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.cart.errors import GuestSessionRequiredError, MissingCartIdentityError
from apps.cart.schemas.request import CartItemAddRequestSchema, CartItemUpdateRequestSchema
from apps.cart.schemas.response import CartItemResponseSchema, CartResponseSchema
from apps.cart.use_cases import (
    AddItemUseCase,
    GetCartUseCase,
    MergeCartUseCase,
    RemoveItemUseCase,
    UpdateItemUseCase,
)
from shared.auth_lib import UserRole

router = APIRouter(prefix='/cart')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


def _identity(request: Request, session_id: str | None) -> tuple[UUID | None, str | None]:
    """Возвращает (user_id, session_id) — ровно один из них не None.

    Правила (см. flow B2C-8 §IDOR):
    - Авторизован как BUYER → user_id из JWT, session_id ИГНОРИРУЕТСЯ.
    - Не авторизован → требуется X-Session-Id.
    - Авторизован не как BUYER → 401 (нет покупательской идентичности).
    """
    user = getattr(request.state, 'user', None)
    if user is not None and user.role == UserRole.BUYER:
        return user.id, None
    if session_id:
        return None, session_id
    raise MissingCartIdentityError()


@router.get('', response_model=CartResponseSchema, responses=error_responses)
@inject
async def get_cart(
    request: Request,
    use_case: FromDishka[GetCartUseCase],
    x_session_id: str | None = Header(default=None, alias='X-Session-Id'),
) -> CartResponseSchema:
    user_id, session_id = _identity(request, x_session_id)
    return await use_case(user_id=user_id, session_id=session_id)


@router.post('/items', response_model=CartResponseSchema, responses=error_responses)
@inject
async def add_item(
    request: Request,
    data: CartItemAddRequestSchema,
    response: Response,
    add_use_case: FromDishka[AddItemUseCase],
    get_use_case: FromDishka[GetCartUseCase],
    x_session_id: str | None = Header(default=None, alias='X-Session-Id'),
) -> CartResponseSchema:
    user_id, session_id = _identity(request, x_session_id)
    result = await add_use_case(data, user_id=user_id, session_id=session_id)
    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    return await get_use_case(user_id=user_id, session_id=session_id)


@router.patch('/items/{item_id}', response_model=CartItemResponseSchema, responses=error_responses)
@inject
async def update_item(
    request: Request,
    item_id: UUID,
    data: CartItemUpdateRequestSchema,
    use_case: FromDishka[UpdateItemUseCase],
    x_session_id: str | None = Header(default=None, alias='X-Session-Id'),
) -> CartItemResponseSchema:
    user_id, session_id = _identity(request, x_session_id)
    item = await use_case(item_id, data, user_id=user_id, session_id=session_id)
    return CartItemResponseSchema(
        id=item.id,
        sku_id=item.sku_id,
        quantity=item.quantity,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.delete('/items/{item_id}', status_code=status.HTTP_204_NO_CONTENT, responses=error_responses)
@inject
async def delete_item(
    request: Request,
    item_id: UUID,
    use_case: FromDishka[RemoveItemUseCase],
    x_session_id: str | None = Header(default=None, alias='X-Session-Id'),
) -> Response:
    user_id, session_id = _identity(request, x_session_id)
    await use_case(item_id, user_id=user_id, session_id=session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/merge', response_model=CartResponseSchema, responses=error_responses)
@inject
async def merge_cart(
    request: Request,
    merge_use_case: FromDishka[MergeCartUseCase],
    get_use_case: FromDishka[GetCartUseCase],
    x_session_id: str | None = Header(default=None, alias='X-Session-Id'),
) -> CartResponseSchema:
    user = getattr(request.state, 'user', None)
    if user is None or user.role != UserRole.BUYER:
        raise MissingCartIdentityError()
    if not x_session_id:
        raise GuestSessionRequiredError()
    await merge_use_case(user_id=user.id, session_id=x_session_id)
    return await get_use_case(user_id=user.id, session_id=None)
