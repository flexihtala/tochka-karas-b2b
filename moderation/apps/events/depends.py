from dishka import Provider, Scope, provide

from apps.events.use_cases import HandleB2BEventUseCase


class EventsProvider(Provider):
    """DI входящего канала b2b/events.

    `TicketRepository` уже регистрируется TicketsProvider — dishka резолвит его из
    общего набора провайдеров, как и QueueProvider. Здесь объявляем только сам use-case.
    """

    handle_b2b_event_use_case = provide(HandleB2BEventUseCase, scope=Scope.REQUEST)
