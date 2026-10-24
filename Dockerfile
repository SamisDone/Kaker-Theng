# One service: the website (Next.js static export) and the API (FastAPI) on
# one origin. Built from the repository root:
#   docker build -t kaker-theng .            the whole thing (what Render runs)
#   docker build --target api -t kt-api .    the API alone (docker compose)

# 1. The website. Next.js runs on Node; Bun installs and runs the scripts.
FROM node:22.23.3-slim AS site
COPY --from=oven/bun:1.3.12-slim /usr/local/bin/bun /usr/local/bin/bun
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
# No NEXT_PUBLIC_API_URL: the site calls /api on its own origin.
RUN bun run build

# 2. The API. Same Python as the development venv.
FROM python:3.13.9-slim AS api

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

WORKDIR /srv

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# One thread per library: faster on Render's 0.1 CPU (see app/__init__.py).
# Set after the install so changing it keeps the cached dependency layer.
ENV KT_THREADS=1

COPY backend/app ./app
COPY backend/assets ./assets

RUN useradd --create-home --uid 10001 crow
USER crow

EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]

# 3. Both: the API serving the built site at /.
FROM api
USER root
COPY --from=site /app/out ./site
# Compressed once here, so the server never compresses per request.
RUN rm -f site/_headers && python -m app.site site
ENV KT_SITE_DIR=/srv/site
USER crow
