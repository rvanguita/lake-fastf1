# %%

from src.spark_session import spark_session


import os
import mlflow
import mlflow.data

import pandas as pd
from sklearn import ensemble
from sklearn import model_selection
from sklearn import metrics
from sklearn import pipeline
from sklearn import impute

# from feature_engine import imputation

import matplotlib.pyplot as plt

import dotenv
dotenv.load_dotenv

mlflow.set_tracking_uri(os.getenv("MLFLOW_URI"))
mlflow.set_experiment(experiment_name=os.getenv("MLFLOW_EXPERIMENT_NAME"))

# pd.set_option('display.max_columns', None)
# pd.set_option('display.max_rows', None)

spark = spark_session()
# %%
df = (spark
      .read
      .format("delta")
      .load(f"{os.getenv("PATH_SILVER")}/tb_abt")
      ).toPandas()
# %%
df['dt_ref'] = pd.to_datetime(df['dt_ref'])

# %%
df_row_round_year = df[['dt_ref']].drop_duplicates()

# %%

df_row_round_year["row_number"] = (df_row_round_year
                                   .sort_values('dt_ref', ascending=False)
                                   .groupby(df["dt_ref"].dt.year)
                                   .cumcount())
df_row_round_year = df_row_round_year[df_row_round_year['row_number'] > 4]
df_row_round_year = df_row_round_year.drop('row_number', axis=1)
df_row_round_year.shape
# %%

cols = list(df.columns)
cols.insert(2, cols.pop(-1))
df = df[cols]
df.columns
# %%
df_sampling = pd.merge(df, df_row_round_year, on='dt_ref', how='inner')
df_sampling.shape

# %%
df_train = df_sampling[df_sampling['dt_ref'].dt.year < 2024]
df_test = df_sampling[df_sampling['dt_ref'].dt.year == 2024]
df_oot = df[df['dt_ref'].dt.year == 2025]


# %%
df.shape, df_train.shape, df_test.shape, df_oot.shape

# %%
features = df.iloc[:, 3:].columns
features
# %%
X_train, y_train = df_train[features], df_train['flChampion']
X_test, y_test = df_test[features], df_test['flChampion']
X_oot, y_oot = df_oot[features], df_oot['flChampion']

# %%
# EXPLORE

isna = X_train.isna().sum()
isna[isna > 0]

# %%

# missing = imputation.ArbitraryNumberImputer(
#     arbitrary_number=-10000,
#     variables=X_train.columns.tolist())

columns_with_na = X_train.columns[X_train.isna().any()]

rfc = ensemble.RandomForestClassifier(
    min_samples_leaf=50,
    n_estimators=500,
    random_state=42,
    n_jobs=-1,
)

model = pipeline.Pipeline(steps=[
    ('Imputation', impute.SimpleImputer(
        strategy="constant",
        fill_value=-10000
    )),
    ("RandomForest", rfc)
])

# %%

with mlflow.start_run():
    model.fit(X_train, y_train)

    y_train_prob = model.predict_proba(X_train)[:, 1]
    roc_train = metrics.roc_curve(y_train, y_train_prob)
    auc_train = metrics.roc_auc_score(y_train, y_train_prob)
    mlflow.log_metric("ROC Train", round(auc_train, 4))

    y_test_prob = model.predict_proba(X_test)[:, 1]
    roc_test = metrics.roc_curve(y_test, y_test_prob)
    auc_test = metrics.roc_auc_score(y_test, y_test_prob)
    mlflow.log_metric("ROC Test", round(auc_test, 4))

    y_oot_pred = model.predict(X_oot)
    y_oot_prob = model.predict_proba(X_oot)[:, 1]
    auc_oot = metrics.roc_auc_score(y_oot, y_oot_prob)
    roc_oot = metrics.roc_curve(y_oot, y_oot_prob)
    mlflow.log_metric("ROC OOT", round(auc_oot, 4))

    plt.figure(dpi=100)
    plt.plot(roc_train[0], roc_train[1])
    plt.plot(roc_test[0], roc_test[1])
    plt.plot(roc_oot[0], roc_oot[1])
    plt.legend([f"Train: {auc_train:.4f}",
               f"Test: {auc_test:.4f}",
               f"OOT: {auc_oot:.4f}"])
    plt.grid(True)
    plt.title("ROC Curve")
    plt.savefig("img/roc_curve.png")
    mlflow.log_artifact("img/roc_curve.png")

    feature_importance = pd.Series(
        rfc.feature_importances_, index=X_train.columns)
    feature_importance = feature_importance.sort_values(ascending=False)
    feature_importance.to_markdown("img/feature_importances.md")
    mlflow.log_artifact("img/feature_importances.md")

    model.fit(df[features], df['flChampion'])

    mlflow.sklearn.log_model(
        sk_model=model,
        name="RandomForest",
        skops_trusted_types=["numpy.dtype"]
    )

    dataset = mlflow.data.from_pandas(
        df,
        name="tb_abt",
        targets="flChampion",
    )

    # mlflow.log_input(dataset, context="training")


# %%
