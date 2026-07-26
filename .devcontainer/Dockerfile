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

COPY requirements.txt /tmp/pip-tmp/

RUN pip3 --disable-pip-version-check \
       --no-cache-dir \
       install \
       -r /tmp/pip-tmp/requirements.txt \
       && rm -rf /tmp/pip-tmp

USER vscode