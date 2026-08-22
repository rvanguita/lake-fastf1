FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Install dependencies (layer-cached until pyproject.toml changes)
COPY pyproject.toml ./
RUN uv pip install --system --no-cache \
    "deltalake>=1.6.2" \
    "pandas>=2.0.0,<3.0.0" \
    "plotly>=5.0.0" \
    "requests>=2.31.0" \
    "streamlit>=1.61.1"

COPY . .

CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0"]