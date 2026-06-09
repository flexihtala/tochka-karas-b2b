from uuid import UUID

from apps.categories.errors import CategoryNotFoundError
from apps.categories.repositories import CategoryRepository
from apps.categories.schemas.response import CategoryResponseSchema


class GetCategoryUseCase:
    """GET /api/v1/categories/{id} — детали одной категории."""

    def __init__(self, category_repository: CategoryRepository):
        self.category_repository = category_repository

    async def __call__(self, category_id: UUID) -> CategoryResponseSchema:
        category = await self.category_repository.get_or_none(category_id)
        if category is None:
            raise CategoryNotFoundError()

        return CategoryResponseSchema.model_validate(category)
