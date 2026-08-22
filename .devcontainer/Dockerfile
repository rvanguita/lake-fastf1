FROM mcr.microsoft.com/devcontainers/python:3.13-bookworm

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
       openjdk-17-jre-headless \
       procps \
       curl \
       && apt-get clean \
       && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/lib/jvm/java-17-openjdk-* /usr/lib/jvm/java-17-openjdk
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk
ENV PATH=$JAVA_HOME/bin:$PATH

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
       UV_PROJECT_ENVIRONMENT=/usr/local

COPY pyproject.toml uv.lock /tmp/pip-tmp/

RUN cd /tmp/pip-tmp && uv sync --frozen --no-install-project \
       && rm -rf /tmp/pip-tmp

USER vscode