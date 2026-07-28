
```bash
docker compose up --build -d
```


```env
AWS_KEY=
AWS_SECRET_KEY=

AIRFLOW_VERSION=3.3.0
AIRFLOW_PORT=8080
AIRFLOW_UID=1000

API_PORT = 5002

PATH_RAW = "data/raw"
PATH_BRONZE = "data/bronze"
PATH_SILVER = "data/silver"
PATH_QUERIES = "src/queries"

FORMAT_READ = "parquet"

MLFLOW_URI = "http://mlflow_ip:5050/"
MLFLOW_MODEL_REGISTERED = "model_name"
MLFLOW_EXPERIMENT_NAME = "experiment_name"

STREAMLIT_PORT=8501
```

Descrição:

| Variável      | Descrição                                                                |
| ------------- | ------------------------------------------------------------------------ |
| `PATH_RAW`    | Diretório onde os arquivos Parquet extraídos são armazenados.            |
| `PATH_BRONZE` | Diretório onde as tabelas consolidadas da camada Bronze são armazenadas. |
| `PATH_SILVER` | Diretório onde as tabelas processadas da camada Silver são armazenadas.  |
