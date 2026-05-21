from apps.stats.schemas.response import ModeratorStatsResponseSchema
from apps.tickets.enums import TicketStatus
from apps.tickets.repositories import TicketRepository


class ModeratorsStatsUseCase:
    """GET /api/v1/stats/moderators — per-moderator аггрегаты.

    Спека ModeratorStats требует только moderator_id + decisions_count, остальные
    поля опциональны. Считаем для тикетов с claimed_by != NULL:
    - decisions_count = approved + blocked + hard_blocked (терминальные решения)
    - approved_count / blocked_count / hard_blocked_count — детализация
    Опциональный period проброшен сюда (агрегация по периоду — задел на M4).
    """

    def __init__(self, ticket_repository: TicketRepository):
        self.ticket_repository = ticket_repository

    async def __call__(self, period: str | None = None) -> list[ModeratorStatsResponseSchema]:
        _ = period  # M3: фильтрация по периоду — задел на M4.
        per_mod = await self.ticket_repository.count_by_moderator()
        result: list[ModeratorStatsResponseSchema] = []
        for moderator_id, status_counts in per_mod:
            approved = status_counts.get(TicketStatus.APPROVED.value, 0)
            blocked = status_counts.get(TicketStatus.BLOCKED.value, 0)
            hard_blocked = status_counts.get(TicketStatus.HARD_BLOCKED.value, 0)
            result.append(
                ModeratorStatsResponseSchema(
                    moderator_id=moderator_id,
                    decisions_count=approved + blocked + hard_blocked,
                    approved_count=approved,
                    blocked_count=blocked,
                    hard_blocked_count=hard_blocked,
                )
            )
        return result
