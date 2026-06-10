from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.blocking_reasons.repositories import BlockingReasonRepository
from apps.outbox.repositories import ModerationOutboxRepository
from apps.tickets.enums import FieldReportName, TicketStatus
from apps.tickets.errors import (
    InvalidFieldNameError,
    TicketNotFoundError,
    TicketNotOwnerError,
    TicketTerminalError,
    TicketWrongStatusError,
    UnknownBlockingReasonError,
)
from apps.tickets.repositories import TicketRepository
from apps.tickets.schemas.db import TicketUpdateSchema
from apps.tickets.schemas.request import BlockTicketRequestSchema, FieldReportSchema
from apps.tickets.schemas.response import TicketResponseSchema
from shared.auth_lib import UserRole
from shared.db import SessionManager
from shared.outbox import OutboxEnqueueSchema
from shared.types import ServiceName


class BlockTicketUseCase:
    """POST /api/v1/tickets/{id}/block — заблокировать товар (soft или hard).

    Тело запроса (BlockDecisionRequest по спеке): blocking_reason_ids (array, minItems=1),
    comment (опц.), field_reports (опц.).

    hard_block выводится из выбранных причин: если ХОТЯ БЫ ОДНА причина hard_block=true,
    результирующий статус — HARD_BLOCKED (терминальный, продавец не может исправить).
    Иначе — BLOCKED (продавец может отредактировать и пройти модерацию заново).

    Коды ошибок по канону MOD-4 (moderation-flows.md#soft-block):
    - чужой тикет → 403 (TicketNotOwnerError), как в approve;
    - неизвестная/неактивная причина → 400 (UnknownBlockingReasonError);
    - field_name вне enum FieldReportName → 400 (InvalidFieldNameError).

    field_reports персистятся на тикете (JSONB-колонка): каждый block ПОЛНОСТЬЮ заменяет
    предыдущий список (канон, шаги 10-11: DELETE старых + INSERT новых); пустой запрос
    очищает замечания значением [] (не None — колонка NOT NULL).
    """

    def __init__(
        self,
        ticket_repository: TicketRepository,
        blocking_reason_repository: BlockingReasonRepository,
        outbox_repository: ModerationOutboxRepository,
        session_manager: SessionManager,
    ):
        self.ticket_repository = ticket_repository
        self.blocking_reason_repository = blocking_reason_repository
        self.outbox_repository = outbox_repository
        self.session_manager = session_manager

    async def __call__(
        self,
        ticket_id: UUID,
        data: BlockTicketRequestSchema,
        moderator_id: UUID,
        role: UserRole,
    ) -> TicketResponseSchema:
        # Доменная валидация тела запроса — до обращения к ресурсам (как pydantic-валидация).
        field_reports = self._validate_field_reports(data.field_reports)

        ticket = await self.ticket_repository.get_or_none(ticket_id)
        if ticket is None:
            raise TicketNotFoundError()

        # HARD_BLOCKED — терминальный статус: 403 (необратимость), не generic 409.
        if ticket.status == TicketStatus.HARD_BLOCKED:
            raise TicketTerminalError()

        if ticket.status != TicketStatus.IN_REVIEW:
            raise TicketWrongStatusError()

        # Канон MOD-4, шаг 5: чужая карточка → 403 Forbidden (Not assigned to you).
        if role != UserRole.ADMIN and ticket.claimed_by != moderator_id:
            raise TicketNotOwnerError()

        # Резолвим все причины (валидация всех ID, не только первого).
        # Канон MOD-4, шаг 7: неизвестная причина → 400 Bad Request.
        reasons = []
        for reason_id in data.blocking_reason_ids:
            reason = await self.blocking_reason_repository.get_or_none(reason_id)
            if reason is None or not reason.is_active:
                raise UnknownBlockingReasonError()
            reasons.append(reason)

        hard_block = any(r.hard_block for r in reasons)
        result_status = TicketStatus.HARD_BLOCKED if hard_block else TicketStatus.BLOCKED
        idempotency_key = uuid4()
        now = datetime.now(UTC)
        # Модель пока хранит одну FK — кладём первую причину; полный список идёт в outbox payload.
        primary_reason_id = data.blocking_reason_ids[0]
        # Канонический вид замечаний для персистенса и события (field_name/sku_id/comment;
        # field_path сохраняется для legacy-формы).
        serialized_reports = [fr.model_dump(mode='json') for fr in field_reports]

        async with self.session_manager.get_session() as session:
            updated = await self.ticket_repository.update_in_session(
                session,
                TicketUpdateSchema(
                    id=ticket_id,
                    status=result_status,
                    decision_at=now,
                    blocking_reason_id=primary_reason_id,
                    moderator_comment=data.comment,
                    # Полная замена замечаний при каждом (пере)блокировании; [] очищает.
                    field_reports=serialized_reports,
                ),
            )
            if updated is None:
                raise TicketNotFoundError()

            payload: dict[str, object] = {
                'product_id': str(updated.product_id),
                'blocking_reason_ids': [str(rid) for rid in data.blocking_reason_ids],
                'comment': data.comment,
                'hard_block': hard_block,
                'field_reports': serialized_reports,
                'idempotency_key': str(idempotency_key),
            }

            # B2B-контракт (ModerationEventRequest, US-B2B-09) знает только event_type
            # MODERATED|BLOCKED. Жёсткость передаётся ОТДЕЛЬНЫМ булевым полем hard_block
            # в payload — поэтому event_type всегда BLOCKED (и для soft, и для hard).
            await self.outbox_repository.enqueue(
                session,
                OutboxEnqueueSchema(
                    idempotency_key=idempotency_key,
                    event_type='BLOCKED',
                    target_service=ServiceName.B2B,
                    payload=payload,
                ),
            )

            return TicketResponseSchema.model_validate(updated)

    @staticmethod
    def _validate_field_reports(field_reports: list[FieldReportSchema] | None) -> list[FieldReportSchema]:
        """Проверяет field_name каждого замечания против enum FieldReportName (канон MOD-4).

        field_name опционален (legacy-форма шлёт field_path), но если указан —
        обязан входить в enum, иначе 400 INVALID_FIELD_NAME.
        """
        reports = field_reports or []
        for report in reports:
            if report.field_name is not None and report.field_name not in FieldReportName:
                allowed = ', '.join(name.value for name in FieldReportName)
                raise InvalidFieldNameError(
                    f'Недопустимый field_name {report.field_name!r}; допустимые значения: {allowed}',
                )
        return reports
