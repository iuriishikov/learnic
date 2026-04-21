# Learnic

Backend-сервис на **Clean Architecture** со строгим разделением слоёв,
CQRS-паттерном для персистентности и императивным маппингом SQLAlchemy.

Ветка `bootstrap` содержит инфраструктурную основу — DI, конфигурация,
брокер фоновых задач, S3-хранилище, email-транспорт — поверх которой
дальше разворачиваются продуктовые агрегаты и use-case'ы.

---

## Стек

| Слой | Технология |
|---|---|
| Язык | Python 3.14 |
| HTTP | FastAPI + uvicorn (gunicorn в проде) |
| БД | PostgreSQL 16, SQLAlchemy 2 (async `asyncpg` в приложении, sync `psycopg` для Alembic) |
| Миграции | Alembic |
| Фоновые задачи | TaskIQ + Redis (`taskiq-redis`) |
| Объектное хранилище | S3-совместимое (`aioboto3`), локально MinIO |
| Email | Rusender через `httpx` |
| DI | dishka |
| Валидация | Pydantic 2 (на HTTP-границе и в конфигах) |
| TLS на проде | Caddy с автоматическим ACME |
| Пакеты | Poetry 2 |
| Тесты | pytest + pytest-asyncio + httpx (ASGI transport) |
| Качество кода | ruff, mypy (strict), bandit, semgrep, codespell |
| Локальный оркестратор | `just` + `docker compose` |

---

## Архитектура

Зависимости текут **только внутрь**:

```
presentation ─▶ application ─▶ entities
                     ▲
infrastructure ──────┘        (реализует application-протоколы)
```

- `entities/` — чистый домен: сущности, VO, доменные ошибки. Нулевые внешние импорты.
- `application/` — use-case'ы, `Protocol`-границы (`Transaction`, `*Gateway`, `*Reader`, `TaskScheduler`, `FileStorage`, `EmailSender`). Ничего не знает про FastAPI, SQLAlchemy или dishka.
- `infrastructure/` — адаптеры: SQLAlchemy-мапперы, S3, Rusender, TaskIQ-брокер и таски.
- `presentation/http/` — роуты FastAPI, Pydantic-схемы, exception handlers.

Полные архитектурные правила и чек-листы добавления новых use-case'ов / агрегатов — в [`CLAUDE.md`](./CLAUDE.md).

---

## Структура репозитория

```
src/learnic/
├── application/
│   ├── commands/                 # командные хендлеры (write-side)
│   ├── queries/                  # query-хендлеры (read-side)
│   └── common/
│       ├── email/sender.py       # EmailSender Protocol
│       ├── persistence/          # Transaction, EntitySaver, *Gateway, *Reader
│       ├── storage/file_storage.py
│       └── tasks/scheduler.py    # TaskScheduler Protocol
├── entities/
│   ├── common/                   # BaseEntity, DomainError, FieldError
│   └── user/                     # User + VO + errors + constants
├── infrastructure/
│   ├── configs.py                # BaseSettings: Postgres, ASGI, S3, TaskIQ, Rusender
│   ├── email/adapters/rusender.py
│   ├── persistence/
│   │   ├── adapters/             # *MapperAlchemy, TransactionAlchemy
│   │   ├── alembic/              # миграции
│   │   └── models/               # sa.Table + map_<aggregate>_table()
│   ├── storage/adapters/s3.py
│   └── tasks/
│       ├── broker.py             # singleton AsyncBroker
│       ├── scheduler.py          # TaskSchedulerTaskIQ адаптер
│       └── handlers/             # @broker.task функции
├── presentation/http/routes/
├── static/                       # статика, раздаётся с корня (/)
├── bootstrap.py                  # setup_configs, setup_routes, setup_map_tables
├── ioc.py                        # dishka-провайдеры
├── web.py                        # create_app_production / create_app_tests
├── __main__.py                   # прод-энтрипоинт API (uvicorn)
└── worker.py                     # энтрипоинт TaskIQ-воркера
```

---

## Быстрый старт

### Требования

- Python 3.14
- Poetry ≥ 2.0
- Docker + Docker Compose
- `just` (`brew install just`)

### Установка

```bash
git clone <repo-url> learnic && cd learnic
just bootstrap           # копирует .env.dist → .env, ставит зависимости
```

### Конфигурация

`just bootstrap` скопирует `.env.dist` в `.env`. Отредактируй `.env` под себя — секция **Environment** ниже поясняет ключи. Обязательный ручной шаг: `S3_SECRET_KEY` должен быть ≥ 8 символов (требование MinIO).

### Запуск

```bash
just serve
```

Эта команда:

1. Поднимает Postgres, MinIO и Redis через `docker-compose.dev.yaml`.
2. Прогоняет `alembic upgrade head`.
3. Параллельно стартует **FastAPI с `--reload`** и **TaskIQ-воркер с `--reload`**.

API доступен на `http://localhost:8000`. Swagger — `http://localhost:8000/docs`.

---

## Процесс разработки

### Запуск только воркера

```bash
just worker
```

Удобно, когда хочется дебажить таски без HTTP-шума.

### Линтеры и форматтер

```bash
just lint               # ruff check + ruff format + codespell (быстро, каждые 30 сек)
```

### Статический анализ

```bash
just static             # mypy strict + bandit + semgrep (дольше, перед пушем)
```

### Тесты

Smoke-набор на `httpx.AsyncClient + ASGITransport` — без поднятия HTTP-сервера, прямо в память:

```bash
poetry run pytest                    # весь набор
poetry run pytest -v                 # с именами тестов
poetry run pytest -k healthcheck     # по фильтру
```

### Поднятие / опускание dev-стека

```bash
just dev-up              # Postgres + MinIO + Redis (+ создание бакета)
just dev-down            # остановить и удалить контейнеры (volumes сохраняются)
```

---

## Справка по командам (`just`)

| Рецепт | Назначение |
|---|---|
| `bootstrap` | Первичная установка: копирование `.env`, `poetry install` |
| `serve` | Локальный запуск API + воркера в параллели (с миграциями и `--reload`) |
| `worker` | Только TaskIQ-воркер |
| `lint` | Быстрая проверка стиля и опечаток (ruff + codespell) |
| `static` | Глубокая проверка типов и безопасности (mypy + bandit + semgrep) |
| `dev-up` / `dev-down` | Подъём / остановка dev-инфраструктуры в Docker |
| `prod-up` / `prod-down` | Сборка и запуск прод-подобного стека с Caddy |

---

## Environment

`.env.dist` — шаблон. `just bootstrap` копирует его в `.env`, дальше правь под себя.

### PostgreSQL

| Переменная | Обязательная | Описание |
|---|---|---|
| `POSTGRES_USER` | ✓ | Пользователь БД |
| `POSTGRES_PASSWORD` | ✓ | Пароль |
| `POSTGRES_HOST` | ✓ | Хост (`postgres` внутри compose, `localhost` вне) |
| `POSTGRES_PORT` | ✓ | Порт (обычно `5432`) |
| `POSTGRES_DB` | ✓ | Имя БД |
| `SQLALCHEMY_DEBUG` | ✗ | `1` — логирует SQL-запросы (`echo=True`) |

### Uvicorn / FastAPI

| Переменная | Обязательная | Описание |
|---|---|---|
| `UVICORN_HOST` | ✓ | Интерфейс биндинга (`0.0.0.0` внутри контейнера) |
| `UVICORN_PORT` | ✓ | Порт (обычно `8000`) |
| `FASTAPI_DEBUG` | ✗ | `1` включает debug-режим FastAPI |

### S3 / MinIO

| Переменная | Обязательная | Описание |
|---|---|---|
| `S3_ENDPOINT` | ✓ | URL S3-сервиса (`http://localhost:9000` для локального MinIO) |
| `S3_ACCESS_KEY` | ✓ | Access key; для MinIO ≥ 3 символов |
| `S3_SECRET_KEY` | ✓ | Secret key; для MinIO **≥ 8 символов** |
| `S3_BUCKET` | ✓ | Имя бакета |
| `S3_REGION` | ✗ | Регион (по умолчанию `us-east-1`) |

### TaskIQ / Redis

| Переменная | Дефолт | Описание |
|---|---|---|
| `TASKIQ_BROKER_URL` | `redis://localhost:6379/0` | URL брокера |
| `TASKIQ_RESULT_BACKEND_URL` | `redis://localhost:6379/1` | URL хранилища результатов |
| `TASKIQ_IN_MEMORY` | `false` | `true` — `InMemoryBroker` для тестов/одноразового дева |
| `TASKIQ_WORKERS` | `2` | Количество воркер-процессов (игнорируется при `--reload`) |

### Rusender (email)

| Переменная | Обязательная | Описание |
|---|---|---|
| `RUSENDER_API_KEY` | ✓ | Ключ API с https://beta.rusender.ru/api |
| `RUSENDER_FROM_EMAIL` | ✓ | Адрес отправителя (должен быть верифицирован на стороне Rusender) |
| `RUSENDER_FROM_NAME` | ✗ | Отображаемое имя отправителя |

### Деплой / Caddy

| Переменная | Описание |
|---|---|
| `DOMAIN` | Доменное имя для ACME-сертификата |
| `ACME_EMAIL` | Email для Let's Encrypt (уведомления о продлении) |

---

## Деплой

Прод-стек описан в `docker-compose.yaml`: Postgres → migrate-контейнер → app → Caddy. TLS-сертификат выдаётся автоматически через Let's Encrypt при первом запуске.

```bash
# на сервере с Docker
git clone <repo-url> /opt/learnic && cd /opt/learnic
cp .env.dist .env    # отредактировать: реальные секреты, DOMAIN, ACME_EMAIL
just prod-up
```

Проверка:

```bash
curl -I https://<your-domain>/healthz    # 200 OK — Caddy жив
curl -I https://<your-domain>/healthcheck # 200 OK — приложение жив
```

**Важно**: текущий `docker-compose.yaml` ещё не содержит сервисов Redis и воркера — их нужно добавить при необходимости фоновой обработки в проде (см. секцию TaskIQ в CLAUDE.md).

---

## Для агентов и будущих разработчиков

[`CLAUDE.md`](./CLAUDE.md) — полная архитектурная документация: правила слоёв, канонические паттерны (VO, Entity, CommandHandler, route, TaskIQ-таска), анти-паттерны и чек-листы добавления новых use-case'ов и агрегатов. Перед первым коммитом в проект — читать обязательно.

---

## Лицензия

Пока не определена.
