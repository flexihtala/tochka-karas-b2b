from uuid import uuid4

import pytest

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
    assert result is not None
    assert result.status == TicketStatus.IN_REVIEW
    assert result.assigned_moderator_id == moderator_id
    assert result.queue_priority == 1


@pytest.mark.anyio
async def test_claim_ticket_empty_queue_returns_none():
    """По спеке /queue/claim возвращает 204 — use-case отдаёт None, роутер мапит в 204."""
    repo = FakeTicketRepository()
    moderator_id = uuid4()
    use_case = ClaimTicketUseCase(ticket_repository=repo)

    result = await use_case(moderator_id)

    assert result is None
    assert repo.claim_next_calls == [moderator_id]


@pytest.mark.anyio
async def test_list_queue_returns_only_pending():
    """По спеке /queue возвращает только PENDING — APPROVED/BLOCKED исключены."""
    repo = FakeTicketRepository()
    repo.add(make_ticket(status=TicketStatus.PENDING, queue_priority=1))
    repo.add(make_ticket(status=TicketStatus.PENDING, queue_priority=2))
    repo.add(make_ticket(status=TicketStatus.APPROVED))
    use_case = ListQueueUseCase(ticket_repository=repo)

    result = await use_case(limit=10, offset=0)

    assert result.total_count == 2
    assert all(t.status == TicketStatus.PENDING for t in result.items)
    assert result.limit == 10
    assert result.offset == 0


@pytest.mark.anyio
async def test_list_queue_filters_by_queue_priority():
    repo = FakeTicketRepository()
    repo.add(make_ticket(status=TicketStatus.PENDING, queue_priority=1))
    repo.add(make_ticket(status=TicketStatus.PENDING, queue_priority=2))
    repo.add(make_ticket(status=TicketStatus.PENDING, queue_priority=2))
    use_case = ListQueueUseCase(ticket_repository=repo)

    result = await use_case(limit=10, offset=0, queue_priority=2)

    assert result.total_count == 2
    assert all(t.queue_priority == 2 for t in result.items)


@pytest.mark.anyio
async def test_list_queue_filters_by_seller_id():
    seller_a = uuid4()
    seller_b = uuid4()
    repo = FakeTicketRepository()
    repo.add(make_ticket(status=TicketStatus.PENDING, seller_id=seller_a))
    repo.add(make_ticket(status=TicketStatus.PENDING, seller_id=seller_b))
    use_case = ListQueueUseCase(ticket_repository=repo)

    result = await use_case(limit=10, offset=0, seller_id=seller_a)

    assert result.total_count == 1
    assert result.items[0].seller_id == seller_a
