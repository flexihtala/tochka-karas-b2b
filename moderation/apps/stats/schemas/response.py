from uuid import UUID

from pydantic import BaseModel


class StatsOverviewResponseSchema(BaseModel):
    """GET /api/v1/stats/overview — сводка по тикетам.

    M3 заводит минимальный набор счётчиков. Расширим, когда появятся
    avg_review_time_seconds, pending_by_priority (M4).
    """

    total_tickets: int
    pending_count: int
    in_review_count: int
    approved_count: int
    blocked_count: int


class ModeratorStatsResponseSchema(BaseModel):
    """GET /api/v1/stats/moderators — агрегаты по модераторам.

    M3 версия — без среднего времени review (вводится в M4 после добавления decision_at).
    """

    moderator_id: UUID
    decisions_count: int
    approved_count: int
    blocked_count: int
    in_review_count: int
