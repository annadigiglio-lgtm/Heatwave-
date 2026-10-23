import json

import pandas as pd
import pytest

from src.machine_learning.climate_clustering import (
    build_pipeline,
    evaluate_k_values,
    fit_climate_model,
    load_model,
    predict_clusters,
    save_model,
)


@pytest.fixture
def climate_data():
    return pd.DataFrame({
        'municipality_name': [f'C{i}' for i in range(9)],
        'temp_mean_avg': [7.0, 7.2, 7.4, 12.0, 12.2, 12.4, 17.0, 17.2, 17.4],
        'days_gt_30c_avg': [0, 1, 0, 12, 14, 13, 48, 50, 52],
        'days_gt_35c_avg': [0, 0, 0, 1, 2, 1, 14, 15, 16],
    })


def test_pipeline_contains_scaler_and_kmeans():
    pipeline = build_pipeline(3)
    assert list(pipeline.named_steps) == ['scaler', 'kmeans']


def test_evaluation_returns_valid_silhouette_scores(climate_data):
    evaluation = evaluate_k_values(climate_data, [2, 3, 4])
    assert evaluation['k'].tolist() == [2, 3, 4]
    assert evaluation['silhouette_score'].between(-1, 1).all()


def test_labels_are_ordered_from_cool_to_warm(climate_data):
    pipeline, metadata, _ = fit_climate_model(climate_data, k=3)
    labels = predict_clusters(climate_data, pipeline, metadata)
    means = climate_data.assign(cluster=labels).groupby('cluster')['temp_mean_avg'].mean()
    assert means.index.tolist() == [0, 1, 2]
    assert means.is_monotonic_increasing


def test_model_round_trip(tmp_path, climate_data):
    pipeline, metadata, _ = fit_climate_model(climate_data, k=3)
    expected = predict_clusters(climate_data, pipeline, metadata)
    model_path, metadata_path = save_model(pipeline, metadata, tmp_path)

    assert model_path.exists()
    assert json.loads(metadata_path.read_text(encoding='utf-8'))['selected_k'] == 3

    loaded_pipeline, loaded_metadata = load_model(tmp_path)
    actual = predict_clusters(climate_data, loaded_pipeline, loaded_metadata)
    pd.testing.assert_series_equal(actual, expected)


def test_missing_feature_is_rejected(climate_data):
    with pytest.raises(ValueError, match='Colonne ML mancanti'):
        evaluate_k_values(climate_data.drop(columns='days_gt_35c_avg'))
