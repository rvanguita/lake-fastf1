FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
# Instala exatamente o uv.lock testado (sem versões soltas).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY .streamlit ./.streamlit
COPY *.py ./
COPY views ./views
EXPOSE 8501
CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0", "--server.port=8501"]
