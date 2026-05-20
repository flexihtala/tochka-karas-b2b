# ADR-0004: Триггер fulfill при DELIVERED — явный use-case + outbox

**Статус**: принято (US-ORD-05).

## Контекст

При переходе заказа в `DELIVERED` B2C должен вызвать `POST /api/v1/inventory/fulfill`
у B2B — иначе `reserved_quantity` в B2B растёт бесконечно
(см. canon `flows/b2c-orders-flows.md#b2c-13-fulfill`).
Нужно выбрать механизм триггера и обеспечить идемпотентность + retry на сбоях B2B.

## Рассмотренные варианты

1. **Django `post_save`-signal на `Order`** — автомагия, не нужно дёргать руками.
   Минусы: трудно тестировать (сигнал срабатывает в неожиданных контекстах,
   например, миграции/dataload, обновления полей не связанных со статусом),
   неявная зависимость, повторный INSERT outbox при любом сохранении DELIVERED-заказа.
2. **Django Admin action / `save_model`** — кнопка в админке вызывает API B2B напрямую.
   Минусы: смешивает UI-слой и бизнес-логику, на сбое 5xx админ видит ошибку, retry
   только ручной; в тестах нужно поднимать Admin.
3. **Явный use-case `MarkDeliveredUseCase`** (выбран): тонкий доменный объект,
   принимает `order_id`, валидирует переход, кладёт `FULFILL_ORDER` в outbox в
   одной транзакции с `Order.status = DELIVERED`. Admin / management command —
   просто тонкий вызывающий слой.

## Решение

Реализуем `MarkDeliveredUseCase`. Любой триггер (Django Admin action, management
command, будущий internal endpoint) проходит через него.

- Только переход `DELIVERING -> DELIVERED` валиден; повторный вызов на уже
  `DELIVERED`-заказе — идемпотентный no-op, outbox не дублируется.
- Outbox-воркер (`shared.outbox.OutboxWorker`) асинхронно вызывает B2B fulfill;
  при 5xx/timeout планирует ретрай с exponential backoff (см. ADR-0003).
- Идемпотентность на стороне B2B — по `order_id` (канон, §"идемпотентно, no-op").

## Обоснование

- **Явный API** для смены статуса — единая точка валидации переходов; легко
  тестировать в изоляции (тесты в `tests/orders/test_mark_delivered_use_case.py`).
- **Переиспользование outbox-инфраструктуры** US-ORD-03 — никакой новой
  инфраструктуры, тот же воркер, тот же backoff, та же таблица.
- **Без скрытых сигналов** — DELIVERED-переход всегда явный и наблюдаемый;
  миграции / админские update не способны случайно триггернуть fulfill.

## Что отбросили и почему

- **`post_save`-signal** — слишком много неявных триггеров, сложнее тесты,
  риск дублирующих INSERT в outbox.
- **Прямой вызов B2B из Admin** — сбой B2B рушит UX; нет встроенного retry;
  логика "DELIVERED + fulfill" размазана по UI-слою.
