from dishka import Provider, Scope, provide

from apps.events.use_cases import ApplyModerationEventUseCase


class EventsProvider(Provider):
    apply_moderation_event_use_case = provide(ApplyModerationEventUseCase, scope=Scope.REQUEST)
