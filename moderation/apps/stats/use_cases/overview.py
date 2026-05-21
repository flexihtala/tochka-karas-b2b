from apps.stats.schemas.response import StatsOverviewResponseSchema
from apps.tickets.enums import TicketStatus
from apps.tickets.repositories import TicketRepository


class OverviewStatsUseCase:
    """GET /api/v1/stats/overview — спека StatsOverview из neomarket-moderation.yaml.

    Возвращает per-status counts: PENDING, IN_REVIEW, APPROVED, BLOCKED, HARD_BLOCKED.
    Опциональный period query param поддерживается на уровне роутера и пробрасывается
    в use-case (агрегация по периоду — задел на M4).
    """

    def __init__(self, ticket_repository: TicketRepository):
        self.ticket_repository = ticket_repository

    async def __call__(self, period: str | None = None) -> StatsOverviewResponseSchema:
        _ = period  # M3: фильтрация по периоду — задел на M4.
        counts = await self.ticket_repository.count_by_status()
        return StatsOverviewResponseSchema(
            pending_count=counts.get(TicketStatus.PENDING.value, 0),
            in_review_count=counts.get(TicketStatus.IN_REVIEW.value, 0),
            approved_count=counts.get(TicketStatus.APPROVED.value, 0),
            blocked_count=counts.get(TicketStatus.BLOCKED.value, 0),
            hard_blocked_count=counts.get(TicketStatus.HARD_BLOCKED.value, 0),
        )
