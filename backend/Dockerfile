FROM python:3.12-slim AS builder
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["fastapi", "run", "app/main.py", "--port", "8000"]
