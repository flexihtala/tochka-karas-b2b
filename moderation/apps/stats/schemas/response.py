from uuid import UUID

from pydantic import BaseModel


class StatsOverviewResponseSchema(BaseModel):
    """GET /api/v1/stats/overview — спека StatsOverview из neomarket-moderation.yaml.

    Обязательные поля: pending_count, in_review_count, approved_count, blocked_count,
    hard_blocked_count.
    Опциональные: avg_review_time_seconds, pending_by_priority (вводятся в M4).
    """

    pending_count: int
    in_review_count: int
    approved_count: int
    blocked_count: int
    hard_blocked_count: int


class ModeratorStatsResponseSchema(BaseModel):
    """GET /api/v1/stats/moderators — спека ModeratorStats из neomarket-moderation.yaml.

    Обязательные: moderator_id, decisions_count. Опциональные: moderator_name,
    approved_count, blocked_count, hard_blocked_count, avg_review_time_seconds,
    released_count.
    """

    moderator_id: UUID
    moderator_name: str | None = None
    decisions_count: int
    approved_count: int = 0
    blocked_count: int = 0
    hard_blocked_count: int = 0
    avg_review_time_seconds: int | None = None
    released_count: int = 0
