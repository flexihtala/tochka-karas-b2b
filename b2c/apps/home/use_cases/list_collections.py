from apps.home.repositories import CollectionRepository
from apps.home.schemas.response import CollectionMetaResponseSchema


class ListCollectionsUseCase:
    """GET /home/collections — список активных подборок без товаров.

    Только метаданные (id, slug, title, description, position).
    Сортировка: position ASC, created_at ASC.
    """

    def __init__(self, collection_repository: CollectionRepository):
        self.collection_repository = collection_repository

    async def __call__(self) -> list[CollectionMetaResponseSchema]:
        collections = await self.collection_repository.list_active()
        return [CollectionMetaResponseSchema.model_validate(c) for c in collections]
