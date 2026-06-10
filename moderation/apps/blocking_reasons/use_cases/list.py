from apps.blocking_reasons.repositories import BlockingReasonRepository
from apps.blocking_reasons.schemas.response import BlockingReasonResponseSchema


class ListBlockingReasonsUseCase:
    """GET /api/v1/blocking-reasons — moderator + admin доступ.

    Используется и admin-UI (для редактирования), и модераторами при выборе
    причины блокировки. По спеке возвращается массив (без пагинации/обёртки).
    Поддерживаются фильтры hard_block и is_active.

    По спеке is_active по умолчанию true: без явного фильтра возвращаются только
    активные причины (деактивированные скрыты от модераторов). Админ может явно
    запросить ?is_active=false, чтобы увидеть деактивированные.
    """

    def __init__(self, blocking_reason_repository: BlockingReasonRepository):
        self.blocking_reason_repository = blocking_reason_repository

    async def __call__(
        self,
        *,
        hard_block: bool | None = None,
        is_active: bool | None = None,
    ) -> list[BlockingReasonResponseSchema]:
        if is_active is None:
            is_active = True
        items = await self.blocking_reason_repository.list_(hard_block=hard_block, is_active=is_active)
        return [BlockingReasonResponseSchema.model_validate(i) for i in items]
