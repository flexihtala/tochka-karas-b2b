"""ADR — Idempotency для входящих событий (US-B2B-09).

Решение: использовать таблицу `processed_events` с UNIQUE-ограничением по
(sender_service, idempotency_key) и обёртку `shared.inbox.IdempotentHandler`,
которая на лету определяет дубликат, отдаёт cached-payload и обрабатывает
race-condition через IntegrityError при параллельных вставках.

Альтернативы:
- Поле `last_event_key` на товаре — недостаточно: один товар может получать
  события от разных продьюсеров и в произвольном порядке; ключ должен быть
  глобальным.
- Только UNIQUE на outbox — outbox решает доставку исходящих, не приём.
  Inbox нужен отдельной таблицей.
- Upsert ON CONFLICT — не позволяет вернуть cached-ответ повторному клиенту.

Критерии выбора: безопасность гонок (UNIQUE + IntegrityError-fallback на
повторный SELECT), простота обслуживания (TTL-чистка по `created_at`),
переиспользование между сервисами (общий mixin/handler в shared.inbox).
"""
