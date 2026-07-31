# %%
import os
import mlflow
import pandas as pd
from flask import Flask, request

API_PORT = os.environ["API_PORT"]
MLFLOW_URI = os.environ["MLFLOW_URI"]
MLFLOW_MODEL_REGISTERED = os.environ["MLFLOW_MODEL_REGISTERED"]


mlflow.set_tracking_uri(MLFLOW_URI)

models = mlflow.search_registered_models(
    filter_string=f"name='{MLFLOW_MODEL_REGISTERED}'")[-1]
last_version = int(models.latest_versions[-1].version)
MODEL = mlflow.sklearn.load_model(
    f"models:/{MLFLOW_MODEL_REGISTERED}/{last_version}")
print(MODEL)
# %%

app = Flask(__name__)


@app.route('/health_check')
def health_check():
    return "OK", 200


@app.route('/predict', methods=['POST'])
def predict():
    payload = request.get_json()
    data = payload.get('values', [])
    if len(data) == 0:
        return {"error": "No features provided"}, 400

    df = pd.DataFrame(data)
    X = df[MODEL.feature_names_in_]

    df_proba = pd.DataFrame(MODEL.predict_proba(X), columns=MODEL.classes_)
    df_proba['id'] = df['id'].copy()
    df_proba.set_index('id', inplace=True)

    payload = df_proba.to_dict(orient='index')

    return {"predictions": payload}, 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=API_PORT)

# %%
