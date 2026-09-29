FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY *.py ./
COPY pages ./pages
COPY assets ./assets
EXPOSE 8050
CMD ["gunicorn", "--bind", "0.0.0.0:8050", "--workers", "2", "--threads", "4", "--timeout", "120", "main:server"]
