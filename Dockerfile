ARG AIRFLOW_VERSION=3.3.0

FROM apache/airflow:${AIRFLOW_VERSION}-python3.13

# ARG AIRFLOW_VERSION

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless \
    && JAVA_HOME_PATH="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")" \
    && ln -sfn "${JAVA_HOME_PATH}" /opt/java \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/opt/java
ENV PATH="${JAVA_HOME}/bin:${PATH}"
ENV PYTHONPATH=/opt/airflow/project
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

USER airflow

COPY --chown=airflow:root requirements.txt /tmp/requirements.txt

RUN pip install \
    --no-cache-dir \
    --disable-pip-version-check \
    "apache-airflow==${AIRFLOW_VERSION}" \
    -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt