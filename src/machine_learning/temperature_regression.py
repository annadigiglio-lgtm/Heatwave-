"""Regressione supervisionata della temperatura media comunale.

Si spiega ``temp_mean_avg`` (media 2000-2025 del comune) con le caratteristiche
del territorio e si confrontano tre modelli scikit-learn, ognuno in una
``Pipeline`` con ``StandardScaler``:

- ``LinearRegression`` (baseline);
- ``RandomForestRegressor`` con ``GridSearchCV``;
- ``MLPRegressor`` (rete neurale, ponte verso il deep learning).

La validazione usa due schemi: ``KFold`` casuale e ``GroupKFold`` per
provincia. I comuni vicini si assomigliano (autocorrelazione spaziale), quindi
il KFold casuale tende a essere ottimista: il confronto tra i due schemi è
parte del risultato. I dati arrivano solo dai parquet di
``paths.dashboard_export``: nessun database.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import make_scorer, mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import (
    GridSearchCV,
    GroupKFold,
    KFold,
    cross_val_predict,
    cross_validate,
)
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

RANDOM_SEED = 42
TARGET_COLUMN = 'temp_mean_avg'
GROUP_COLUMN = 'province_name'
MAIN_FEATURES = (
    'elevation_m',
    'population_density',
    'pct_urban',
    'pct_forest_seminatural',
    'ndvi_mean',
)
COORDINATE_FEATURES = ('lat', 'lon')
MAIN_FEATURE_SET = 'territorio'
FEATURE_SETS: dict[str, tuple[str, ...]] = {
    MAIN_FEATURE_SET: MAIN_FEATURES,
    'territorio_coordinate': MAIN_FEATURES + COORDINATE_FEATURES,
}
CV_KFOLD = 'KFold'
CV_GROUP = 'GroupKFold'
DEFAULT_RF_GRID: dict[str, list] = {
    'model__n_estimators': [100, 200],
    'model__max_depth': [None, 10],
    'model__min_samples_leaf': [1, 5],
}
INNER_CV_FOLDS = 3
MODEL_FILENAME = 'temperature_regressor.joblib'
METADATA_FILENAME = 'temperature_regressor_metadata.json'
RESIDUALS_FILENAME = 'temperature_regression_residuals.parquet'

# Colonne richieste in ciascun parquet di ``paths.dashboard_export``.
SOURCE_COLUMNS: dict[str, tuple[str, ...]] = {
    'spatial_analysis': ('municipality_name', 'lon', 'lat', TARGET_COLUMN),
    'municipality_metadata_all': ('municipality_name', 'province_name', 'elevation_m'),
    'land_cover_with_population': (
        'municipality_name', 'province_name', 'population', 'area_km2',
        'pct_urban', 'pct_forest_seminatural',
    ),
    'ndvi_all': ('municipality_name', 'province_name', 'ndvi_mean'),
}
DATASET_COLUMNS = (
    'municipality_name', GROUP_COLUMN, TARGET_COLUMN, *MAIN_FEATURES, *COORDINATE_FEATURES,
)


# --- Dati -------------------------------------------------------------------

def _rmse(y_true, y_pred) -> float:
    """Radice dell'errore quadratico medio (stessa unità del target, °C)."""
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


SCORERS = {
    'mae': make_scorer(mean_absolute_error, greater_is_better=False),
    'rmse': make_scorer(_rmse, greater_is_better=False),
    'r2': make_scorer(r2_score),
}


def validate_columns(df: pd.DataFrame, required: Sequence[str], source: str) -> None:
    """Solleva ``ValueError`` se ``df`` non contiene tutte le colonne richieste."""
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Colonne mancanti in {source}: {', '.join(missing)}")


def _check_unique(df: pd.DataFrame, keys: list[str], source: str) -> None:
    """Verifica che la chiave di join identifichi una sola riga."""
    duplicated = int(df.duplicated(keys).sum())
    if duplicated:
        raise ValueError(
            f"Chiave {'+'.join(keys)} non univoca in {source}: {duplicated} duplicati"
        )


def load_sources(export_dir: str | Path | None = None) -> dict[str, pd.DataFrame]:
    """Legge i quattro parquet sorgente, validando le colonne richieste."""
    directory = Path(export_dir or config.get('paths.dashboard_export'))
    frames = {}
    for name, columns in SOURCE_COLUMNS.items():
        path = directory / f'{name}.parquet'
        if not path.exists():
            raise FileNotFoundError(f'Parquet mancante: {path}')
        df = pd.read_parquet(path)
        validate_columns(df, columns, path.name)
        frames[name] = df.loc[:, list(columns)].copy()
    return frames


def merge_sources(frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Unisce le sorgenti in una riga per comune e calcola ``population_density``.

    ``municipality_metadata_all``, ``land_cover_with_population`` e ``ndvi_all``
    si uniscono per ``municipality_name`` + ``province_name`` (chiave più
    robusta); ``spatial_analysis`` non ha la provincia e si unisce per solo
    nome, che deve quindi essere univoco (verificato: lo è nei 1180 comuni).
    """
    for name, columns in SOURCE_COLUMNS.items():
        if name not in frames:
            raise ValueError(f'Sorgente mancante: {name}')
        validate_columns(frames[name], columns, name)

    spatial = frames['spatial_analysis']
    metadata = frames['municipality_metadata_all']
    _check_unique(spatial, ['municipality_name'], 'spatial_analysis')
    _check_unique(metadata, ['municipality_name'], 'municipality_metadata_all')
    province_keys = ['municipality_name', 'province_name']
    for name in ('land_cover_with_population', 'ndvi_all'):
        _check_unique(frames[name], province_keys, name)

    merged = (
        spatial.merge(metadata, on='municipality_name', how='left')
        .merge(frames['land_cover_with_population'], on=province_keys, how='left')
        .merge(frames['ndvi_all'], on=province_keys, how='left')
    )
    numeric = [
        TARGET_COLUMN, 'lat', 'lon', 'elevation_m', 'population', 'area_km2',
        'pct_urban', 'pct_forest_seminatural', 'ndvi_mean',
    ]
    for column in numeric:
        # Le percentuali arrivano come Decimal (NUMERIC di PostgreSQL).
        merged[column] = pd.to_numeric(merged[column].astype('object'), errors='coerce')
    area = merged['area_km2'].where(merged['area_km2'] > 0)
    merged['population_density'] = merged['population'] / area
    return merged.loc[:, list(DATASET_COLUMNS)]


def drop_missing(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Esclude le righe con NaN in target, feature o provincia e le conta."""
    validate_columns(df, DATASET_COLUMNS, 'dataset')
    complete = df.dropna(subset=list(DATASET_COLUMNS)).reset_index(drop=True)
    return complete, int(len(df) - len(complete))


def build_dataset(export_dir: str | Path | None = None) -> pd.DataFrame:
    """Costruisce il dataset di regressione dai parquet di ``dashboard_export``.

    Il conteggio delle righe totali ed escluse è in ``df.attrs``
    (``n_rows_total``, ``n_excluded``).
    """
    merged = merge_sources(load_sources(export_dir))
    dataset, n_excluded = drop_missing(merged)
    if n_excluded:
        logger.warning(f'Righe escluse per valori mancanti: {n_excluded} su {len(merged)}')
    else:
        logger.info(f'Nessuna riga esclusa: {len(merged)} comuni completi')
    dataset.attrs['n_rows_total'] = int(len(merged))
    dataset.attrs['n_excluded'] = n_excluded
    return dataset


# --- Modelli ----------------------------------------------------------------

def build_models(
    seed: int = RANDOM_SEED,
    rf_grid: Mapping[str, list] | None = None,
    inner_cv_folds: int = INNER_CV_FOLDS,
) -> dict[str, BaseEstimator]:
    """Crea i tre modelli candidati, tutti con ``StandardScaler`` in Pipeline.

    Il RandomForest è una ``GridSearchCV`` che avvolge la Pipeline: dentro una
    cross-validation esterna diventa così una CV annidata (la griglia è scelta
    solo sui dati di training di ciascun fold).
    """
    if inner_cv_folds < 2:
        raise ValueError('inner_cv_folds deve essere almeno 2')
    grid = dict(rf_grid if rf_grid is not None else DEFAULT_RF_GRID)
    linear = Pipeline([
        ('scaler', StandardScaler()),
        ('model', LinearRegression()),
    ])
    forest = Pipeline([
        ('scaler', StandardScaler()),
        ('model', RandomForestRegressor(random_state=seed)),
    ])
    mlp = Pipeline([
        ('scaler', StandardScaler()),
        ('model', MLPRegressor(
            hidden_layer_sizes=(32, 16),
            early_stopping=True,
            max_iter=2000,
            random_state=seed,
        )),
    ])
    return {
        'LinearRegression': linear,
        'RandomForestRegressor': GridSearchCV(
            forest,
            param_grid=grid,
            cv=KFold(inner_cv_folds, shuffle=True, random_state=seed),
            scoring=SCORERS['rmse'],
        ),
        'MLPRegressor': mlp,
    }


def build_cv_splitters(df: pd.DataFrame, cv_folds: int, seed: int) -> dict[str, object]:
    """Restituisce KFold casuale e GroupKFold per provincia."""
    if cv_folds < 2:
        raise ValueError('cv_folds deve essere almeno 2')
    if len(df) < cv_folds:
        raise ValueError(f'Servono almeno {cv_folds} righe per la cross-validation')
    n_groups = int(df[GROUP_COLUMN].nunique())
    if n_groups < 2:
        raise ValueError('Servono almeno 2 province per GroupKFold')
    group_folds = min(cv_folds, n_groups)
    if group_folds < cv_folds:
        logger.warning(f'GroupKFold ridotto a {group_folds} fold ({n_groups} province)')
    return {
        CV_KFOLD: KFold(cv_folds, shuffle=True, random_state=seed),
        CV_GROUP: GroupKFold(n_splits=group_folds),
    }


def _feature_matrix(df: pd.DataFrame, features: Sequence[str]) -> tuple[pd.DataFrame, pd.Series]:
    validate_columns(df, [*features, TARGET_COLUMN, GROUP_COLUMN], 'dataset')
    return df.loc[:, list(features)], df[TARGET_COLUMN]


def evaluate_models(
    df: pd.DataFrame,
    feature_sets: Mapping[str, Sequence[str]] | None = None,
    cv_folds: int = 5,
    seed: int = RANDOM_SEED,
    rf_grid: Mapping[str, list] | None = None,
) -> pd.DataFrame:
    """Valuta ogni modello × set di feature × schema di CV con ``cross_validate``.

    Restituisce media e deviazione standard (sui fold) di MAE, RMSE e R².
    """
    feature_sets = dict(feature_sets or FEATURE_SETS)
    splitters = build_cv_splitters(df, cv_folds, seed)
    groups = df[GROUP_COLUMN]
    rows = []
    for set_name, features in feature_sets.items():
        X, y = _feature_matrix(df, features)
        for model_name, estimator in build_models(seed, rf_grid).items():
            for cv_name, splitter in splitters.items():
                scores = cross_validate(
                    clone(estimator), X, y,
                    cv=splitter,
                    groups=groups if cv_name == CV_GROUP else None,
                    scoring=SCORERS,
                )
                row = {
                    'model': model_name,
                    'feature_set': set_name,
                    'cv_scheme': cv_name,
                    'n_splits': int(splitter.get_n_splits()),
                }
                for metric in ('mae', 'rmse', 'r2'):
                    values = scores[f'test_{metric}']
                    if metric != 'r2':
                        values = -values  # gli scorer di errore sono negati
                    row[f'{metric}_mean'] = float(np.mean(values))
                    row[f'{metric}_std'] = float(np.std(values))
                rows.append(row)
                logger.info(
                    f"{model_name} | {set_name} | {cv_name}: "
                    f"RMSE={row['rmse_mean']:.3f} R2={row['r2_mean']:.3f}"
                )
    return pd.DataFrame(rows)


def select_best_model(
    metrics: pd.DataFrame,
    feature_set: str = MAIN_FEATURE_SET,
    cv_scheme: str = CV_GROUP,
) -> dict:
    """Sceglie il modello con RMSE medio minimo per set di feature e schema dati."""
    candidates = metrics[
        (metrics['feature_set'] == feature_set) & (metrics['cv_scheme'] == cv_scheme)
    ]
    if candidates.empty:
        raise ValueError(f'Nessuna metrica per feature_set={feature_set}, cv={cv_scheme}')
    return candidates.loc[candidates['rmse_mean'].idxmin()].to_dict()


def fit_best_model(
    df: pd.DataFrame,
    model_name: str,
    features: Sequence[str],
    seed: int = RANDOM_SEED,
    rf_grid: Mapping[str, list] | None = None,
) -> tuple[Pipeline, dict]:
    """Riaddestra il modello scelto su tutto il dataset.

    Restituisce la Pipeline addestrata e i parametri migliori della
    ``GridSearchCV`` (dizionario vuoto per i modelli senza griglia).
    """
    models = build_models(seed, rf_grid)
    if model_name not in models:
        raise ValueError(f"Modello sconosciuto: {model_name}. Validi: {', '.join(models)}")
    X, y = _feature_matrix(df, features)
    estimator = models[model_name].fit(X, y)
    if isinstance(estimator, GridSearchCV):
        best_params = {
            key.removeprefix('model__'): value for key, value in estimator.best_params_.items()
        }
        return estimator.best_estimator_, best_params
    return estimator, {}


def compute_feature_importance(
    pipeline: Pipeline,
    df: pd.DataFrame,
    features: Sequence[str],
    seed: int = RANDOM_SEED,
    n_repeats: int = 10,
) -> pd.DataFrame:
    """Importanza per permutazione: calo medio di R² mescolando ogni feature."""
    X, y = _feature_matrix(df, features)
    result = permutation_importance(
        pipeline, X, y, scoring='r2', n_repeats=n_repeats, random_state=seed,
    )
    return pd.DataFrame({
        'feature': list(features),
        'importance_mean': result.importances_mean,
        'importance_std': result.importances_std,
    }).sort_values('importance_mean', ascending=False).reset_index(drop=True)


def cross_validated_residuals(
    df: pd.DataFrame,
    model_name: str,
    features: Sequence[str],
    cv_folds: int = 5,
    seed: int = RANDOM_SEED,
    rf_grid: Mapping[str, list] | None = None,
) -> pd.DataFrame:
    """Predizioni fuori campione (GroupKFold per provincia) e residui per comune."""
    X, y = _feature_matrix(df, features)
    splitter = build_cv_splitters(df, cv_folds, seed)[CV_GROUP]
    estimator = build_models(seed, rf_grid)[model_name]
    predicted = cross_val_predict(estimator, X, y, cv=splitter, groups=df[GROUP_COLUMN])
    residuals = df.loc[:, ['municipality_name', GROUP_COLUMN, 'lon', 'lat']].copy()
    residuals['osservato'] = y.to_numpy()
    residuals['predetto'] = predicted
    residuals['residuo'] = residuals['osservato'] - residuals['predetto']
    return residuals


def fit_temperature_model(
    df: pd.DataFrame,
    cv_folds: int = 5,
    seed: int = RANDOM_SEED,
    rf_grid: Mapping[str, list] | None = None,
    feature_sets: Mapping[str, Sequence[str]] | None = None,
    metrics: pd.DataFrame | None = None,
) -> tuple[Pipeline, dict, pd.DataFrame]:
    """Valuta i candidati, riaddestra il migliore e produce i metadati.

    ``metrics`` permette di riusare una tabella già prodotta da
    ``evaluate_models`` con gli stessi argomenti, evitando di ripetere la CV.
    """
    feature_sets = dict(feature_sets or FEATURE_SETS)
    if MAIN_FEATURE_SET not in feature_sets:
        raise ValueError(f'Il set di feature principale {MAIN_FEATURE_SET} è obbligatorio')
    if metrics is None:
        metrics = evaluate_models(df, feature_sets, cv_folds, seed, rf_grid)
    best = select_best_model(metrics)
    features = list(feature_sets[MAIN_FEATURE_SET])
    pipeline, best_params = fit_best_model(df, best['model'], features, seed, rf_grid)
    importance = compute_feature_importance(pipeline, df, features, seed)
    grid = dict(rf_grid if rf_grid is not None else DEFAULT_RF_GRID)

    metadata = {
        'model_type': f"StandardScaler + {best['model']}",
        'model_name': best['model'],
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'target': TARGET_COLUMN,
        'feature_set': MAIN_FEATURE_SET,
        'features': features,
        'feature_sets': {name: list(cols) for name, cols in feature_sets.items()},
        'n_observations': int(len(df)),
        'n_rows_total': int(df.attrs.get('n_rows_total', len(df))),
        'n_excluded': int(df.attrs.get('n_excluded', 0)),
        'random_seed': int(seed),
        'cv_folds': int(cv_folds),
        'selection_criterion': (
            f'RMSE medio minimo con {CV_GROUP} per {GROUP_COLUMN} '
            f'sul set di feature {MAIN_FEATURE_SET}'
        ),
        'selected_metrics': {
            key: best[key] for key in ('mae_mean', 'rmse_mean', 'r2_mean')
        },
        'best_params': best_params,
        'rf_param_grid': {key.removeprefix('model__'): value for key, value in grid.items()},
        'metrics': metrics.to_dict(orient='records'),
        'feature_importance': importance.to_dict(orient='records'),
        'importance_note': (
            'permutation_importance sul dataset di addestramento: calo medio di R² '
            'quando si mescola la feature (10 ripetizioni).'
        ),
        'validation_note': (
            'KFold mescola comuni di tutte le province: i comuni vicini, simili per '
            'autocorrelazione spaziale, finiscono sia in training sia in test e le '
            'metriche risultano ottimiste. GroupKFold tiene fuori una provincia '
            'intera per fold e stima meglio la generalizzazione a territori non '
            'visti; per questo la scelta del modello usa GroupKFold. La GridSearchCV '
            f'del RandomForest usa al suo interno KFold({INNER_CV_FOLDS}) sui dati di training.'
        ),
        'join_note': (
            'spatial_analysis unito per municipality_name (univoco); le altre sorgenti '
            'per municipality_name + province_name.'
        ),
    }
    return pipeline, metadata, metrics


# --- Persistenza --------------------------------------------------------------

def _to_json_safe(value):
    """Converte i tipi NumPy in tipi Python serializzabili in JSON."""
    if isinstance(value, dict):
        return {str(key): _to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


def save_model(
    pipeline: Pipeline, metadata: dict, model_dir: str | Path = 'models'
) -> tuple[Path, Path]:
    """Salva Pipeline e metadati in due artefatti versionabili."""
    directory = Path(model_dir)
    directory.mkdir(parents=True, exist_ok=True)
    model_path = directory / MODEL_FILENAME
    metadata_path = directory / METADATA_FILENAME
    joblib.dump(pipeline, model_path)
    metadata_path.write_text(
        json.dumps(_to_json_safe(metadata), ensure_ascii=False, indent=2), encoding='utf-8'
    )
    return model_path, metadata_path


def load_model(model_dir: str | Path = 'models') -> tuple[Pipeline, dict]:
    """Ricarica Pipeline e metadati, fallendo chiaramente se manca un artefatto."""
    directory = Path(model_dir)
    model_path = directory / MODEL_FILENAME
    metadata_path = directory / METADATA_FILENAME
    if not model_path.exists() or not metadata_path.exists():
        raise FileNotFoundError(
            f'Artefatti del regressore mancanti in {directory}: '
            'eseguire train_temperature_model.py'
        )
    pipeline = joblib.load(model_path)
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    return pipeline, metadata
