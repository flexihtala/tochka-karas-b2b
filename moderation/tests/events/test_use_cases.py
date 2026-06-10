from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from apps.events.errors import DuplicateEventError, TicketNotFoundForEditError
from apps.events.schemas.request import B2BEventTypeEnum, IncomingB2BEventSchema
from apps.events.use_cases.handle_b2b_event import HandleB2BEventUseCase
from apps.tickets.enums import TicketKind, TicketStatus
from tests.events.fakes import FakeInboxRepository
from tests.tickets.fakes import FakeTicketRepository, make_ticket


def make_event(
    event_type: B2BEventTypeEnum,
    *,
    product_id: UUID | None = None,
    seller_id: UUID | None = None,
    json_before: dict[str, Any] | None = None,
    json_after: dict[str, Any] | None = None,
    idempotency_key: UUID | None = None,
) -> IncomingB2BEventSchema:
    payload: dict[str, Any] = {'product_id': str(product_id or uuid4())}
    if seller_id is not None:
        payload['seller_id'] = str(seller_id)
    if json_before is not None:
        payload['json_before'] = json_before
    if json_after is not None:
        payload['json_after'] = json_after
    return IncomingB2BEventSchema(
        event_type=event_type,
        idempotency_key=idempotency_key or uuid4(),
        occurred_at=datetime.now(UTC),
        payload=payload,
    )


# ----------------------------- PRODUCT_CREATED -----------------------------


@pytest.mark.anyio
async def test_created_event_creates_pending_ticket():
    repo = FakeTicketRepository()
    use_case = HandleB2BEventUseCase(ticket_repository=repo, inbox_repository=FakeInboxRepository())
    product_id = uuid4()
    seller_id = uuid4()

    result = await use_case(
        make_event(
            B2BEventTypeEnum.PRODUCT_CREATED,
            product_id=product_id,
            seller_id=seller_id,
            json_after={'title': 'New product'},
        )
    )

    assert result.ticket_id is not None
    created = repo.by_id[result.ticket_id]
    assert created.product_id == product_id
    assert created.seller_id == seller_id
    assert created.status == TicketStatus.PENDING
    assert created.kind == TicketKind.CREATE
    assert created.json_after == {'title': 'New product'}


# ----------------------------- PRODUCT_EDITED -----------------------------


@pytest.mark.anyio
async def test_edited_event_resets_active_ticket_to_pending():
    """EDITED по активному (не терминальному) тикету сбрасывает его в PENDING и снимает claim."""
    repo = FakeTicketRepository()
    use_case = HandleB2BEventUseCase(ticket_repository=repo, inbox_repository=FakeInboxRepository())
    product_id = uuid4()
    moderator_id = uuid4()
    ticket = make_ticket(product_id=product_id, status=TicketStatus.IN_REVIEW, claimed_by=moderator_id)
    repo.add(ticket)

    result = await use_case(
        make_event(
            B2BEventTypeEnum.PRODUCT_EDITED,
            product_id=product_id,
            seller_id=ticket.seller_id,
            json_before={'title': 'old'},
            json_after={'title': 'new'},
        )
    )

    assert result.ticket_id == ticket.id
    assert repo.by_id[ticket.id].status == TicketStatus.PENDING
    assert repo.by_id[ticket.id].claimed_by is None
    assert repo.by_id[ticket.id].claimed_at is None


@pytest.mark.anyio
async def test_edited_event_without_active_ticket_raises_404():
    repo = FakeTicketRepository()
    use_case = HandleB2BEventUseCase(ticket_repository=repo, inbox_repository=FakeInboxRepository())

    with pytest.raises(TicketNotFoundForEditError) as err:
        await use_case(
            make_event(
                B2BEventTypeEnum.PRODUCT_EDITED,
                product_id=uuid4(),
                seller_id=uuid4(),
                json_before={},
                json_after={},
            )
        )
    assert err.value.status_code == 404


@pytest.mark.anyio
async def test_edited_event_on_hard_blocked_is_ignored():
    """DoD US-MOD-05: PRODUCT_EDITED для товара с HARD_BLOCKED-тикетом → тикет ОСТАЁТСЯ
    HARD_BLOCKED (не сбрасывается в PENDING); идемпотентно при повторе."""
    repo = FakeTicketRepository()
    use_case = HandleB2BEventUseCase(ticket_repository=repo, inbox_repository=FakeInboxRepository())
    product_id = uuid4()
    moderator_id = uuid4()
    ticket = make_ticket(
        product_id=product_id,
        status=TicketStatus.HARD_BLOCKED,
        claimed_by=moderator_id,
    )
    repo.add(ticket)

    event = make_event(
        B2BEventTypeEnum.PRODUCT_EDITED,
        product_id=product_id,
        seller_id=ticket.seller_id,
        json_before={'title': 'old'},
        json_after={'title': 'new'},
    )

    result = await use_case(event)

    # Терминальный статус НЕ изменился, claim не снят.
    assert result.ticket_id == ticket.id
    assert repo.by_id[ticket.id].status == TicketStatus.HARD_BLOCKED
    assert repo.by_id[ticket.id].claimed_by == moderator_id
    # Никакого update в репозиторий (no-op).
    assert repo.updated == []

    # Бизнес-идемпотентность: НОВОЕ EDITED-событие (свой idempotency_key) — тоже no-op,
    # статус остаётся HARD_BLOCKED. (Повтор с ТЕМ ЖЕ ключом теперь → 409, см. тесты inbox.)
    await use_case(
        make_event(
            B2BEventTypeEnum.PRODUCT_EDITED,
            product_id=product_id,
            seller_id=ticket.seller_id,
            json_before={'title': 'old'},
            json_after={'title': 'newer'},
        )
    )
    assert repo.by_id[ticket.id].status == TicketStatus.HARD_BLOCKED
    assert repo.updated == []


# ----------------------------- PRODUCT_DELETED -----------------------------


@pytest.mark.anyio
async def test_deleted_event_removes_hard_blocked():
    """DoD US-MOD-05: PRODUCT_DELETED для HARD_BLOCKED-тикета → тикет становится ARCHIVED
    (запись модерации закрыта); идемпотентно при повторе."""
    repo = FakeTicketRepository()
    use_case = HandleB2BEventUseCase(ticket_repository=repo, inbox_repository=FakeInboxRepository())
    product_id = uuid4()
    ticket = make_ticket(product_id=product_id, status=TicketStatus.HARD_BLOCKED)
    repo.add(ticket)

    await use_case(make_event(B2BEventTypeEnum.PRODUCT_DELETED, product_id=product_id))

    assert repo.by_id[ticket.id].status == TicketStatus.ARCHIVED

    # Бизнес-идемпотентность: повторный DELETE с НОВЫМ ключом — no-op, статус остаётся ARCHIVED.
    updates_after_first = len(repo.updated)
    await use_case(make_event(B2BEventTypeEnum.PRODUCT_DELETED, product_id=product_id))
    assert repo.by_id[ticket.id].status == TicketStatus.ARCHIVED
    # Повтор не затронул ни одной строки (уже архивирован).
    assert len(repo.updated) == updates_after_first


@pytest.mark.anyio
async def test_deleted_event_with_no_tickets_is_noop():
    repo = FakeTicketRepository()
    use_case = HandleB2BEventUseCase(ticket_repository=repo, inbox_repository=FakeInboxRepository())

    result = await use_case(make_event(B2BEventTypeEnum.PRODUCT_DELETED, product_id=uuid4()))

    assert result.ticket_id is None
    assert repo.updated == []


# ----------------------- Идемпотентность (US-MOD-01, inbox) -----------------------


@pytest.mark.anyio
async def test_duplicate_product_created_creates_single_ticket():
    """Два одинаковых PRODUCT_CREATED (same idempotency_key) подряд → ровно ОДИН тикет;
    второй вызов поднимает DuplicateEventError (409 DUPLICATE_EVENT)."""
    repo = FakeTicketRepository()
    inbox = FakeInboxRepository()
    use_case = HandleB2BEventUseCase(ticket_repository=repo, inbox_repository=inbox)
    key = uuid4()
    product_id = uuid4()
    seller_id = uuid4()

    first = await use_case(
        make_event(
            B2BEventTypeEnum.PRODUCT_CREATED,
            product_id=product_id,
            seller_id=seller_id,
            json_after={'title': 'New product'},
            idempotency_key=key,
        )
    )
    assert first.ticket_id is not None

    with pytest.raises(DuplicateEventError) as err:
        await use_case(
            make_event(
                B2BEventTypeEnum.PRODUCT_CREATED,
                product_id=product_id,
                seller_id=seller_id,
                json_after={'title': 'New product'},
                idempotency_key=key,
            )
        )

    assert err.value.status_code == 409
    assert err.value.code == 'DUPLICATE_EVENT'
    # Ровно один тикет: дубликат отбит ДО мутаций.
    assert len(repo.created) == 1
    assert len(repo.by_id) == 1


@pytest.mark.anyio
async def test_duplicate_event_returns_409_without_side_effects():
    """Дубликат любого типа события → 409 БЕЗ мутаций тикетов: ключ фиксируется в
    processed_events до побочных эффектов, повтор не доходит до TicketRepository."""
    repo = FakeTicketRepository()
    inbox = FakeInboxRepository()
    use_case = HandleB2BEventUseCase(ticket_repository=repo, inbox_repository=inbox)
    product_id = uuid4()
    moderator_id = uuid4()
    ticket = make_ticket(product_id=product_id, status=TicketStatus.IN_REVIEW, claimed_by=moderator_id)
    repo.add(ticket)
    key = uuid4()

    event = make_event(
        B2BEventTypeEnum.PRODUCT_EDITED,
        product_id=product_id,
        seller_id=ticket.seller_id,
        json_before={'title': 'old'},
        json_after={'title': 'new'},
        idempotency_key=key,
    )
    await use_case(event)
    assert repo.by_id[ticket.id].status == TicketStatus.PENDING
    updates_after_first = len(repo.updated)

    # Имитируем дальнейшую работу модератора — дубликат НЕ должен её откатить.
    repo.by_id[ticket.id].status = TicketStatus.IN_REVIEW
    repo.by_id[ticket.id].claimed_by = moderator_id

    with pytest.raises(DuplicateEventError) as err:
        await use_case(event)

    assert err.value.status_code == 409
    assert err.value.code == 'DUPLICATE_EVENT'
    # Никаких side effects: тикет не тронут, новых create/update не было.
    assert repo.by_id[ticket.id].status == TicketStatus.IN_REVIEW
    assert repo.by_id[ticket.id].claimed_by == moderator_id
    assert len(repo.updated) == updates_after_first
    assert repo.created == []

    # Закрывает и out-of-order ретраи: повтор DELETED с тем же ключом тоже отбит.
    with pytest.raises(DuplicateEventError):
        await use_case(make_event(B2BEventTypeEnum.PRODUCT_DELETED, product_id=product_id, idempotency_key=key))
    assert repo.by_id[ticket.id].status == TicketStatus.IN_REVIEW


@pytest.mark.anyio
async def test_different_keys_create_separate_tickets():
    """Два PRODUCT_CREATED с разными idempotency_key → два независимых тикета."""
    repo = FakeTicketRepository()
    inbox = FakeInboxRepository()
    use_case = HandleB2BEventUseCase(ticket_repository=repo, inbox_repository=inbox)
    seller_id = uuid4()

    first = await use_case(
        make_event(
            B2BEventTypeEnum.PRODUCT_CREATED,
            product_id=uuid4(),
            seller_id=seller_id,
            json_after={'title': 'first'},
            idempotency_key=uuid4(),
        )
    )
    second = await use_case(
        make_event(
            B2BEventTypeEnum.PRODUCT_CREATED,
            product_id=uuid4(),
            seller_id=seller_id,
            json_after={'title': 'second'},
            idempotency_key=uuid4(),
        )
    )

    assert first.ticket_id is not None
    assert second.ticket_id is not None
    assert first.ticket_id != second.ticket_id
    assert len(repo.created) == 2
    assert len(inbox.keys) == 2
