from dishka import Provider, Scope, provide

from apps.subscriptions.repositories import SubscriptionRepository
from apps.subscriptions.use_cases import SubscribeUseCase, UnsubscribeUseCase


class SubscriptionsProvider(Provider):
    subscription_repository = provide(SubscriptionRepository, scope=Scope.REQUEST)
    subscribe_use_case = provide(SubscribeUseCase, scope=Scope.REQUEST)
    unsubscribe_use_case = provide(UnsubscribeUseCase, scope=Scope.REQUEST)
