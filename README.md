
# Lake FastF1
![Alt Text](img/high.png)
Lake FastF1 is a long-term data engineering and machine learning project focused on Formula 1 data. It combines data ingestion, lakehouse-style transformations, and a lightweight prediction experience powered by a trained model.

## What this project does

The project collects Formula 1 race and session results using the FastF1 library, processes them through a multi-layer data pipeline, and prepares curated datasets for analytics and prediction.

The workflow includes:

- Extracting raw race/session results from Formula 1 events.
- Storing the raw data in Parquet files.
- Consolidating the data into a Bronze layer with Delta Lake.
- Creating Silver-layer datasets for champions, driver statistics, and analytical tables.
- Exposing predictions through a Flask API and a Streamlit dashboard.

## Architecture

The project follows a practical data platform structure:

- Raw layer: initial extracted results stored as Parquet files.
- Bronze layer: consolidated data tables stored in Delta format.
- Silver layer: curated analytical datasets prepared for reporting and model consumption.
- Orchestration: an Airflow DAG runs the pipeline on a scheduled basis.
- Serving layer: an API and a Streamlit frontend consume the processed data and machine learning outputs.

## Main technologies

The project uses a modern data stack centered on Python and cloud-friendly data engineering tools:

- Python
- FastF1 for Formula 1 data access
- Pandas and NumPy for data preparation
- PySpark and Delta Lake for distributed processing and storage
- Apache Airflow for orchestration
- Flask for the prediction API
- Streamlit for the dashboard interface
- MLflow for model tracking and deployment workflow
- Docker and Docker Compose for local deployment

## Why this is a long-term project

This repository is designed as a long-term initiative rather than a one-off experiment. The pipeline is expected to evolve continuously as new data sources, validation rules, performance improvements, and modeling requirements are introduced.

In practice, that means the project will likely keep receiving improvements in:

- data quality checks and pipeline reliability
- scheduling and backfill behavior
- table design and business logic
- model retraining and evaluation
- observability, monitoring, and operational robustness

## Repository structure

- data/: raw, bronze, silver datasets produced by the pipeline
- dags/: Airflow DAG definitions
- src/: extraction, transformation, Spark, and SQL-based processing logic
- app/api/: Flask API service
- app/streamlit/: Streamlit dashboard application
- docker-compose.yml: local orchestration of the services

## Getting started

Run the project locally with Docker Compose:

```bash
docker compose up --build -d
```

Example environment variables:

```env
AWS_KEY=
AWS_SECRET_KEY=

AIRFLOW_VERSION=3.3.0
AIRFLOW_PORT=8080
AIRFLOW_UID=1000

API_PORT=5002

PATH_RAW="data/raw"
PATH_BRONZE="data/bronze"
PATH_SILVER="data/silver"
PATH_QUERIES="src/queries"

FORMAT_READ="parquet"

MLFLOW_URI="http://mlflow_ip:5050/"
MLFLOW_MODEL_REGISTERED="model_name"
MLFLOW_EXPERIMENT_NAME="experiment_name"

STREAMLIT_PORT=8501
```

### Environment variables

| Variable | Description |
| --- | --- |
| PATH_RAW | Directory where extracted Parquet files are stored. |
| PATH_BRONZE | Directory where consolidated Bronze tables are stored. |
| PATH_SILVER | Directory where processed Silver tables are stored. |
| PATH_QUERIES | Directory containing SQL files used by the transformation layer. |

## Notes

This project is meant to be practical, extensible, and continuously improved. The data pipeline is central to the architecture, so ongoing maintenance and enhancement are part of the expected lifecycle of the repository.
