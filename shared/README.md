# shared/ — общая инфраструктура

Будет содержать переиспользуемые модули для b2b, moderation, b2c:

- `auth_lib/` — JWT-сервис, AuthMiddleware, password hasher.
- `db/` — DBCrudRepository, SessionManager, базовые миксины.
- `outbox/` — таблица outbox + воркер (transactional outbox pattern).
- `inbox/` — processed_events для idempotency, X-Service-Key middleware.
- `http_clients/` — httpx-клиент с X-Service-Key для service-to-service вызовов.
- `errors/` — AppError + error handlers FastAPI.

Заполняется в PR `forge/karas/shared-scaffold` (Phase 1).
