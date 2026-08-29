import os

import mlflow
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

API_PORT = int(os.environ["API_PORT"])
MLFLOW_URI = os.environ["MLFLOW_URI"]
MLFLOW_MODEL_REGISTERED = os.environ["MLFLOW_MODEL_REGISTERED"]


def model_find(model_id: str | None = None):
    try:
        mlflow.set_tracking_uri(MLFLOW_URI)
        models = mlflow.search_registered_models(filter_string=f"name='{model_id}'")[-1]
        last_version = int(models.latest_versions[-1].version)
        model = mlflow.sklearn.load_model(f"models:/{model_id}/{last_version}")
    except Exception:
        return None
    return model


class PredictRequest(BaseModel):
    values: list[dict]


app = FastAPI(
    title="F1 Driver Champion API",
    description="Predicts championship win probability for F1 drivers.",
    version="1.0.0",
)


@app.get("/health_check", tags=["health"])
def health_check():
    return {"status": "OK"}


@app.post("/predict", tags=["model"])
def predict(body: PredictRequest):
    model = model_find(MLFLOW_MODEL_REGISTERED)
    if model is None:
        raise HTTPException(status_code=500, detail="Model not found")

    if not body.values:
        raise HTTPException(status_code=400, detail="No features provided")

    df = pd.DataFrame(body.values)

    missing = [c for c in model.feature_names_in_ if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=422, detail=f"missing feature columns: {missing}"
        )

    X = df[model.feature_names_in_]

    df_proba = pd.DataFrame(model.predict_proba(X), columns=model.classes_)
    df_proba["id"] = df["id"].copy()
    df_proba.set_index("id", inplace=True)

    return {"predictions": df_proba.to_dict(orient="index")}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
