# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv/apps/api

# Dependencies first for layer caching.
COPY apps/api/pyproject.toml ./
# Install only the dependencies: installing the project itself would put an empty stub
# `app` package into site-packages that shadows the real code for scripts run outside WORKDIR.
RUN python -c "import tomllib; print('\\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" \
      > /tmp/requirements.txt && pip install -r /tmp/requirements.txt

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
