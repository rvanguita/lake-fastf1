# %%
import os
from flask import Flask, request
import mlflow
import pandas as pd

import dotenv
dotenv.load_dotenv()  # Load environment variables from .env file

MLFLOW_URI = os.getenv("MLFLOW_URI")
MLFLOW_MODEL_REGISTERED = os.getenv("MLFLOW_MODEL_REGISTERED")
API_PORT = os.getenv("API_PORT")

def model_find(model_id: str | None = None):
    try:
        mlflow.set_tracking_uri(MLFLOW_URI)

<<<<<<< Updated upstream
mlflow.set_tracking_uri(MLFLOW_URI)

models = mlflow.search_registered_models(
    filter_string=f"name='{MLFLOW_MODEL_REGISTERED}'")[-1]
last_version = int(models.latest_versions[-1].version)
MODEL = mlflow.sklearn.load_model(
    f"models:/{MLFLOW_MODEL_REGISTERED}/{last_version}")

=======
        models = mlflow.search_registered_models(
            filter_string=f"name='{model_id}'")[-1]
        last_version = int(models.latest_versions[-1].version)
        model = mlflow.sklearn.load_model(
            f"models:/{model_id}/{last_version}")
    except Exception as e:
        return None 
    return model 
>>>>>>> Stashed changes
# %%

app = Flask(__name__)


@app.route('/health_check')
def health_check():
    return "OK", 200


@app.route('/predict', methods=['POST'])
def predict():
    
    model = model_find(MLFLOW_MODEL_REGISTERED)
    if model is None:
        return {"error": "Model not found"}, 500

    payload = request.get_json()
    data = payload.get('values', [])
    if len(data) == 0:
        return {"error": "No features provided"}, 400

    df = pd.DataFrame(data)
    X = df[model.feature_names_in_]

    df_proba = pd.DataFrame(model.predict_proba(X), columns=model.classes_)
    df_proba['id'] = df['id'].copy()
    df_proba.set_index('id', inplace=True)

    payload = df_proba.to_dict(orient='index')

    return {"predictions": payload}, 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=API_PORT)

# %%
