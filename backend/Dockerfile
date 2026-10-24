# Same Python as the development venv.
FROM python:3.13.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

# One thread per library: faster on Render's 0.1 CPU (see app/__init__.py).
# Set after the install so changing it keeps the cached dependency layer.
ENV KT_THREADS=1

COPY app ./app
COPY assets ./assets

RUN useradd --create-home --uid 10001 crow
USER crow

EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
