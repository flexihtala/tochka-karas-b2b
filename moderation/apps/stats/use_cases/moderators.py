from apps.stats.schemas.response import ModeratorStatsResponseSchema
from apps.tickets.enums import TicketStatus
from apps.tickets.repositories import TicketRepository


class ModeratorsStatsUseCase:
    """GET /api/v1/stats/moderators — per-moderator аггрегаты.

    Считаем только тикеты с claimed_by != NULL. decisions_count = approved + blocked
    (терминальные для M3); in_review_count — текущие in-flight.
    """

    def __init__(self, ticket_repository: TicketRepository):
        self.ticket_repository = ticket_repository

    async def __call__(self) -> list[ModeratorStatsResponseSchema]:
        per_mod = await self.ticket_repository.count_by_moderator()
        result: list[ModeratorStatsResponseSchema] = []
        for moderator_id, status_counts in per_mod:
            approved = status_counts.get(TicketStatus.APPROVED.value, 0)
            blocked = status_counts.get(TicketStatus.BLOCKED.value, 0)
            in_review = status_counts.get(TicketStatus.IN_REVIEW.value, 0)
            result.append(
                ModeratorStatsResponseSchema(
                    moderator_id=moderator_id,
                    decisions_count=approved + blocked,
                    approved_count=approved,
                    blocked_count=blocked,
                    in_review_count=in_review,
                )
            )
        return result
