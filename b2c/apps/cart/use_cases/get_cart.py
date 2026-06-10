from uuid import UUID

import httpx

from apps.cart.enums import UnavailableReason
from apps.cart.errors import B2BUnavailableError
from apps.cart.repositories import CartItemRepository, CartRepository
from apps.cart.schemas.db import CartItemReadSchema, CartReadSchema
from apps.cart.schemas.response import CartItemResponseSchema, CartResponseSchema, ImageRefSchema
from shared.http_clients import ServiceClient, ServiceClientError


def _pick_image(sku: dict, product: dict) -> ImageRefSchema | None:
    """Первое изображение SKU, иначе первое изображение товара (по списку как есть)."""
    for source in (sku.get('images'), product.get('images')):
        if not source:
            continue
        first = source[0]
        if not isinstance(first, dict):
            continue
        image_id = first.get('id')
        url = first.get('url')
        if image_id is None or url is None:
            continue
        ordering = first.get('ordering')
        try:
            return ImageRefSchema(
                id=UUID(str(image_id)),
                url=str(url),
                ordering=int(ordering) if ordering is not None else 0,
            )
        except ValueError:
            continue
    return None


def enrich_cart(
    cart: CartReadSchema,
    items: list[CartItemReadSchema],
    products_by_id: dict[UUID, dict],
) -> CartResponseSchema:
    """Собирает CartResponseSchema из cart_items + B2B-карточек товаров.

    Маппинг доступности (см. Flow B2C-8 §"Unavailable reasons"):
    - SKU найден в товаре и active_quantity > 0 → доступна, reason None.
    - SKU найден, active_quantity == 0 → is_available False, OUT_OF_STOCK.
    - товар есть, но sku_id не среди product.skus → is_available False, OUT_OF_STOCK.
    - product_id отсутствует в batch-выдаче → is_available False, PRODUCT_DELETED
      (B2B-витрина скрывает причину; точное blocked/on_moderation детектирование
      придёт через события товаров B2B в отдельном квесте).
    Для недоступных позиций line_total = 0 и они не входят в subtotal.
    """
    enriched: list[CartItemResponseSchema] = []
    items_count = 0
    subtotal = 0
    is_valid = True

    for item in items:
        items_count += item.quantity
        enriched_item = _enrich_item(item, products_by_id)
        enriched.append(enriched_item)

        if enriched_item.is_available:
            subtotal += enriched_item.line_total
            if enriched_item.quantity > enriched_item.available_quantity:
                is_valid = False
        else:
            is_valid = False

    return CartResponseSchema(
        items=enriched,
        items_count=items_count,
        subtotal=subtotal,
        is_valid=is_valid,
        id=cart.id,
        updated_at=cart.updated_at,
    )


def _enrich_item(item: CartItemReadSchema, products_by_id: dict[UUID, dict]) -> CartItemResponseSchema:
    product = products_by_id.get(item.product_id) if item.product_id is not None else None
    if product is None:
        # Товар отсутствует в видимой выдаче B2B → снят с продажи / удалён.
        return CartItemResponseSchema(
            sku_id=item.sku_id,
            product_id=item.product_id or item.sku_id,
            name='',
            quantity=item.quantity,
            unit_price=0,
            line_total=0,
            available_quantity=0,
            is_available=False,
            unavailable_reason=UnavailableReason.PRODUCT_DELETED,
        )

    sku = _find_sku(product, item.sku_id)
    if sku is None:
        # Товар виден, но конкретный SKU больше не предлагается → трактуем как нет в наличии.
        return CartItemResponseSchema(
            sku_id=item.sku_id,
            product_id=item.product_id or item.sku_id,
            name=str(product.get('title', '')),
            quantity=item.quantity,
            unit_price=0,
            line_total=0,
            available_quantity=0,
            is_available=False,
            unavailable_reason=UnavailableReason.OUT_OF_STOCK,
            image=_pick_image({}, product),
        )

    active_quantity = int(sku.get('active_quantity', 0))
    unit_price = int(sku.get('price', 0))
    name = f'{product.get("title", "")} {sku.get("name", "")}'.strip()
    is_available = active_quantity > 0

    return CartItemResponseSchema(
        sku_id=item.sku_id,
        product_id=UUID(str(sku['product_id'])),
        name=name,
        quantity=item.quantity,
        unit_price=unit_price,
        line_total=unit_price * item.quantity if is_available else 0,
        available_quantity=active_quantity,
        is_available=is_available,
        sku_code=sku.get('article'),
        image=_pick_image(sku, product),
        unavailable_reason=None if is_available else UnavailableReason.OUT_OF_STOCK,
    )


def _find_sku(product: dict, sku_id: UUID) -> dict | None:
    for raw in product.get('skus', []):
        raw_id = raw.get('id') if isinstance(raw, dict) else None
        if raw_id is None:
            continue
        try:
            if UUID(str(raw_id)) == sku_id:
                return raw
        except ValueError:
            continue
    return None


class GetCartUseCase:
    """GET /api/v1/cart — корзина с обогащением данных из B2B.

    Алгоритм (см. b2c-cart-flows.md, Flow B2C-8 §"Обогащение из B2B"):
    1. Найти корзину по user_id / session_id; нет корзины/позиций → пустой ответ (без B2B).
    2. Собрать distinct product_id позиций (null product_id → PRODUCT_DELETED при обогащении).
    3. ОДИН batch `POST /api/v1/public/products/batch` {product_ids: [...]} → JSON-массив
       видимых карточек товаров (с вложенными skus). Отсутствующие id молча опущены.
    4. Для каждого item найти его SKU внутри product.skus → доступность/цена/итоги.
    5. subtotal — только доступные; items_count — по всем; is_valid — все доступны и qty<=остаток.

    Если B2B недоступен (сеть/5xx) → B2BUnavailableError (503), без кэша.
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
            return CartResponseSchema()

        items = await self.cart_item_repository.list_by_cart(cart.id)
        if not items:
            return CartResponseSchema(id=cart.id, updated_at=cart.updated_at)

        products_by_id = await self._fetch_products(items)
        return enrich_cart(cart, items, products_by_id)

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

    async def _fetch_products(self, items: list[CartItemReadSchema]) -> dict[UUID, dict]:
        """Batch `POST /public/products/batch` → {product_id: product}.

        ServiceClient возвращает распарсенный JSON; для этого эндпоинта это МАССИВ
        (list), а не dict — поэтому не предполагаем .get(). Отсутствующие товары
        просто не попадают в индекс → трактуются как PRODUCT_DELETED.
        """
        product_ids = sorted({item.product_id for item in items if item.product_id is not None})
        if not product_ids:
            return {}

        try:
            payload = await self.b2b_client.post(
                '/api/v1/public/products/batch',
                json={'product_ids': [str(pid) for pid in product_ids]},
            )
        except ServiceClientError as exc:
            raise B2BUnavailableError() from exc
        except httpx.HTTPError as exc:
            raise B2BUnavailableError() from exc

        index: dict[UUID, dict] = {}
        for product in payload if isinstance(payload, list) else []:
            raw_id = product.get('id') if isinstance(product, dict) else None
            if raw_id is None:
                continue
            try:
                index[UUID(str(raw_id))] = product
            except ValueError:
                continue
        return index
