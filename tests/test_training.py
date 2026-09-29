from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from src.train_driver_champion import (
    SKOPS_TRUSTED_TYPES,
    TemporalCalibratedClassifier,
    _base_estimator,
    _normalize_by_snapshot,
    prepare_training_frame,
)


def test_prepare_training_frame_excludes_current_season():
    current_year = datetime.now(UTC).year
    frame = pd.DataFrame(
        {
            "dt_ref": [f"{current_year - 1}-03-01", f"{current_year}-03-01"],
            "DriverId": ["a", "b"],
            "feature": [1.0, 2.0],
            "flChampion": [1, 0],
        }
    )
    # Include both classes in the completed season so the validation guard passes.
    frame = pd.concat(
        [
            frame,
            pd.DataFrame(
                [
                    {
                        "dt_ref": f"{current_year - 1}-03-01",
                        "DriverId": "c",
                        "feature": 0.0,
                        "flChampion": 0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    prepared, features = prepare_training_frame(frame, current_year=current_year)
    assert prepared["Year"].unique().tolist() == [current_year - 1]
    assert features == ["feature"]


def test_normalize_by_snapshot_is_mutually_exclusive():
    scores = np.array([0.8, 0.2, 0.3, 0.3])
    dates = pd.Series(["r1", "r1", "r2", "r2"])
    normalized = _normalize_by_snapshot(scores, dates)
    assert normalized[:2].sum() == pytest.approx(1)
    assert normalized[2:].sum() == pytest.approx(1)


def test_logged_model_reopens_with_declared_skops_types(tmp_path):
    """O MLflow grava em skops; sem os tipos declarados o modelo não reabre na API."""
    import mlflow
    from sklearn.linear_model import LogisticRegression

    frame = pd.DataFrame(
        {"f1": [0, 1, 0, 1, 2, 3, np.nan, 1], "f2": [1, 0, 1, 0, 3, 2, 1, 0]}
    )
    target = [0, 1, 0, 1, 1, 0, 0, 1]
    estimator = _base_estimator().set_params(
        forest__n_estimators=3, forest__min_samples_leaf=1, forest__n_jobs=1
    )
    estimator.fit(frame, target)
    calibrator = LogisticRegression().fit(
        estimator.predict_proba(frame)[:, 1].reshape(-1, 1), target
    )
    model = TemporalCalibratedClassifier(estimator, calibrator, ["f1", "f2"])
    assert type(model).__module__ == "src.train_driver_champion"

    path = tmp_path / "model"
    mlflow.sklearn.save_model(
        model,
        str(path),
        serialization_format="skops",
        skops_trusted_types=SKOPS_TRUSTED_TYPES,
        pip_requirements=["scikit-learn"],
    )
    loaded = mlflow.sklearn.load_model(str(path))
    np.testing.assert_allclose(loaded.predict_proba(frame), model.predict_proba(frame))
    assert len(loaded.predict_proba_members(frame)) == 3
