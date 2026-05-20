from uuid import uuid4

import pytest

from apps.queue.errors import QueueEmptyError
from apps.queue.use_cases.claim_ticket import ClaimTicketUseCase
from apps.queue.use_cases.list_queue import ListQueueUseCase
from apps.tickets.enums import TicketStatus
from tests.tickets.fakes import FakeTicketRepository, make_ticket


@pytest.mark.anyio
async def test_claim_ticket_returns_next_pending_in_review():
    repo = FakeTicketRepository()
    repo.add(make_ticket(status=TicketStatus.PENDING, queue_priority=2))
    repo.add(make_ticket(status=TicketStatus.PENDING, queue_priority=1))  # highest priority
    moderator_id = uuid4()
    use_case = ClaimTicketUseCase(ticket_repository=repo)

    result = await use_case(moderator_id)

    # Use-case должен вызывать repository.claim_next() — а не работать с PENDING'ами вручную.
    assert repo.claim_next_calls == [moderator_id]
    # Возвращён тикет с приоритетом 1 (FIFO внутри приоритета не важно — у одного приоритета один тикет).
    assert result.status == TicketStatus.IN_REVIEW
    assert result.claimed_by == moderator_id
    assert result.queue_priority == 1


@pytest.mark.anyio
async def test_claim_ticket_empty_queue_raises_404():
    repo = FakeTicketRepository()
    moderator_id = uuid4()
    use_case = ClaimTicketUseCase(ticket_repository=repo)

    with pytest.raises(QueueEmptyError):
        await use_case(moderator_id)

    # Use-case всё равно делегирует к claim_next() — empty-сигнал приходит оттуда,
    # а не выводится use-cas'ом через get_or_none/list.
    assert repo.claim_next_calls == [moderator_id]


@pytest.mark.anyio
async def test_list_queue_returns_paginated_items():
    repo = FakeTicketRepository()
    repo.add(make_ticket(status=TicketStatus.PENDING, queue_priority=1))
    repo.add(make_ticket(status=TicketStatus.PENDING, queue_priority=2))
    repo.add(make_ticket(status=TicketStatus.APPROVED))
    use_case = ListQueueUseCase(ticket_repository=repo)

    result = await use_case(limit=10, offset=0)

    assert result.total_count == 3
    assert len(result.items) == 3
    assert result.limit == 10
    assert result.offset == 0


@pytest.mark.anyio
async def test_list_queue_filters_by_status():
    repo = FakeTicketRepository()
    repo.add(make_ticket(status=TicketStatus.PENDING))
    repo.add(make_ticket(status=TicketStatus.PENDING))
    repo.add(make_ticket(status=TicketStatus.APPROVED))
    use_case = ListQueueUseCase(ticket_repository=repo)

    result = await use_case(limit=10, offset=0, status=TicketStatus.PENDING)

    assert result.total_count == 2
    assert all(t.status == TicketStatus.PENDING for t in result.items)
