"""Интеграция с B2B через РЕАЛЬНЫЙ ServiceClient + httpx.MockTransport.

Мокается только транспорт (httpx), весь остальной код ServiceClient (заголовки,
разбор JSON, ServiceClientError) выполняется как в проде. Проверяем:
- POST /api/v1/public/products/batch формируется корректно (path + body product_ids).
- ServiceClient прокидывает X-Service-Key.
- payload-массив разбирается в обогащённую корзину.
- B2B недоступен (5xx) → B2BUnavailableError (503).
"""

import json as json_lib
from typing import Any
from uuid import uuid4

import httpx
import pytest

from apps.cart.enums import UnavailableReason
from apps.cart.errors import B2BUnavailableError
from apps.cart.schemas.db import CartCreateSchema, CartItemCreateSchema
from apps.cart.use_cases import GetCartUseCase
from shared.http_clients import ServiceClient
from tests.cart.fakes import FakeCartItemRepository, FakeCartRepository, make_product, make_sku


@pytest.mark.anyio
async def test_get_cart_calls_b2b_batch_endpoint_with_service_key():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    sku_id = uuid4()
    product_id = uuid4()
    cart = await cart_repo.create(CartCreateSchema(user_id=user_id))
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_id, product_id=product_id, quantity=2))

    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured['method'] = request.method
        captured['path'] = request.url.path
        captured['service_key'] = request.headers.get('X-Service-Key')
        captured['body'] = json_lib.loads(request.content)
        return httpx.Response(
            200,
            json=[
                make_product(
                    product_id=product_id,
                    title='Foo',
                    skus=[make_sku(sku_id=sku_id, product_id=product_id, name='S', price=250, active_quantity=7)],
                )
            ],
        )

    client = ServiceClient(
        base_url='http://b2b.test',
        service_key='secret-key',
        transport=httpx.MockTransport(handler),
    )
    use_case = GetCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=client)

    result = await use_case(user_id=user_id, session_id=None)

    assert captured['method'] == 'POST'
    assert captured['path'] == '/api/v1/public/products/batch'
    assert captured['service_key'] == 'secret-key'
    assert captured['body'] == {'product_ids': [str(product_id)]}

    assert len(result.items) == 1
    assert result.items[0].name == 'Foo S'
    assert result.items[0].unit_price == 250
    assert result.items[0].line_total == 500  # 250 * 2
    assert result.subtotal == 500
    assert result.is_valid is True


@pytest.mark.anyio
async def test_get_cart_missing_product_in_b2b_response_marks_as_deleted():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    sku_id = uuid4()
    product_id = uuid4()
    cart = await cart_repo.create(CartCreateSchema(user_id=user_id))
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_id, product_id=product_id, quantity=3))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])  # B2B ничего не вернул (товар скрыт/удалён)

    client = ServiceClient(base_url='http://b2b.test', service_key='k', transport=httpx.MockTransport(handler))
    use_case = GetCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=client)

    result = await use_case(user_id=user_id, session_id=None)

    assert len(result.items) == 1
    assert result.items[0].is_available is False
    assert result.items[0].unavailable_reason == UnavailableReason.PRODUCT_DELETED
    assert result.items[0].line_total == 0
    assert result.subtotal == 0
    assert result.is_valid is False


@pytest.mark.anyio
async def test_get_cart_raises_503_when_b2b_unavailable():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    cart = await cart_repo.create(CartCreateSchema(user_id=user_id))
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=uuid4(), product_id=uuid4(), quantity=1))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={'code': 'DOWN'})

    client = ServiceClient(base_url='http://b2b.test', service_key='k', transport=httpx.MockTransport(handler))
    use_case = GetCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=client)

    with pytest.raises(B2BUnavailableError):
        await use_case(user_id=user_id, session_id=None)
