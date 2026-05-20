"""Тесты интеграции с B2B через ServiceClient + httpx.MockTransport.

Не дёргаем сеть — используем httpx.MockTransport чтобы убедиться:
- GET /api/v1/skus?ids=... формируется корректно
- ServiceClient прокидывает X-Service-Key заголовок
- payload разбирается в обогащённую корзину
"""

from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from apps.cart.enums import UnavailableReason
from apps.cart.schemas.db import CartItemCreateSchema
from apps.cart.use_cases import GetCartUseCase
from shared.http_clients import ServiceClient
from tests.cart.fakes import FakeCartItemRepository, FakeCartRepository


class _ServiceClientWithTransport(ServiceClient):
    """ServiceClient с httpx.MockTransport вместо реального HTTP."""

    def __init__(self, transport: httpx.MockTransport, service_key: str = 'test-key'):
        super().__init__(base_url='http://b2b.test', service_key=service_key, timeout=5.0)
        self.transport = transport

    async def _request(  # type: ignore[override]
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        url = f'{self.base_url}{path}'
        headers = {'X-Service-Key': self.service_key}
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key

        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
            response = await client.request(method, url, json=json, params=params, headers=headers)

        if response.status_code >= 400:
            raise RuntimeError(f'{method} {path}: {response.status_code}')
        if not response.content:
            return {}
        return response.json()  # type: ignore[no-any-return]


@pytest.mark.anyio
async def test_get_cart_calls_b2b_skus_endpoint_with_service_key():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    sku_id = uuid4()
    cart = await cart_repo.create(_cart_create_schema(user_id=user_id))
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_id, quantity=2))

    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured['path'] = request.url.path
        captured['query'] = dict(request.url.params)
        captured['service_key'] = request.headers.get('X-Service-Key')
        return httpx.Response(
            200,
            json={
                'items': [
                    {'id': str(sku_id), 'title': 'Foo', 'price': 250, 'available_quantity': 7},
                ],
            },
        )

    client = _ServiceClientWithTransport(httpx.MockTransport(handler), service_key='secret-key')
    use_case = GetCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=client)

    result = await use_case(user_id=user_id, session_id=None)

    assert captured['path'] == '/api/v1/skus'
    assert captured['query'] == {'ids': str(sku_id)}
    assert captured['service_key'] == 'secret-key'

    assert len(result.items) == 1
    assert result.items[0].title == 'Foo'
    assert result.items[0].line_total == 500  # 250 * 2
    assert result.total_amount == 500


@pytest.mark.anyio
async def test_get_cart_missing_sku_in_b2b_response_marks_as_deleted():
    cart_repo = FakeCartRepository()
    item_repo = FakeCartItemRepository()
    user_id = uuid4()
    sku_id = uuid4()
    cart = await cart_repo.create(_cart_create_schema(user_id=user_id))
    await item_repo.create(CartItemCreateSchema(cart_id=cart.id, sku_id=sku_id, quantity=3))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'items': []})  # B2B ничего не вернул

    client = _ServiceClientWithTransport(httpx.MockTransport(handler))
    use_case = GetCartUseCase(cart_repository=cart_repo, cart_item_repository=item_repo, b2b_client=client)

    result = await use_case(user_id=user_id, session_id=None)

    assert len(result.items) == 1
    assert result.items[0].unavailable_reason == UnavailableReason.DELETED
    assert result.items[0].line_total == 0
    assert result.total_amount == 0


def _cart_create_schema(user_id: UUID | None = None, session_id: str | None = None):
    from apps.cart.schemas.db import CartCreateSchema

    return CartCreateSchema(user_id=user_id, session_id=session_id)
