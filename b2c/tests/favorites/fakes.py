"""In-memory фейки для favorites — без обращений к БД и HTTP."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from apps.favorites.schemas.db import FavoriteCreateSchema, FavoriteReadSchema


class FakeFavoriteRepository:
    """In-memory эквивалент FavoriteRepository.

    Сохраняет UNIQUE(user_id, product_id): повторный create => ConstraintError-like
    поведение мы здесь не имитируем, потому что use-case сам проверяет существование
    через get_by_user_and_product (идемпотентность реализована на уровне use-case).
    """

    def __init__(self):
        self.by_id: dict[UUID, FavoriteReadSchema] = {}
        self.created: list[FavoriteCreateSchema] = []
        self.deleted: list[tuple[UUID, UUID]] = []

    async def create(self, data: FavoriteCreateSchema) -> FavoriteReadSchema:
        self.created.append(data)
        favorite_id = data.id or uuid4()
        now = datetime.now(UTC)
        favorite = FavoriteReadSchema(
            id=favorite_id,
            user_id=data.user_id,
            product_id=data.product_id,
            created_at=now,
            updated_at=now,
        )
        self.by_id[favorite_id] = favorite
        return favorite

    async def get_by_user_and_product(self, user_id: UUID, product_id: UUID) -> FavoriteReadSchema | None:
        for favorite in self.by_id.values():
            if favorite.user_id == user_id and favorite.product_id == product_id:
                return favorite
        return None

    async def list_by_user(self, user_id: UUID) -> list[FavoriteReadSchema]:
        return sorted(
            (favorite for favorite in self.by_id.values() if favorite.user_id == user_id),
            key=lambda favorite: favorite.created_at,
        )

    async def delete_by_user_and_product(self, user_id: UUID, product_id: UUID) -> bool:
        target = await self.get_by_user_and_product(user_id, product_id)
        self.deleted.append((user_id, product_id))
        if target is None:
            return False
        self.by_id.pop(target.id, None)
        return True

    def add(self, favorite: FavoriteReadSchema) -> None:
        self.by_id[favorite.id] = favorite


class FakeB2BProductsClient:
    """In-memory эквивалент B2BProductsClient: словарь product_id -> product-dict.

    Если product_id отсутствует в словаре — товар считается заблокированным/удалённым
    и не возвращается (как делает реальный B2B при batch /products?ids=...).
    """

    def __init__(self, products: dict[str, dict[str, Any]] | None = None):
        self.products: dict[str, dict[str, Any]] = products or {}
        self.calls: list[list[UUID]] = []
        self.error: Exception | None = None

    async def list_products_by_ids(self, ids: list[UUID]) -> list[dict[str, Any]]:
        self.calls.append(list(ids))
        if self.error:
            raise self.error
        result: list[dict[str, Any]] = []
        for product_id in ids:
            product = self.products.get(str(product_id))
            if product is not None:
                result.append(product)
        return result

    def add_product(self, product_id: UUID, **fields: Any) -> None:
        payload = {'id': str(product_id), **fields}
        self.products[str(product_id)] = payload
