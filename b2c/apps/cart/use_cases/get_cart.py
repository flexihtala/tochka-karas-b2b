from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.cart.enums import UnavailableReason
from apps.cart.repositories import CartItemRepository, CartRepository
from apps.cart.schemas.db import CartItemReadSchema, CartReadSchema
from apps.cart.schemas.response import CartItemResponseSchema, CartResponseSchema
from shared.http_clients import ServiceClient, ServiceClientError


class GetCartUseCase:
    """GET /api/v1/cart — корзина с обогащением данных из B2B.

    Алгоритм (см. b2c-cart-flows.md, Flow B2C-8 §"Обогащение из B2B"):
    1. Найти корзину по user_id / session_id.
    2. Если корзины нет — вернуть пустой плейсхолдер (id берётся из идентичности).
    3. Собрать sku_id из cart_items, дёрнуть B2B `GET /api/v1/skus?ids=...`.
    4. Для каждого item:
       - SKU в ответе и available_quantity > 0 → доступна, line_total = unit_price * qty.
       - SKU в ответе, но BLOCKED → unavailable_reason = BLOCKED.
       - SKU в ответе, available_quantity == 0 → unavailable_reason = OUT_OF_STOCK.
       - SKU отсутствует в ответе → unavailable_reason = DELETED.
    5. total_amount = сумма line_total ТОЛЬКО available-позиций.

    Если B2B недоступен — ServiceClientError пробрасывается наружу (FastAPI вернёт 5xx).
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
        *,
        user_id: UUID | None,
        session_id: str | None,
    ) -> CartResponseSchema:
        cart = await self._find_cart(user_id=user_id, session_id=session_id)
        if cart is None:
            return self._empty_cart(user_id=user_id, session_id=session_id)

        items = await self.cart_item_repository.list_by_cart(cart.id)
        if not items:
            return CartResponseSchema(
                id=cart.id,
                user_id=cart.user_id,
                session_id=cart.session_id,
                items=[],
                total_amount=0,
                items_count=0,
                updated_at=cart.updated_at,
            )

        sku_index = await self._fetch_sku_index([item.sku_id for item in items])

        enriched: list[CartItemResponseSchema] = []
        total_amount = 0
        items_count = 0
        for item in items:
            enriched_item = self._enrich(item, sku_index)
            enriched.append(enriched_item)
            items_count += item.quantity
            if enriched_item.unavailable_reason is None:
                total_amount += enriched_item.line_total

        return CartResponseSchema(
            id=cart.id,
            user_id=cart.user_id,
            session_id=cart.session_id,
            items=enriched,
            total_amount=total_amount,
            items_count=items_count,
            updated_at=cart.updated_at,
        )

    async def _find_cart(
        self,
        *,
        user_id: UUID | None,
        session_id: str | None,
    ) -> CartReadSchema | None:
        if user_id is not None:
            return await self.cart_repository.get_by_user(user_id)
        assert session_id is not None
        return await self.cart_repository.get_by_session(session_id)

    @staticmethod
    def _empty_cart(*, user_id: UUID | None, session_id: str | None) -> CartResponseSchema:
        now = datetime.now(UTC)
        return CartResponseSchema(
            id=uuid4(),
            user_id=user_id,
            session_id=session_id,
            items=[],
            total_amount=0,
            items_count=0,
            updated_at=now,
        )

    async def _fetch_sku_index(self, sku_ids: list[UUID]) -> dict[UUID, dict]:
        """Batch-запрос к B2B `GET /api/v1/skus?ids=...` → {sku_id: {price, title, available_quantity, blocked}}.

        Контракт B2B: возвращает только existing SKU (удалённые отсутствуют), каждый
        с полями `id`, `title`, `price` (копейки), `available_quantity`, `blocked` (опц.).
        """
        if not sku_ids:
            return {}

        try:
            payload = await self.b2b_client.get('/api/v1/skus', params={'ids': ','.join(str(s) for s in sku_ids)})
        except ServiceClientError:
            raise

        index: dict[UUID, dict] = {}
        for raw in payload.get('items', []):
            raw_id = raw.get('id') if isinstance(raw, dict) else None
            if raw_id is None:
                continue
            try:
                sku_id = UUID(str(raw_id))
            except ValueError:
                continue
            index[sku_id] = raw
        return index

    @staticmethod
    def _enrich(item: CartItemReadSchema, sku_index: dict[UUID, dict]) -> CartItemResponseSchema:
        raw = sku_index.get(item.sku_id)
        if raw is None:
            return CartItemResponseSchema(
                id=item.id,
                sku_id=item.sku_id,
                quantity=item.quantity,
                title=None,
                unit_price=None,
                available_quantity=None,
                line_total=0,
                unavailable_reason=UnavailableReason.DELETED,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )

        title = raw.get('title')
        unit_price = raw.get('price')
        available_quantity = raw.get('available_quantity')
        is_blocked = bool(raw.get('blocked', False))

        if is_blocked:
            reason: UnavailableReason | None = UnavailableReason.BLOCKED
        elif available_quantity is None or int(available_quantity) <= 0:
            reason = UnavailableReason.OUT_OF_STOCK
        else:
            reason = None

        line_total = 0
        if reason is None and unit_price is not None:
            line_total = int(unit_price) * item.quantity

        return CartItemResponseSchema(
            id=item.id,
            sku_id=item.sku_id,
            quantity=item.quantity,
            title=title,
            unit_price=int(unit_price) if unit_price is not None else None,
            available_quantity=int(available_quantity) if available_quantity is not None else None,
            line_total=line_total,
            unavailable_reason=reason,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
