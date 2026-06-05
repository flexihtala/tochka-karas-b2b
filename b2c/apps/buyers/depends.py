from dishka import Provider, Scope, provide

from apps.buyers.use_cases import GetBuyerUseCase, UpdateBuyerUseCase


class BuyersProvider(Provider):
    get_buyer_use_case = provide(GetBuyerUseCase, scope=Scope.REQUEST)
    update_buyer_use_case = provide(UpdateBuyerUseCase, scope=Scope.REQUEST)
