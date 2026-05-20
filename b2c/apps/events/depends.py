"""DI-провайдер для apps.events.

FastAPI Depends для проверки X-Service-Key создаётся в routers.py через
shared.inbox.make_verify_service_key(...) — это не объект, а функция-
зависимость с дефолтом на Header, потому через dishka не оборачиваем.
"""

from dishka import Provider, Scope, provide

from apps.events.repositories import SkuUnavailabilityRepository
from apps.events.use_cases import HandleProductEventUseCase


class EventsProvider(Provider):
    unavailability_repository = provide(SkuUnavailabilityRepository, scope=Scope.REQUEST)
    handle_product_event_use_case = provide(HandleProductEventUseCase, scope=Scope.REQUEST)
