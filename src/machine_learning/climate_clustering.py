"""Pipeline K-Means valutata e persistibile per i cluster climatici."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import joblib
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

RANDOM_SEED = 42
FEATURE_COLUMNS = ('temp_mean_avg', 'days_gt_30c_avg', 'days_gt_35c_avg')
MODEL_FILENAME = 'climate_kmeans.joblib'
METADATA_FILENAME = 'climate_kmeans_metadata.json'


def validate_features(df: pd.DataFrame) -> pd.DataFrame:
    """Restituisce le feature numeriche validate, senza modificare ``df``."""
    missing_columns = [column for column in FEATURE_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Colonne ML mancanti: {', '.join(missing_columns)}")

    features = df.loc[:, FEATURE_COLUMNS].apply(pd.to_numeric, errors='coerce')
    missing_values = features.isna().sum()
    if missing_values.any():
        details = ', '.join(
            f'{column}={int(count)}' for column, count in missing_values.items() if count
        )
        raise ValueError(f'Valori ML mancanti o non numerici: {details}')
    if len(features) < 3:
        raise ValueError('Servono almeno 3 osservazioni per valutare il clustering')
    return features


def build_pipeline(k: int) -> Pipeline:
    """Crea la Pipeline richiesta: standardizzazione seguita da K-Means."""
    if k < 2:
        raise ValueError('k deve essere almeno 2')
    return Pipeline([
        ('scaler', StandardScaler()),
        ('kmeans', KMeans(n_clusters=k, random_state=RANDOM_SEED, n_init=10)),
    ])


def evaluate_k_values(df: pd.DataFrame, k_values: Iterable[int] = range(2, 9)) -> pd.DataFrame:
    """Valuta ogni ``k`` valido con il silhouette score."""
    features = validate_features(df)
    rows = []
    for k in sorted(set(int(value) for value in k_values)):
        if k < 2 or k >= len(features):
            continue
        pipeline = build_pipeline(k)
        labels = pipeline.fit_predict(features)
        scaled_features = pipeline.named_steps['scaler'].transform(features)
        rows.append({
            'k': k,
            'silhouette_score': float(silhouette_score(scaled_features, labels)),
        })
    if not rows:
        raise ValueError('Nessun valore di k valido per il numero di osservazioni')
    return pd.DataFrame(rows).sort_values('k').reset_index(drop=True)


def label_mapping(df: pd.DataFrame, raw_labels) -> dict[int, int]:
    """Ordina le etichette dal cluster climaticamente più fresco al più caldo."""
    raw = pd.Series(raw_labels, index=df.index)
    temperature_by_cluster = df['temp_mean_avg'].groupby(raw).mean().sort_values()
    return {int(raw_label): rank for rank, raw_label in enumerate(temperature_by_cluster.index)}


def fit_climate_model(df: pd.DataFrame, k: int | None = None) -> tuple[Pipeline, dict, pd.DataFrame]:
    """Valuta i candidati, addestra il modello scelto e produce i metadati."""
    features = validate_features(df)
    evaluation = evaluate_k_values(df)
    selected_k = int(k) if k is not None else int(
        evaluation.loc[evaluation['silhouette_score'].idxmax(), 'k']
    )
    if selected_k not in evaluation['k'].tolist():
        raise ValueError(f'k={selected_k} non è valido per {len(features)} osservazioni')

    pipeline = build_pipeline(selected_k)
    raw_labels = pipeline.fit_predict(features)
    mapping = label_mapping(df, raw_labels)
    selected_score = float(
        evaluation.loc[evaluation['k'] == selected_k, 'silhouette_score'].iloc[0]
    )
    metadata = {
        'model_type': 'StandardScaler + KMeans',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'scikit_learn_features': list(FEATURE_COLUMNS),
        'n_observations': int(len(features)),
        'selected_k': selected_k,
        'silhouette_score': selected_score,
        'random_seed': RANDOM_SEED,
        'raw_to_ordered_label': {str(key): value for key, value in mapping.items()},
        'label_meaning': '0 = cluster con temperatura media minore; valori crescenti = più caldo',
        'selection_note': (
            'Se k non è specificato, viene scelto il valore con silhouette score massimo; '
            'l’interpretazione scientifica va comunque verificata nella dashboard.'
        ),
        'k_evaluation': evaluation.to_dict(orient='records'),
    }
    return pipeline, metadata, evaluation


def predict_clusters(df: pd.DataFrame, pipeline: Pipeline, metadata: dict) -> pd.Series:
    """Assegna etichette ordinate usando una Pipeline già addestrata."""
    features = validate_features(df)
    expected = list(metadata.get('scikit_learn_features', []))
    if expected != list(FEATURE_COLUMNS):
        raise ValueError('Le feature nei metadati non corrispondono alla versione del codice')
    raw_labels = pipeline.predict(features)
    mapping = {int(key): int(value) for key, value in metadata['raw_to_ordered_label'].items()}
    ordered = pd.Series(raw_labels, index=df.index).map(mapping)
    if ordered.isna().any():
        raise ValueError('Il modello ha restituito un cluster non presente nei metadati')
    return ordered.astype(int).rename('climate_cluster')


def save_model(pipeline: Pipeline, metadata: dict, model_dir: str | Path = 'models') -> tuple[Path, Path]:
    """Salva Pipeline e metadati in due artefatti versionabili."""
    directory = Path(model_dir)
    directory.mkdir(parents=True, exist_ok=True)
    model_path = directory / MODEL_FILENAME
    metadata_path = directory / METADATA_FILENAME
    joblib.dump(pipeline, model_path)
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    return model_path, metadata_path


def load_model(model_dir: str | Path = 'models') -> tuple[Pipeline, dict]:
    """Ricarica Pipeline e metadati, fallendo chiaramente se manca un artefatto."""
    directory = Path(model_dir)
    model_path = directory / MODEL_FILENAME
    metadata_path = directory / METADATA_FILENAME
    if not model_path.exists() or not metadata_path.exists():
        raise FileNotFoundError(
            f'Artefatti ML mancanti in {directory}: eseguire train_climate_model.py'
        )
    pipeline = joblib.load(model_path)
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    return pipeline, metadata
