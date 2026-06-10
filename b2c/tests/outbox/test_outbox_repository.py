"""Юнит-тесты B2COutboxRepository — модель + конкретизация generic.

Тесты SQLAlchemy-репозитория с реальной БД здесь не делаем (нет фикстуры PG),
но проверяем что:
- B2COutboxRepository наследуется от shared.outbox.OutboxRepository;
- model_type корректно зафиксирован;
- модель OutboxEvent определяет ожидаемые колонки (через __tablename__ / columns).
"""

from apps.outbox.models import OutboxEvent
from apps.outbox.repositories import B2COutboxRepository
from shared.outbox import OutboxRepository


def test_repository_is_subclass_of_generic():
    assert issubclass(B2COutboxRepository, OutboxRepository)


def test_repository_model_type_is_outbox_event():
    assert B2COutboxRepository.model_type is OutboxEvent


def test_outbox_event_tablename():
    assert OutboxEvent.__tablename__ == 'outbox'


def test_outbox_event_has_required_columns():
    columns = {c.name for c in OutboxEvent.__table__.columns}
    expected = {
        'id',
        'idempotency_key',
        'event_type',
        'target_service',
        'payload',
        'status',
        'retry_count',
        'next_retry_at',
        'sent_at',
        'last_error',
        'created_at',
        'updated_at',
    }
    assert expected.issubset(columns)


def test_outbox_event_idempotency_key_unique():
    col = OutboxEvent.__table__.c.idempotency_key
    assert col.unique is True
