# tochka-karas-b2b — NeoMarket Platform Monorepo

Монорепо команды «Карась» с реализацией NeoMarket по новому протоколу
([URFU2026-NeoMarket/neomarket-protocols](https://github.com/URFU2026-NeoMarket/neomarket-protocols)).

Три сервиса, каждый со своей БД, общаются только через HTTP API:

```
┌──────┐  HTTP+X-Service-Key  ┌────────────┐  HTTP+X-Service-Key  ┌──────┐
│ B2C  │────────────────────► │     B2B    │ ◄──────────────────── │ Mod  │
└──────┘                      └────────────┘                       └──────┘
   │                                │                                │
   ▼                                ▼                                ▼
postgres-b2c                  postgres-b2b                   postgres-moderation
  :5435                         :5433                            :5434
```

## Структура

- `b2b/` — кабинет продавца (US-B2B-01..12). Управление товарами, SKU, накладными, инвентарём.
- `moderation/` — модерация товаров (без квестов, по спеке). Очередь, тикеты, причины блокировки.
- `b2c/` — витрина покупателя (US-CAT/CART/ORD-XX). Каталог, корзина, избранное, заказы.
- `shared/` — общая инфраструктура (auth, DB-helpers, outbox, inbox, http-clients, errors).

## Стек

Python 3.14, FastAPI, SQLAlchemy 2.0 (async, asyncpg), Postgres 16, dishka, alembic, uv, ruff.

## Локальный запуск

```bash
# Запустить все 3 Postgres
docker compose up -d

# Поднять b2b
cd b2b
cp .env.example .env  # отредактируй при необходимости
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn cmd.rest:app --port 8001 --reload
```

Аналогично для `moderation/` (порт 8002) и `b2c/` (порт 8003) — после их bootstrap.

## Тесты

```bash
cd b2b && uv run pytest -v
```

## Roadmap

См. план реализации в `/Users/q/.claude/plans/m2-prancy-sparrow.md` (локально у автора).

7 фаз → ~31 PR в этом репо + ~10 gap-PR в `neomarket-protocols`.

## Контракты

- Protocols: <https://github.com/URFU2026-NeoMarket/neomarket-protocols>
- Канонические сценарии: <https://github.com/URFU2026-NeoMarket/neomarket-canon>
- Квесты: <https://contract.tochka-urfu.tech>
