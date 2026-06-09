from dishka import Provider, Scope, provide

from apps.moderators.use_cases import (
    CreateModeratorUseCase,
    GetModeratorUseCase,
    ListModeratorsUseCase,
    UpdateModeratorUseCase,
)


class ModeratorsProvider(Provider):
    list_moderators_use_case = provide(ListModeratorsUseCase, scope=Scope.REQUEST)
    get_moderator_use_case = provide(GetModeratorUseCase, scope=Scope.REQUEST)
    create_moderator_use_case = provide(CreateModeratorUseCase, scope=Scope.REQUEST)
    update_moderator_use_case = provide(UpdateModeratorUseCase, scope=Scope.REQUEST)
