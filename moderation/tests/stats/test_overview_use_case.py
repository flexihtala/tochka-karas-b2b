import pytest

from apps.stats.use_cases import OverviewStatsUseCase
from apps.tickets.enums import TicketStatus
from tests.events.fakes import FakeTicketRepository, make_ticket_read_schema


def _add_tickets(repo: FakeTicketRepository, status: str, n: int) -> None:
    for _ in range(n):
        repo.add(make_ticket_read_schema(status=status))


@pytest.mark.anyio
async def test_overview_returns_correct_counts():
    repo = FakeTicketRepository()
    _add_tickets(repo, TicketStatus.PENDING.value, 3)
    _add_tickets(repo, TicketStatus.IN_REVIEW.value, 1)
    _add_tickets(repo, TicketStatus.APPROVED.value, 5)
    _add_tickets(repo, TicketStatus.BLOCKED.value, 2)
    _add_tickets(repo, TicketStatus.ARCHIVED.value, 4)

    use_case = OverviewStatsUseCase(ticket_repository=repo)
    result = await use_case()

    assert result.total_tickets == 15
    assert result.pending_count == 3
    assert result.in_review_count == 1
    assert result.approved_count == 5
    assert result.blocked_count == 2


@pytest.mark.anyio
async def test_overview_returns_zeros_for_empty_repo():
    repo = FakeTicketRepository()
    use_case = OverviewStatsUseCase(ticket_repository=repo)

    result = await use_case()

    assert result.total_tickets == 0
    assert result.pending_count == 0
    assert result.in_review_count == 0
    assert result.approved_count == 0
    assert result.blocked_count == 0


@pytest.mark.anyio
async def test_overview_ignores_unknown_statuses():
    """Если в БД появится непредусмотренный статус — счётчики не падают, просто 0."""
    repo = FakeTicketRepository()
    repo.add(make_ticket_read_schema(status='UNKNOWN_STATUS'))
    repo.add(make_ticket_read_schema(status=TicketStatus.PENDING.value))

    use_case = OverviewStatsUseCase(ticket_repository=repo)
    result = await use_case()

    assert result.total_tickets == 2
    assert result.pending_count == 1
    assert result.in_review_count == 0
