# Multi-stage container for Azure Container Apps Consumption.
# Builds the Vite frontend, installs Django dependencies, and serves via Gunicorn.

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim AS runtime
# uv is pinned rather than :latest so an image rebuild cannot pick up a different resolver.
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    WEB_CONCURRENCY=2 \
    # Install into the image's system prefix instead of a .venv, so start-container.sh
    # can keep calling bare `python` and `gunicorn` with no activation step.
    UV_PROJECT_ENVIRONMENT=/usr/local \
    UV_LINK_MODE=copy

WORKDIR /app

# --locked fails the build if uv.lock is out of date with respect to pyproject.toml, so the
# image can never be built from dependencies nobody resolved. --no-dev omits pytest.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-cache

COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
COPY scripts/start-container.sh ./scripts/start-container.sh

WORKDIR /app/backend
RUN chmod +x /app/scripts/start-container.sh \
    && DEBUG=True python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["/app/scripts/start-container.sh"]
