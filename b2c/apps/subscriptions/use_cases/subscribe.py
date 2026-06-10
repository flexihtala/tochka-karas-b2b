from apps.subscriptions.errors import SubscriptionAlreadyExistsError
from apps.subscriptions.repositories import SubscriptionRepository
from apps.subscriptions.schemas.db import SubscriptionCreateSchema
from apps.subscriptions.schemas.request import SubscriptionCreateRequestSchema
from apps.subscriptions.schemas.response import SubscriptionResponseSchema
from shared.auth_lib import AuthenticatedUserSchema


class SubscribeUseCase:
    """POST /api/v1/subscriptions.

    Бизнес-правила:
    - user_id берётся ТОЛЬКО из JWT (current_user.id), любой user_id в теле
      запроса игнорируется.
    - Повтор подписки (user_id, product_id) → 409 SUBSCRIPTION_ALREADY_EXISTS.
    - Невалидные значения notify_on отсекаются на уровне схемы (400).
    - Существование товара в B2B мы не проверяем здесь (MVP-каркас):
      product_id — любой валидный UUID, фактическая верификация и матчинг
      событий BACK_IN_STOCK/PRICE_DROP происходит в B2B/inbox-обработчике.
      См. ADR в b2c/README.md.
    """

    def __init__(self, subscription_repository: SubscriptionRepository):
        self.subscription_repository = subscription_repository

    async def __call__(
        self,
        data: SubscriptionCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> SubscriptionResponseSchema:
        existing = await self.subscription_repository.get_by_user_and_product(current_user.id, data.product_id)
        if existing is not None:
            raise SubscriptionAlreadyExistsError()

        subscription = await self.subscription_repository.create(
            SubscriptionCreateSchema(
                user_id=current_user.id,
                product_id=data.product_id,
                notify_on=data.notify_on,
            )
        )
        return SubscriptionResponseSchema.model_validate(subscription)
