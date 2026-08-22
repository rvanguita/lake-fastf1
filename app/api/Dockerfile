FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/usr/local

# Install dependencies first (layer-cached until pyproject.toml changes)
COPY pyproject.toml ./
RUN uv pip install --system --no-cache \
    "fastapi>=0.115.0" \
    "uvicorn>=0.30.0" \
    "mlflow>=3.15.1" \
    "numpy>=2.0.0,<3.0.0" \
    "pandas>=2.0.0,<3.0.0" \
    "psutil>=6.0.0" \
    "rich>=13.0.0" \
    "scikit-learn>=1.3.0" \
    "scipy>=1.11.0" \
    "skops>=0.10.0"

COPY . .

CMD ["python", "main.py"]