from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.home.schemas.db import (
    BannerClickCreateSchema,
    BannerClickReadSchema,
    BannerCreateSchema,
    BannerReadSchema,
    CollectionCreateSchema,
    CollectionItemCreateSchema,
    CollectionItemReadSchema,
    CollectionReadSchema,
)
from apps.home.services import B2BProductSchema


class FakeBannerRepository:
    def __init__(self):
        self.by_id: dict[UUID, BannerReadSchema] = {}
        self.created: list[BannerCreateSchema] = []

    def add(self, banner: BannerReadSchema) -> None:
        self.by_id[banner.id] = banner

    async def create(self, data: BannerCreateSchema) -> BannerReadSchema:
        self.created.append(data)
        banner_id = data.id or uuid4()
        now = datetime.now(UTC)
        banner = BannerReadSchema(
            id=banner_id,
            title=data.title,
            image_url=data.image_url,
            link_url=data.link_url,
            priority=data.priority,
            is_active=data.is_active,
            schedule_start=data.schedule_start,
            schedule_end=data.schedule_end,
            created_at=now,
            updated_at=now,
        )
        self.by_id[banner_id] = banner
        return banner

    async def get_or_none(self, id_: UUID) -> BannerReadSchema | None:
        return self.by_id.get(id_)

    async def exists(self, banner_id: UUID) -> bool:
        return banner_id in self.by_id

    async def list_active(self, now: datetime) -> list[BannerReadSchema]:
        result = [
            banner
            for banner in self.by_id.values()
            if banner.is_active
            and (banner.schedule_start is None or banner.schedule_start <= now)
            and (banner.schedule_end is None or banner.schedule_end >= now)
        ]
        # priority DESC, created_at ASC — стабильная очерёдность при равном priority.
        return sorted(result, key=lambda b: (-b.priority, b.created_at))


class FakeBannerClickRepository:
    def __init__(self):
        self.by_id: dict[UUID, BannerClickReadSchema] = {}
        self.created: list[BannerClickCreateSchema] = []

    async def create(self, data: BannerClickCreateSchema) -> BannerClickReadSchema:
        self.created.append(data)
        click_id = data.id or uuid4()
        now = datetime.now(UTC)
        click = BannerClickReadSchema(
            id=click_id,
            banner_id=data.banner_id,
            user_id=data.user_id,
            created_at=now,
            updated_at=now,
        )
        self.by_id[click_id] = click
        return click


class FakeCollectionRepository:
    def __init__(self):
        self.by_id: dict[UUID, CollectionReadSchema] = {}
        self.created: list[CollectionCreateSchema] = []

    def add(self, collection: CollectionReadSchema) -> None:
        self.by_id[collection.id] = collection

    async def create(self, data: CollectionCreateSchema) -> CollectionReadSchema:
        self.created.append(data)
        collection_id = data.id or uuid4()
        now = datetime.now(UTC)
        collection = CollectionReadSchema(
            id=collection_id,
            slug=data.slug,
            title=data.title,
            description=data.description,
            position=data.position,
            is_active=data.is_active,
            created_at=now,
            updated_at=now,
        )
        self.by_id[collection_id] = collection
        return collection

    async def get_or_none(self, id_: UUID) -> CollectionReadSchema | None:
        return self.by_id.get(id_)

    async def list_active(self) -> list[CollectionReadSchema]:
        result = [c for c in self.by_id.values() if c.is_active]
        return sorted(result, key=lambda c: (c.position, c.created_at))


class FakeCollectionItemRepository:
    def __init__(self):
        self.by_id: dict[UUID, CollectionItemReadSchema] = {}
        self.created: list[CollectionItemCreateSchema] = []

    def add(self, item: CollectionItemReadSchema) -> None:
        self.by_id[item.id] = item

    async def create(self, data: CollectionItemCreateSchema) -> CollectionItemReadSchema:
        self.created.append(data)
        item_id = data.id or uuid4()
        now = datetime.now(UTC)
        item = CollectionItemReadSchema(
            id=item_id,
            collection_id=data.collection_id,
            product_id=data.product_id,
            ordering=data.ordering,
            created_at=now,
            updated_at=now,
        )
        self.by_id[item_id] = item
        return item

    async def list_by_collection(self, collection_id: UUID) -> list[CollectionItemReadSchema]:
        result = [it for it in self.by_id.values() if it.collection_id == collection_id]
        return sorted(result, key=lambda it: (it.ordering, it.created_at))


class FakeB2BProductsClient:
    """Контролируемый стенд для use-case-тестов; не делает HTTP."""

    def __init__(self):
        self.available: dict[UUID, B2BProductSchema] = {}
        self.batches_called: list[list[UUID]] = []

    def add_available(self, product: B2BProductSchema) -> None:
        self.available[product.id] = product

    async def fetch_batch(self, product_ids: list[UUID]) -> list[B2BProductSchema]:
        self.batches_called.append(list(product_ids))
        return [self.available[pid] for pid in product_ids if pid in self.available]
