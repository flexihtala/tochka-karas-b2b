from dataclasses import dataclass
from uuid import UUID

import httpx

from apps.cart.errors import B2BUnavailableError, InsufficientStockError, SkuUnavailableError
from apps.cart.repositories import CartItemRepository, CartRepository
from apps.cart.schemas.db import (
    CartCreateSchema,
    CartItemCreateSchema,
    CartItemReadSchema,
    CartItemUpdateSchema,
)
from apps.cart.schemas.request import CartItemAddRequestSchema
from shared.http_clients import ServiceClient, ServiceClientError


@dataclass
class AddItemResult:
    """Результат AddItemUseCase: позиция + флаг "была ли уже"."""

    item: CartItemReadSchema
    created: bool


class AddItemUseCase:
    """POST /api/v1/cart/items — добавить SKU в корзину.

    Бизнес-правила (см. b2c-cart-flows.md, Flow B2C-8, edge case #8):
    - Перед добавлением валидируем SKU в B2B `GET /api/v1/public/skus/{sku_id}`:
        - 404 от B2B → SkuUnavailableError (404, товар не виден/удалён/заблокирован).
        - сеть/5xx → B2BUnavailableError (503), не можем проверить наличие.
        - requested_total > active_quantity → InsufficientStockError (409).
    - Lazy reserve: на этом шаге НЕ резервируем остатки в B2B — только читаем.
    - Если SKU уже есть в корзине — quantity += body.quantity (created=False, 200).
    - Если нет — создаётся новая позиция (created=True, 201).
    - Корзина создаётся лениво, если её ещё не существует для данной идентичности.
    - Идентификация: user_id из JWT ИЛИ session_id из X-Session-Id (взаимоисключающе).
    """

    def __init__(
        self,
        cart_repository: CartRepository,
        cart_item_repository: CartItemRepository,
        b2b_client: ServiceClient,
    ):
        self.cart_repository = cart_repository
        self.cart_item_repository = cart_item_repository
        self.b2b_client = b2b_client

    async def __call__(
        self,
        data: CartItemAddRequestSchema,
        *,
        user_id: UUID | None,
        session_id: str | None,
    ) -> AddItemResult:
        sku = await self._fetch_sku(data.sku_id)
        product_id = UUID(str(sku['product_id']))
        active_quantity = int(sku.get('active_quantity', 0))
        unit_price = int(sku['price']) if sku.get('price') is not None else None

        cart = await self._get_or_create_cart(user_id=user_id, session_id=session_id)

        existing = await self.cart_item_repository.get_by_cart_and_sku(cart.id, data.sku_id)
        new_total = (existing.quantity if existing is not None else 0) + data.quantity
        if active_quantity < new_total:
            raise InsufficientStockError()

        if existing is not None:
            updated = await self.cart_item_repository.update(
                CartItemUpdateSchema(
                    id=existing.id,
                    product_id=product_id,
                    quantity=new_total,
                )
            )
            assert updated is not None
            return AddItemResult(item=updated, created=False)

        created = await self.cart_item_repository.create(
            CartItemCreateSchema(
                cart_id=cart.id,
                sku_id=data.sku_id,
                product_id=product_id,
                quantity=data.quantity,
            )
        )
        # unit_price_at_add не хранится в БД (опционально) — он берётся из B2B при чтении;
        # здесь оставляем поведение «не сохраняем» (см. quest DoD: storage опционально).
        _ = unit_price
        return AddItemResult(item=created, created=True)

    async def _fetch_sku(self, sku_id: UUID) -> dict:
        """Читает SKU из B2B-витрины. 404 → SkuUnavailableError, иначе сеть/5xx → 503."""
        try:
            return await self.b2b_client.get(f'/api/v1/public/skus/{sku_id}')
        except ServiceClientError as exc:
            if exc.status_code == 404:
                raise SkuUnavailableError() from exc
            raise B2BUnavailableError() from exc
        except httpx.HTTPError as exc:
            raise B2BUnavailableError() from exc

    async def _get_or_create_cart(self, *, user_id: UUID | None, session_id: str | None):
        if user_id is not None:
            cart = await self.cart_repository.get_by_user(user_id)
            if cart is not None:
                return cart
            return await self.cart_repository.create(CartCreateSchema(user_id=user_id))

        assert session_id is not None
        cart = await self.cart_repository.get_by_session(session_id)
        if cart is not None:
            return cart
        return await self.cart_repository.create(CartCreateSchema(session_id=session_id))
