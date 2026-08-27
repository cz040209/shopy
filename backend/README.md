# Shopy AI backend

The FastAPI server keeps `GEMINI_API_KEY` on the server, provides chat and vision endpoints, and transcribes user-confirmed voice recordings locally with Faster-Whisper.

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and replace the example PostgreSQL password.
docker compose --env-file backend/.env up -d postgres

cd backend
poetry install
poetry run alembic upgrade head
poetry run python -m app.scripts.seed_catalog
poetry run python -m app.scripts.seed_apparel_catalog
poetry run python -m app.scripts.seed_furniture_catalog
poetry run python -m app.scripts.seed_travel_catalog
poetry run uvicorn app.main:app --reload --port 8000
```

The API connects to PostgreSQL through `DATABASE_URL`. The Compose service keeps
its data in the named `shopy_postgres_data` volume and exposes PostgreSQL on
`POSTGRES_PORT` (5433 by default). Check connectivity at
`GET /health/database`.

## Catalog import and commerce API

The former TypeScript demo catalog is imported once with the command above.
It creates stable UUID-based PostgreSQL products, categories, a catalog seller,
and product images. It is safe to run again: products are matched by their
legacy SKU and updated rather than duplicated. After seeding, the storefront
uses `GET /api/v1/products` and UUID product URLs as its catalog source.

To add the separate apparel collection (shirts, T-shirts, jeans, trousers,
pants, socks, shoes, outerwear, dresses, activewear, and accessories), run:

```bash
poetry run python -m app.scripts.seed_apparel_catalog
```

It is safe to rerun: products are upserted by `APPAREL-*` SKU and include
verified color variants, materials, fits, and sizes for catalog and agent use.

To add the separate room-focused furniture collection, run:

```bash
poetry run python -m app.scripts.seed_furniture_catalog
```

It upserts 20 `FURNITURE-*` products with dimensions, materials, colors, best
rooms, and placement guidance for room-planning and future image-based agents.

To add the travel collection, run:

```bash
poetry run python -m app.scripts.seed_travel_catalog
```

It upserts 30 `TRAVEL-*` products with varied prices, ratings, stock, colours,
capacity or dimensions, and use-case-oriented specifications for comparisons.

Authenticated commerce endpoints are available under `/api/v1`: `cart`,
`orders/checkout`, `orders`, `wallet`, and product review creation. Checkout
creates an order and a pending payment record; a real payment-provider capture
must be added before calling it a completed payment.

## Agent orchestration run logs

Apply the latest migration before using agent runs:

```bash
poetry run alembic upgrade head
```

`POST /api/v1/agentic/runs` accepts an authenticated shopping request and
persists its observable workflow in `orchestration_runs` and
`orchestration_run_events`. The owner can inspect history with `GET
/api/v1/agentic/runs` or one run with `GET /api/v1/agentic/runs/{run_id}`.

Events include the structured mission output, need-plan output, validated tool
inputs/results, audit outcome, repair attempts, and final response. They do
not store model chain-of-thought or secrets. Set `AI_LOG_CUSTOMER_INPUT=false`
to redact customer request content in both terminal and orchestration logs.

Example DBeaver query:

```sql
SELECT r.request_id, r.status, e.sequence, e.event_type, e.node_name,
       e.tool_name, e.input_data, e.output_data, e.error_message
FROM orchestration_runs r
JOIN orchestration_run_events e ON e.run_id = r.id
ORDER BY r.created_at DESC, e.sequence;
```

Run backend tests with:

```bash
cd backend
poetry run pytest
```

Copy `.env.example` to `.env` and set the required values before running in a new environment. The local `.env` is ignored by Git.

## Local Whisper speech-to-text

`POST /api/v1/transcribe` accepts a multipart `audio` field in WebM, WAV, MP3, M4A/MP4, or OGG format. The recording is held only in a temporary file during decoding and is deleted immediately afterward.

Configure Whisper in `.env`:

```env
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

The first transcription downloads the selected open-source model into the local Hugging Face cache. Use `small` for a balanced local CPU setup, or `medium` when you have more memory and can accept slower transcription. For a CUDA deployment, set a compatible `WHISPER_DEVICE` and compute type.

To test once the server is running:

```bash
curl -X POST http://localhost:8000/api/v1/transcribe \
  -F "audio=@/path/to/recording.webm;type=audio/webm"
```

## AI process logs

Run the backend as normal to see structured JSON logs in the terminal:

```bash
poetry run uvicorn app.main:app --reload --port 8000
```

Each text, voice, and camera request receives a short `request_id` and logs its received input, processing stages, high-level execution trace, outcome, and final output. Camera logs record safe metadata and the selected analysis mode rather than image bytes.

Customer input is logged by default for local development. To retain only its character count in a shared or production terminal, set:

```env
AI_LOG_CUSTOMER_INPUT=false
```

The trace intentionally does not log hidden AI chain-of-thought. It logs the observable work performed, such as context assembly, audio decoding/transcription, vision-mode selection, model request, and final response.
