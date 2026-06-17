FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.18 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=./.venv \
    PATH="./.venv/bin:${PATH}" \
    STREAMLIT_SERVER_PORT=8080 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_MAX_UPLOAD_SIZE=10 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid appuser --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app \
    && chown appuser:appuser /app

WORKDIR /app
USER appuser

COPY --chown=appuser:appuser pyproject.toml README.md uv.lock ./
RUN uv sync --locked --no-dev --extra ui --no-install-project

COPY --chown=appuser:appuser .streamlit/ .streamlit/
COPY --chown=appuser:appuser harunobu/ harunobu/
COPY --chown=appuser:appuser app.py .
RUN uv sync --locked --no-dev --extra ui

EXPOSE 8080
CMD ["streamlit", "run", "app.py"]
