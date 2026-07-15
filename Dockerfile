FROM node:22-alpine AS frontend-build

WORKDIR /frontend

ARG VITE_BASE_PATH=/
ARG VITE_API_BASE_URL=
ENV VITE_BASE_PATH=${VITE_BASE_PATH} \
    VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./
RUN npm run build

FROM python:3.12-slim

ARG UV_VERSION=0.11.28

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir "uv==${UV_VERSION}"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY --from=frontend-build /frontend/dist ./frontend/dist

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app app \
    && mkdir -p storage/uploads logs \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "app.main", "web", "--host", "0.0.0.0", "--port", "8000"]
