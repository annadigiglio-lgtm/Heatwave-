from decimal import Decimal

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.machine_learning.temperature_regression import (
    CV_GROUP,
    CV_KFOLD,
    FEATURE_SETS,
    MAIN_FEATURES,
    build_dataset,
    build_models,
    cross_validated_residuals,
    evaluate_models,
    fit_temperature_model,
    load_model,
    save_model,
    select_best_model,
)

SMALL_GRID = {
    'model__n_estimators': [20],
    'model__max_depth': [None],
    'model__min_samples_leaf': [1],
}
N_ROWS = 40
PROVINCES = ['PA', 'PB', 'PC', 'PD']


def write_synthetic_export(directory, nan_rows: int = 0):
    """Scrive 4 parquet sintetici: temperatura = funzione lineare della quota + rumore."""
    rng = np.random.default_rng(0)
    names = [f'Comune {i}' for i in range(N_ROWS)]
    provinces = [PROVINCES[i % len(PROVINCES)] for i in range(N_ROWS)]
    elevation = rng.uniform(100, 2000, N_ROWS)
    temperature = 14.0 - 0.0065 * elevation + rng.normal(0, 0.15, N_ROWS)
    if nan_rows:
        elevation[:nan_rows] = np.nan
    lat = rng.uniform(44.0, 46.0, N_ROWS)
    lon = rng.uniform(7.0, 9.0, N_ROWS)

    pd.DataFrame({
        'municipality_name': names, 'lon': lon, 'lat': lat,
        'temp_mean_avg': temperature,
        'days_gt_30c_avg': 0.0, 'days_gt_35c_avg': 0.0, 'climate_cluster': 0,
    }).to_parquet(directory / 'spatial_analysis.parquet')
    pd.DataFrame({
        'municipality_name': names, 'province_name': provinces,
        'elevation_m': elevation, 'lat': lat, 'lon': lon,
    }).to_parquet(directory / 'municipality_metadata_all.parquet')
    pd.DataFrame({
        'municipality_name': names, 'province_name': provinces,
        'population': rng.uniform(100, 5000, N_ROWS).round(),
        'area_km2': np.full(N_ROWS, 10.0),
        # Come nel parquet reale, le percentuali sono Decimal.
        'pct_urban': [Decimal(str(round(v, 2))) for v in rng.uniform(0, 30, N_ROWS)],
        'pct_forest_seminatural': [
            Decimal(str(round(v, 2))) for v in rng.uniform(0, 70, N_ROWS)
        ],
    }).to_parquet(directory / 'land_cover_with_population.parquet')
    pd.DataFrame({
        'municipality_name': names, 'province_name': provinces,
        'ndvi_mean': rng.uniform(0.2, 0.8, N_ROWS),
    }).to_parquet(directory / 'ndvi_all.parquet')
    return directory


@pytest.fixture(scope='module')
def dataset(tmp_path_factory):
    return build_dataset(write_synthetic_export(tmp_path_factory.mktemp('export')))


@pytest.fixture(scope='module')
def metrics(dataset):
    return evaluate_models(dataset, cv_folds=5, seed=42, rf_grid=SMALL_GRID)


def test_build_dataset_merges_sources_and_computes_density(tmp_path):
    write_synthetic_export(tmp_path)
    df = build_dataset(tmp_path)
    assert len(df) == N_ROWS
    assert df.attrs['n_excluded'] == 0
    population = pd.read_parquet(tmp_path / 'land_cover_with_population.parquet')['population']
    assert np.allclose(df['population_density'], population / 10.0)
    assert df['pct_urban'].dtype.kind == 'f'
    assert set(df['province_name']) == set(PROVINCES)


def test_rows_with_nan_are_excluded_and_counted(tmp_path):
    df = build_dataset(write_synthetic_export(tmp_path, nan_rows=3))
    assert len(df) == N_ROWS - 3
    assert df.attrs['n_excluded'] == 3
    assert df.attrs['n_rows_total'] == N_ROWS
    assert not df.isna().any().any()


def test_missing_columns_raise_clear_error(tmp_path):
    write_synthetic_export(tmp_path)
    ndvi = pd.read_parquet(tmp_path / 'ndvi_all.parquet').drop(columns='ndvi_mean')
    ndvi.to_parquet(tmp_path / 'ndvi_all.parquet')
    with pytest.raises(ValueError, match='Colonne mancanti in ndvi_all.parquet: ndvi_mean'):
        build_dataset(tmp_path)


def test_three_models_are_pipelines_with_scaler():
    models = build_models(42, SMALL_GRID)
    assert list(models) == ['LinearRegression', 'RandomForestRegressor', 'MLPRegressor']
    assert isinstance(models['RandomForestRegressor'], GridSearchCV)
    for estimator in models.values():
        pipeline = estimator.estimator if isinstance(estimator, GridSearchCV) else estimator
        assert isinstance(pipeline, Pipeline)
        assert isinstance(pipeline.named_steps['scaler'], StandardScaler)
        assert list(pipeline.named_steps) == ['scaler', 'model']


def test_metrics_format_for_both_cv_schemes(metrics):
    expected_columns = {
        'model', 'feature_set', 'cv_scheme', 'n_splits',
        'mae_mean', 'mae_std', 'rmse_mean', 'rmse_std', 'r2_mean', 'r2_std',
    }
    assert expected_columns <= set(metrics.columns)
    assert len(metrics) == 3 * len(FEATURE_SETS) * 2
    assert set(metrics['cv_scheme']) == {CV_KFOLD, CV_GROUP}
    assert (metrics[['mae_mean', 'rmse_mean', 'mae_std', 'rmse_std']] >= 0).all().all()
    assert (metrics['rmse_mean'] >= metrics['mae_mean']).all()
    # Solo 4 province: GroupKFold ridotto a 4 fold.
    assert set(metrics.loc[metrics['cv_scheme'] == CV_GROUP, 'n_splits']) == {4}


def test_best_model_explains_synthetic_temperature(metrics):
    best = select_best_model(metrics)
    assert best['cv_scheme'] == CV_GROUP
    assert best['r2_mean'] > 0.8


def test_residuals_are_out_of_sample(dataset):
    residuals = cross_validated_residuals(
        dataset, 'LinearRegression', list(MAIN_FEATURES), cv_folds=5, seed=42
    )
    assert list(residuals.columns) == [
        'municipality_name', 'province_name', 'lon', 'lat', 'osservato', 'predetto', 'residuo',
    ]
    assert np.allclose(residuals['residuo'], residuals['osservato'] - residuals['predetto'])


def test_joblib_round_trip_with_metadata(dataset, metrics, tmp_path):
    pipeline, metadata, _ = fit_temperature_model(
        dataset, cv_folds=5, seed=42, rf_grid=SMALL_GRID, metrics=metrics
    )
    save_model(pipeline, metadata, tmp_path / 'models')
    loaded, loaded_metadata = load_model(tmp_path / 'models')

    X = dataset[loaded_metadata['features']]
    assert np.allclose(loaded.predict(X), pipeline.predict(X))
    assert loaded_metadata['n_observations'] == N_ROWS
    assert loaded_metadata['n_excluded'] == 0
    assert loaded_metadata['random_seed'] == 42
    assert {row['model'] for row in loaded_metadata['metrics']} == {
        'LinearRegression', 'RandomForestRegressor', 'MLPRegressor',
    }
    assert len(loaded_metadata['metrics']) == len(metrics)
    assert {row['feature'] for row in loaded_metadata['feature_importance']} == set(MAIN_FEATURES)
    assert 'GroupKFold' in loaded_metadata['validation_note']
    assert 'created_at_utc' in loaded_metadata


def test_load_model_missing_artifacts(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_model(tmp_path)
