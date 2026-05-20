from dishka import Provider, Scope, provide

from apps.events.use_cases import HandleB2BEventUseCase
from apps.tickets.repositories import TicketRepository


class EventsProvider(Provider):
    ticket_repository = provide(TicketRepository, scope=Scope.REQUEST)
    handle_b2b_event_use_case = provide(HandleB2BEventUseCase, scope=Scope.REQUEST)
