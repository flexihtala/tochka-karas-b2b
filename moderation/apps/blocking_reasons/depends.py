from dishka import Provider, Scope, provide

from apps.blocking_reasons.repositories import BlockingReasonRepository
from apps.blocking_reasons.use_cases import (
    CreateBlockingReasonUseCase,
    DeleteBlockingReasonUseCase,
    ListBlockingReasonsUseCase,
    UpdateBlockingReasonUseCase,
)


class BlockingReasonsProvider(Provider):
    blocking_reason_repository = provide(BlockingReasonRepository, scope=Scope.REQUEST)

    list_blocking_reasons_use_case = provide(ListBlockingReasonsUseCase, scope=Scope.REQUEST)
    create_blocking_reason_use_case = provide(CreateBlockingReasonUseCase, scope=Scope.REQUEST)
    update_blocking_reason_use_case = provide(UpdateBlockingReasonUseCase, scope=Scope.REQUEST)
    delete_blocking_reason_use_case = provide(DeleteBlockingReasonUseCase, scope=Scope.REQUEST)
