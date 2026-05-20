from apps.stats.schemas.response import StatsOverviewResponseSchema
from apps.tickets.enums import TicketStatus
from apps.tickets.repositories import TicketRepository


class OverviewStatsUseCase:
    """GET /api/v1/stats/overview — сводка по всем тикетам.

    Возвращает: total + per-status counts (PENDING, IN_REVIEW, APPROVED, BLOCKED).
    """

    def __init__(self, ticket_repository: TicketRepository):
        self.ticket_repository = ticket_repository

    async def __call__(self) -> StatsOverviewResponseSchema:
        counts = await self.ticket_repository.count_by_status()
        total = await self.ticket_repository.total_count()
        return StatsOverviewResponseSchema(
            total_tickets=total,
            pending_count=counts.get(TicketStatus.PENDING.value, 0),
            in_review_count=counts.get(TicketStatus.IN_REVIEW.value, 0),
            approved_count=counts.get(TicketStatus.APPROVED.value, 0),
            blocked_count=counts.get(TicketStatus.BLOCKED.value, 0),
        )
