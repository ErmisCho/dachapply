# Multi-stage container for Azure Container Apps Consumption.
# Builds the Vite frontend, installs Django dependencies, and serves via Gunicorn.

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    WEB_CONCURRENCY=2

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
COPY scripts/start-container.sh ./scripts/start-container.sh

WORKDIR /app/backend
RUN chmod +x /app/scripts/start-container.sh \
    && DEBUG=True python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["/app/scripts/start-container.sh"]
