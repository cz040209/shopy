<img width="1506" height="714" alt="Screenshot 2026-08-26 at 3 39 25 PM" src="https://github.com/user-attachments/assets/0908644a-8f59-4e40-a8e1-a196863b4fed" />
# Shopy AI

Shopy AI is a full-stack e-commerce platform: a Next.js storefront, FastAPI commerce API, PostgreSQL catalog, Redis short-term memory, and a LangChain/LangGraph shopping assistant.

> Checkout creates pending payment records only. It is not a production payment integration.

## What is included

- Catalog, categories, sellers, reviews, carts, orders, wallets, and authentication
- Text chat, local voice transcription, and image shopping
- Agentic catalog search, planning, bundle support, and final response auditing
- Redis-backed 30-minute shopping memory for mission, budget, preferences, constraints, bundle state, and product decisions
- Persisted agent-run observability for nodes, tools, audits, and repairs

## Architecture

```text
Next.js storefront :3002
      │ HTTP + cookie credentials
      ▼
FastAPI API :8000
  ├── PostgreSQL :5433  — catalog, users, commerce, conversations, run logs
  ├── Redis :6380       — expiring short-term shopping memory
  ├── Gemini            — intent, planning, vision, writing, semantic audit
  └── Faster-Whisper    — local speech-to-text
```

### Agent workflow

```text
Request → Redis memory load → intent → planning/manager → catalog tools
        → response draft → audit → brand voice → final audit
        → Redis memory update → response
```

Catalog tools are the source of truth for product facts. The auditor validates selected products, stock, pricing, constraints, fulfillment, and unsupported claims before delivery.

## Repository layout

```text
frontend/                 Next.js 16 + React 19 UI
backend/                  FastAPI, Alembic, Poetry, LangGraph agents
  app/agentic/            Orchestration, tools, audit, planning, Redis memory
  app/api/routes/         HTTP endpoints
  app/scripts/            Catalog seed scripts
  migrations/             Database migrations
  tests/                  Backend tests
docker-compose.yml        Local PostgreSQL and Redis
```

## Prerequisites

- Node.js 20+ and npm
- Python 3.11–3.14
- [Poetry](https://python-poetry.org/)
- Docker Desktop / Docker Compose
- Gemini API key

## Quick start

### 1. Create local environment files

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Set these values in `backend/.env`:

```env
GEMINI_API_KEY=your_gemini_api_key
POSTGRES_PASSWORD=choose_a_local_password
DATABASE_URL=postgresql+psycopg://shopy:choose_a_local_password@localhost:5433/shopy
REDIS_PORT=6380
REDIS_URL=redis://localhost:6380/0
FRONTEND_ORIGIN=http://localhost:3002
```

The frontend uses:

```env
NEXT_PUBLIC_ASSISTANT_API_URL=http://localhost:8000
```

### 2. Start PostgreSQL and Redis

```bash
docker compose --env-file backend/.env up -d
docker compose ps
```

PostgreSQL is exposed on `5433`; Redis is exposed on `6380` to avoid conflicts with another local Redis instance. If the backend runs in the Docker network, use `REDIS_URL=redis://redis:6379/0`.

### 3. Install, migrate, and seed the backend

```bash
cd backend
poetry install
poetry run alembic upgrade head
poetry run python -m app.scripts.seed_catalog
poetry run python -m app.scripts.seed_apparel_catalog
poetry run python -m app.scripts.seed_furniture_catalog
```

Seed scripts are safe to rerun: known SKUs are updated rather than duplicated.

### 4. Start FastAPI

```bash
cd backend
poetry run uvicorn app.main:app --reload --port 8000
```

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/database
```

### 5. Start the frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev -- --port 3002
```

Open [http://localhost:3002](http://localhost:3002).

## Configuration

Never commit `backend/.env` or `frontend/.env.local`.

| Variable | Purpose | Local default |
| --- | --- | --- |
| `GEMINI_API_KEY` | Gemini API credential | required |
| `GEMINI_MODEL` | Gemini model | `gemini-2.5-flash-lite` |
| `FRONTEND_ORIGIN` | Allowed browser origin | `http://localhost:3002` |
| `DATABASE_URL` | PostgreSQL connection URL | Postgres on `5433` |
| `POSTGRES_PORT` | Host PostgreSQL port | `5433` |
| `REDIS_URL` | Redis memory URL | `redis://localhost:6380/0` |
| `REDIS_PORT` | Host Redis port | `6380` |
| `SHOPPING_MEMORY_TTL_SECONDS` | Memory inactivity expiry | `1800` |
| `SHOPPING_MEMORY_RECENT_TURNS` | Recent turns retained | `8` |
| `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE` | Voice settings | `small`, `cpu`, `int8` |
| `AI_LOG_CUSTOMER_INPUT` | Log customer text locally | `true` |

Agent limits are configurable with `AGENT_MAX_GRAPH_ITERATIONS`, `AGENT_MAX_TOOL_CALLS`, `AGENT_MAX_REPAIR_ATTEMPTS`, `AGENT_RESPONSE_FORMAT_ATTEMPTS`, `AGENT_MODEL_TIMEOUT_SECONDS`, and `AGENT_TOOL_TIMEOUT_SECONDS`.

## Redis short-term memory

- Scope: authenticated user + auth session, or anonymous conversation session
- TTL: 30 minutes of inactivity; refreshed on memory load and update
- Stored context: rolling summary, recent turns, active mission, budget, preferences, constraints, owned items, viewed/selected/rejected products, bundle state, and optimization mode
- Security: keys contain a SHA-256 digest of the session scope; authenticated logout clears its memory
- Resilience: the request continues without memory if Redis is unavailable

The Intent Agent decides if a message continues the prior mission. For example, “Make it cheaper” can use the earlier budget; an unrelated request does not inherit old constraints.

## API overview

Interactive API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

| Area | Endpoints |
| --- | --- |
| Health | `GET /health`, `GET /health/database` |
| Auth | `POST /api/v1/auth/register`, `login`, `logout`; `GET /me` |
| Catalog | `/api/v1/products`, categories, sellers, product details, reviews |
| Commerce | Cart CRUD, checkout, orders, wallet, and product reviews under `/api/v1` |
| Assistant | `POST /api/chat` |
| Voice | `POST /api/v1/transcribe` with multipart `audio` |
| Vision | `POST /api/v1/shopping/missions/vision` with multipart `image` and `mode` |
| Agent history | Authenticated `/api/v1/agentic/runs` endpoints |

### Chat example

```bash
curl -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Build me a wireless gaming setup under RM4,000"}]}'
```

The browser frontend manages cookies automatically. Preserve login cookies when testing protected endpoints with `curl`.

## Voice and vision

`POST /api/v1/transcribe` accepts WebM, WAV, MP3, M4A/MP4, and OGG. Audio exists in a temporary file only during Faster-Whisper decoding.

```bash
curl -X POST http://localhost:8000/api/v1/transcribe \
  -F 'audio=@/path/to/recording.webm;type=audio/webm'
```

The vision endpoint accepts JPEG, PNG, and WebP images up to 10 MB for room shopping, outfit completion, and similar/complementary product searches. Raw image bytes are not persisted in orchestration logs.

## Observability

Each request has a short request ID. `orchestration_runs` and `orchestration_run_events` store observable node transitions, tool activity, audits, repairs, and outputs. Hidden chain-of-thought is not stored.

Set `AI_LOG_CUSTOMER_INPUT=false` to redact customer text from terminal logs.

```sql
SELECT r.request_id, r.status, e.sequence, e.event_type, e.node_name,
       e.tool_name, e.input_data, e.output_data, e.error_message
FROM orchestration_runs r
JOIN orchestration_run_events e ON e.run_id = r.id
ORDER BY r.created_at DESC, e.sequence;
```

## Development commands

```bash
# Backend
cd backend
poetry run pytest
poetry check
poetry run alembic upgrade head

# Frontend
cd frontend
npm run lint
npm run build

# Infrastructure
docker compose --env-file backend/.env up -d
docker compose logs -f postgres redis
docker compose down
```

`docker compose down` retains named volumes. Removing `shopy_postgres_data` or `shopy_redis_data` permanently deletes local development data.

## Troubleshooting

### `ModuleNotFoundError: No module named 'sqlalchemy'`

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```

### Database or Redis connection error

```bash
docker compose ps
docker compose logs postgres redis
curl http://localhost:8000/health/database
```

Ensure `POSTGRES_PASSWORD` matches `DATABASE_URL`, and use `REDIS_URL=redis://localhost:6380/0` when FastAPI runs on your host machine.

### Browser CORS error

Set `FRONTEND_ORIGIN` to the frontend URL, restart FastAPI, and verify `NEXT_PUBLIC_ASSISTANT_API_URL` points to the backend.

### Gemini error

Confirm `GEMINI_API_KEY` is set in `backend/.env`, restart the backend, and never place it in a frontend variable.

## Before pushing to GitHub

- [ ] Keep `.env`, `.env.local`, credentials, virtual environments, and build output out of Git
- [ ] Update `.env.example` files without real secrets
- [ ] Run `poetry run pytest` in `backend/`
- [ ] Run `npm run lint` and `npm run build` in `frontend/`
- [ ] Review `git status` and commit only intended files
- [ ] Add a license before public distribution

## License

Add a project license before publishing or distributing this repository.
