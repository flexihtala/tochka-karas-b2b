from uuid import uuid4

import pytest

from apps.stats.use_cases import ModeratorsStatsUseCase
from apps.tickets.enums import TicketStatus
from tests.events.fakes import FakeTicketRepository, make_ticket_read_schema


@pytest.mark.anyio
async def test_moderators_stats_aggregates_per_moderator():
    repo = FakeTicketRepository()
    mod_a = uuid4()
    mod_b = uuid4()

    # Модератор A: 2 APPROVED, 1 BLOCKED, 1 IN_REVIEW.
    repo.add(make_ticket_read_schema(claimed_by=mod_a, status=TicketStatus.APPROVED.value))
    repo.add(make_ticket_read_schema(claimed_by=mod_a, status=TicketStatus.APPROVED.value))
    repo.add(make_ticket_read_schema(claimed_by=mod_a, status=TicketStatus.BLOCKED.value))
    repo.add(make_ticket_read_schema(claimed_by=mod_a, status=TicketStatus.IN_REVIEW.value))

    # Модератор B: 3 APPROVED.
    for _ in range(3):
        repo.add(make_ticket_read_schema(claimed_by=mod_b, status=TicketStatus.APPROVED.value))

    # Не-зачитанные тикеты (claimed_by=None) — не должны попасть.
    repo.add(make_ticket_read_schema(claimed_by=None, status=TicketStatus.PENDING.value))

    use_case = ModeratorsStatsUseCase(ticket_repository=repo)
    result = await use_case()

    by_id = {r.moderator_id: r for r in result}
    assert set(by_id.keys()) == {mod_a, mod_b}

    a = by_id[mod_a]
    assert a.approved_count == 2
    assert a.blocked_count == 1
    assert a.in_review_count == 1
    assert a.decisions_count == 3  # 2 approved + 1 blocked

    b = by_id[mod_b]
    assert b.approved_count == 3
    assert b.blocked_count == 0
    assert b.in_review_count == 0
    assert b.decisions_count == 3


@pytest.mark.anyio
async def test_moderators_stats_returns_empty_when_no_claimed_tickets():
    repo = FakeTicketRepository()
    repo.add(make_ticket_read_schema(claimed_by=None, status=TicketStatus.PENDING.value))

    use_case = ModeratorsStatsUseCase(ticket_repository=repo)
    result = await use_case()

    assert result == []
