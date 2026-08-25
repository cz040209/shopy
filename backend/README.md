# Shopy AI backend

The FastAPI server keeps `GEMINI_API_KEY` on the server, provides chat and vision endpoints, and transcribes user-confirmed voice recordings locally with Faster-Whisper.

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and replace the example PostgreSQL password.
docker compose --env-file backend/.env up -d postgres

cd backend
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload --port 8000
```

The API connects to PostgreSQL through `DATABASE_URL`. The Compose service keeps
its data in the named `shopy_postgres_data` volume and exposes PostgreSQL on
`POSTGRES_PORT` (5433 by default). Check connectivity at
`GET /health/database`.

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
