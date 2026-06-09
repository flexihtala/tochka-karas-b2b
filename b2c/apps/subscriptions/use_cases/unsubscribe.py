from uuid import UUID

from apps.subscriptions.errors import SubscriptionNotFoundError
from apps.subscriptions.repositories import SubscriptionRepository
from shared.auth_lib import AuthenticatedUserSchema


class UnsubscribeUseCase:
    """DELETE /api/v1/subscriptions/{product_id}.

    Бизнес-правила:
    - user_id из JWT.
    - Если подписки нет → 404 SUBSCRIPTION_NOT_FOUND.
    - Снимаем подписку только текущего пользователя (IDOR-prevention).
    """

    def __init__(self, subscription_repository: SubscriptionRepository):
        self.subscription_repository = subscription_repository

    async def __call__(self, product_id: UUID, current_user: AuthenticatedUserSchema) -> None:
        deleted = await self.subscription_repository.delete_by_user_and_product(current_user.id, product_id)
        if not deleted:
            raise SubscriptionNotFoundError()
