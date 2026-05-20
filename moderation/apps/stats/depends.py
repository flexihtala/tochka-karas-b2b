from dishka import Provider, Scope, provide

from apps.stats.use_cases import ModeratorsStatsUseCase, OverviewStatsUseCase


class StatsProvider(Provider):
    overview_stats_use_case = provide(OverviewStatsUseCase, scope=Scope.REQUEST)
    moderators_stats_use_case = provide(ModeratorsStatsUseCase, scope=Scope.REQUEST)
