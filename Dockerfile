FROM node:22-bookworm-slim AS ui
WORKDIR /build/frontend/ui
COPY frontend/ui/package.json frontend/ui/package-lock.json ./
RUN npm ci
COPY frontend/ui/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    HF_HOME=/home/app/.cache/huggingface
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY config/ config/
COPY frontend/*.py frontend/
COPY --from=ui /build/frontend/static/ frontend/static/
COPY graph/ graph/
COPY ingestion/ ingestion/
COPY infrastructure/ infrastructure/
COPY llm/ llm/
COPY memory/ memory/
COPY quiz/ quiz/
COPY main.py ./
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/data /home/app/.cache/huggingface \
    && chown -R app:app /app/data /home/app
USER app
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "frontend.server:app", "--host", "0.0.0.0", "--port", "8000"]
