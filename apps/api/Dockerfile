# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv/apps/api

# Dependencies first for layer caching.
COPY apps/api/pyproject.toml ./
RUN mkdir app && touch app/__init__.py && pip install . && rm -rf app build *.egg-info

COPY apps/api/ ./
COPY config/ /srv/config/
# The app runs from source (WORKDIR is on sys.path); only dependencies are pip-installed.
RUN useradd --system --uid 10001 --home /srv appuser \
    && mkdir -p /data && chown -R appuser /data

ENV CONFIG_DIR=/srv/config DATA_DIR=/data LOG_JSON=true ENVIRONMENT=production
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
