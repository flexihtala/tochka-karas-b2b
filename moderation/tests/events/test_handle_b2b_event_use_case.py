from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.events.errors import TicketNotFoundForEditError
from apps.events.schemas.request import B2BEventPayloadSchema, B2BEventTypeEnum, IncomingB2BEventSchema
from apps.events.use_cases import HandleB2BEventUseCase
from apps.tickets.enums import TicketStatus
from tests.events.fakes import FakeTicketRepository, make_ticket_read_schema


def _make_event(
    event_type: B2BEventTypeEnum,
    *,
    product_id=None,
    seller_id=None,
) -> IncomingB2BEventSchema:
    return IncomingB2BEventSchema(
        event_type=event_type,
        idempotency_key=uuid4(),
        occurred_at=datetime.now(UTC),
        payload=B2BEventPayloadSchema(
            product_id=product_id or uuid4(),
            seller_id=seller_id or uuid4(),
            json_after={'title': 'Test product'},
        ),
    )


@pytest.mark.anyio
async def test_created_event_creates_pending_ticket():
    repo = FakeTicketRepository()
    use_case = HandleB2BEventUseCase(ticket_repository=repo)
    product_id = uuid4()
    seller_id = uuid4()

    response = await use_case(_make_event(B2BEventTypeEnum.PRODUCT_CREATED, product_id=product_id, seller_id=seller_id))

    assert response.ticket_id is not None
    assert len(repo.created) == 1
    created = repo.created[0]
    assert created.product_id == product_id
    assert created.seller_id == seller_id
    assert created.status == TicketStatus.PENDING.value


@pytest.mark.anyio
async def test_edited_event_resets_existing_ticket_to_pending():
    repo = FakeTicketRepository()
    product_id = uuid4()
    moderator_id = uuid4()
    existing = make_ticket_read_schema(
        product_id=product_id,
        status=TicketStatus.IN_REVIEW.value,
        claimed_by=moderator_id,
        claimed_at=datetime.now(UTC),
    )
    repo.add(existing)

    use_case = HandleB2BEventUseCase(ticket_repository=repo)
    response = await use_case(_make_event(B2BEventTypeEnum.PRODUCT_EDITED, product_id=product_id))

    assert response.ticket_id == existing.id
    assert len(repo.updated) == 1
    update = repo.updated[0]
    assert update.id == existing.id
    assert update.status == TicketStatus.PENDING.value
    # claim сбрасывается
    payload = update.model_dump(exclude_unset=True)
    assert payload.get('claimed_by') is None
    assert payload.get('claimed_at') is None
    # И в репозитории должно отразиться:
    assert repo.by_id[existing.id].status == TicketStatus.PENDING.value
    assert repo.by_id[existing.id].claimed_by is None


@pytest.mark.anyio
async def test_edited_event_returns_404_when_no_active_ticket():
    repo = FakeTicketRepository()
    use_case = HandleB2BEventUseCase(ticket_repository=repo)
    with pytest.raises(TicketNotFoundForEditError):
        await use_case(_make_event(B2BEventTypeEnum.PRODUCT_EDITED))


@pytest.mark.anyio
async def test_deleted_event_closes_existing_tickets():
    repo = FakeTicketRepository()
    product_id = uuid4()
    other_product_id = uuid4()
    pending = make_ticket_read_schema(product_id=product_id, status=TicketStatus.PENDING.value)
    in_review = make_ticket_read_schema(product_id=product_id, status=TicketStatus.IN_REVIEW.value)
    other = make_ticket_read_schema(product_id=other_product_id, status=TicketStatus.PENDING.value)
    repo.add(pending)
    repo.add(in_review)
    repo.add(other)

    use_case = HandleB2BEventUseCase(ticket_repository=repo)
    response = await use_case(_make_event(B2BEventTypeEnum.PRODUCT_DELETED, product_id=product_id))

    # Принимаем, ticket_id отсутствует (мы архивируем массово).
    assert response.ticket_id is None
    assert repo.by_id[pending.id].status == TicketStatus.ARCHIVED.value
    assert repo.by_id[in_review.id].status == TicketStatus.ARCHIVED.value
    # Другой товар — не затронут.
    assert repo.by_id[other.id].status == TicketStatus.PENDING.value
    assert product_id in repo.archived_product_ids


@pytest.mark.anyio
async def test_deleted_event_idempotent_when_no_tickets_for_product():
    repo = FakeTicketRepository()
    use_case = HandleB2BEventUseCase(ticket_repository=repo)

    response = await use_case(_make_event(B2BEventTypeEnum.PRODUCT_DELETED))

    assert response.ticket_id is None
    assert len(repo.archived_product_ids) == 1  # сам вызов archive_for_product был
    assert len(repo.created) == 0
    assert len(repo.updated) == 0


@pytest.mark.anyio
async def test_created_event_does_not_touch_existing_archived_ticket():
    """CREATED создаёт новый тикет даже если для product_id есть ARCHIVED — это новый CREATE-цикл."""
    repo = FakeTicketRepository()
    product_id = uuid4()
    archived = make_ticket_read_schema(product_id=product_id, status=TicketStatus.ARCHIVED.value)
    repo.add(archived)

    use_case = HandleB2BEventUseCase(ticket_repository=repo)
    response = await use_case(_make_event(B2BEventTypeEnum.PRODUCT_CREATED, product_id=product_id))

    assert response.ticket_id is not None
    assert response.ticket_id != archived.id
    # Новый ticket в PENDING; старый остался ARCHIVED.
    assert repo.by_id[archived.id].status == TicketStatus.ARCHIVED.value
    assert repo.by_id[response.ticket_id].status == TicketStatus.PENDING.value
