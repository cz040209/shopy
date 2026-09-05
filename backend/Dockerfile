FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN pip install --no-cache-dir "poetry>=2.0,<3.0"

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

COPY . .

EXPOSE 8000
