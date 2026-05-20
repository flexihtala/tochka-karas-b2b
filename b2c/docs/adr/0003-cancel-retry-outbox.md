# ADR-0003: Асинхронный ретрай unreserve при отмене — outbox-pattern

**Статус**: принято (US-ORD-03).

## Контекст

При отмене заказа B2C дёргает `POST /api/v1/inventory/unreserve` у B2B.
Если B2B недоступен (5xx/timeout), мы не можем оставить заказ в статусе PAID
(покупатель сказал "отмени") и не можем сделать CANCELLED (резерв в B2B не снят).

Канон (b2c-orders-flows.md, §"CANCEL_PENDING — async retry") предписывает:
1. Перевести заказ в `CANCEL_PENDING`.
2. Асинхронно ретраить unreserve до успеха → потом перевести в `CANCELLED`.

Нужно выбрать механизм асинхронного ретрая.

## Рассмотренные варианты

1. **Outbox pattern** (выбран): INSERT в `outbox(target=b2b, event=UNRESERVE_ORDER)`,
   воркер периодически дёргает и помечает SENT/RETRY/FAILED. Использует общий
   `shared.outbox.OutboxWorker` + `shared.outbox.OutboxFieldsMixin`.
2. Celery task с RabbitMQ/Redis brokerom — отдельная инфраструктура.
3. Cron + management command — низкая отзывчивость, нет встроенного backoff.

## Решение

Outbox-таблица `outbox` в b2c с тем же контрактом, что и в b2b. При
неудачном unreserve:

```python
await outbox_repository.enqueue_in_new_transaction(
    OutboxEnqueueSchema(
        idempotency_key=uuid4(),
        event_type='UNRESERVE_ORDER',
        target_service=ServiceName.B2B,
        payload={'order_id': str(order.id), 'items': [...]},
    )
)
order.status = CANCEL_PENDING
```

Воркер (`shared.outbox.OutboxWorker`) опрашивает PENDING-события с
exponential backoff (30s → 60s → 120s ... до 10 попыток → FAILED).

В MVP воркер запускается в lifespan FastAPI (отдельный процесс — задача
последующих PR'ов).

## Обоснование

- **Единая инфраструктура** между сервисами (b2b уже использует тот же
  shared.outbox для PRODUCT_BLOCKED/SKU_OUT_OF_STOCK).
- **Транзакционная гарантия**: INSERT в outbox идёт в одной транзакции с
  обновлением статуса — невозможно "потерять" событие.
- **Идемпотентность на стороне получателя**: B2B unreserve идемпотентен по
  `idempotency_key` через inbox — ретраи безопасны.
- **Без внешних зависимостей**: Postgres достаточно, ни Redis ни RabbitMQ.

## Что отбросили и почему

- **Celery** — оверкилл для одного воркера: лишний broker, отдельный процесс,
  больше точек отказа.
- **Cron management command** — низкая отзывчивость (минимум одна минута),
  нет встроенного backoff, нет дедупликации параллельных воркеров.
