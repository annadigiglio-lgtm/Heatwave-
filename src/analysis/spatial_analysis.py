"""
spatial_analysis.py - Analisi Spaziale

Indice di Moran (autocorrelazione spaziale) e clustering K-means per zone
climatiche, sui comuni con dati di temperatura reali (44 dal 2026-07-15: 8
capoluoghi + 36 comuni extra selezionati per copertura spaziale, vedi
src/data_acquisition/download_extra_municipalities.py).

Nota campionaria: anche con 44 unità spaziali (sopra la soglia comune di
20-30 per un'analisi di autocorrelazione spaziale) restano solo una
frazione dei 1180 comuni piemontesi — i risultati sono più robusti che con
gli 8 capoluoghi originali, ma non coprono l'intera regione.

Usage:
    python -m src.analysis.spatial_analysis
"""

from pathlib import Path
from itertools import combinations

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.machine_learning.climate_clustering import (
    FEATURE_COLUMNS,
    build_pipeline,
    label_mapping,
)
from src.utils.config import config
from src.utils.database import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

N_PERMUTATIONS = 999
RANDOM_SEED = 42


def load_municipality_features() -> pd.DataFrame:
    """
    Carica, per tutti i comuni con dati di temperatura reali, coordinate
    del centroide e feature climatiche aggregate (2000-2025) da usare per
    Moran's I e clustering.

    Returns:
        pd.DataFrame: municipality_name, lon, lat, temp_mean_avg,
        days_gt_30c_avg, days_gt_35c_avg
    """
    query = text("""
        SELECT
            m.name AS municipality_name,
            ST_X(ST_Centroid(m.geometry)) AS lon,
            ST_Y(ST_Centroid(m.geometry)) AS lat,
            AVG(k.temp_mean_annual)::float AS temp_mean_avg,
            AVG(k.days_gt_30c)::float AS days_gt_30c_avg,
            AVG(k.days_gt_35c)::float AS days_gt_35c_avg
        FROM kpi_annual_by_municipality k
        JOIN municipalities m ON k.municipality_id = m.municipality_id
        GROUP BY m.name, m.geometry
        ORDER BY m.name
    """)
    with db_manager.engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    columns = ['municipality_name', 'lon', 'lat', 'temp_mean_avg', 'days_gt_30c_avg', 'days_gt_35c_avg']
    return pd.DataFrame(rows, columns=columns)


def haversine_km(lon1, lat1, lon2, lat2) -> float:
    """Distanza in km tra due punti lat/lon (formula haversine)."""
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlambda / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def build_inverse_distance_weights(df: pd.DataFrame) -> np.ndarray:
    """
    Matrice dei pesi spaziali W (n x n), inverso della distanza,
    row-standardized (ogni riga somma a 1), diagonale nulla.
    """
    n = len(df)
    w = np.zeros((n, n))
    for i, j in combinations(range(n), 2):
        dist = haversine_km(df['lon'].iloc[i], df['lat'].iloc[i], df['lon'].iloc[j], df['lat'].iloc[j])
        weight = 1.0 / dist
        w[i, j] = weight
        w[j, i] = weight

    row_sums = w.sum(axis=1, keepdims=True)
    return w / row_sums


def morans_i(values: np.ndarray, w: np.ndarray) -> float:
    """Calcola l'indice di Moran I dato un vettore di valori e una matrice pesi."""
    n = len(values)
    x = values - values.mean()
    s0 = w.sum()
    numerator = np.sum(w * np.outer(x, x))
    denominator = np.sum(x ** 2)
    return (n / s0) * (numerator / denominator)


def morans_i_permutation_test(values: np.ndarray, w: np.ndarray, n_perm: int = N_PERMUTATIONS) -> dict:
    """
    Test di significatività di Moran's I via permutazione (più robusto
    dell'approssimazione normale asintotica quando n è piccolo, come qui).

    Returns:
        dict: I osservato, p-value (two-sided), I atteso sotto casualità
    """
    rng = np.random.default_rng(RANDOM_SEED)
    observed = morans_i(values, w)

    permuted = np.empty(n_perm)
    for k in range(n_perm):
        shuffled = rng.permutation(values)
        permuted[k] = morans_i(shuffled, w)

    p_value = (np.sum(np.abs(permuted) >= np.abs(observed)) + 1) / (n_perm + 1)

    return {
        'morans_i': round(observed, 4),
        'expected_i_random': round(permuted.mean(), 4),
        'p_value_permutation': round(p_value, 4),
    }


def climate_clustering(df: pd.DataFrame, k: int = 3) -> pd.Series:
    """
    K-means clustering dei comuni in zone climatiche, su feature
    standardizzate (temperatura media, giorni >30°C, giorni >35°C).

    Non reimplementa il K-Means: delega alla Pipeline ufficiale di
    `src/machine_learning/climate_clustering.py` (`build_pipeline(k)`,
    cioè StandardScaler + KMeans con lo stesso seed e `n_init`) e al suo
    riordino delle etichette (`label_mapping`). A differenza di
    `predict_clusters()`, qui il modello viene addestrato ex novo su `df`
    e non si usa il modello salvato in `models/`: serve, per esempio, a
    clusterizzare i comuni ARPA nella dashboard.

    Le etichette grezze di K-means (0, 1, 2, ...) sono assegnate da sklearn
    in un ordine arbitrario, senza alcun legame con quanto è caldo o freddo
    il gruppo. Vengono quindi rinumerate in base alla temperatura media reale
    del gruppo, in ordine crescente: il cluster 0 è sempre il più fresco,
    l'ultimo è sempre il più caldo — una convenzione stabile che rende
    l'etichetta di cluster leggibile di per sé (in tooltip, mappe, tabelle)
    senza dover ogni volta consultare quale sia il più freddo o il più caldo.

    Args:
        df (pd.DataFrame): feature per comune
        k (int): numero di cluster (default 3)

    Returns:
        pd.Series: etichetta di cluster per riga (0 = più fresco, k-1 = più caldo)
    """
    features = df.loc[:, list(FEATURE_COLUMNS)]
    raw_labels = build_pipeline(k).fit_predict(features)
    remap = label_mapping(df, raw_labels)
    labels = pd.Series(raw_labels, index=df.index).map(remap)
    return labels.astype(int).rename('climate_cluster')


def main():
    logger.info("=" * 70)
    logger.info("ANALISI SPAZIALE (Moran's I + clustering climatico)")
    logger.info("=" * 70)

    df = load_municipality_features()
    logger.info(f"{len(df)} unità spaziali disponibili (comuni con dati di temperatura reali)")
    w = build_inverse_distance_weights(df)

    mi_result = morans_i_permutation_test(df['temp_mean_avg'].to_numpy(), w)
    logger.info(
        f"Moran's I (temp. media 2000-2025): {mi_result['morans_i']} "
        f"(atteso sotto casualità: {mi_result['expected_i_random']}, "
        f"p={mi_result['p_value_permutation']} su {N_PERMUTATIONS} permutazioni)"
    )

    df['climate_cluster'] = climate_clustering(df, k=3)
    for cluster_id, group in df.groupby('climate_cluster'):
        names = ', '.join(group['municipality_name'])
        logger.info(f"Cluster {cluster_id}: {names} (temp. media {group['temp_mean_avg'].mean():.1f}°C)")

    output_path = Path(config.get('paths.output')) / 'spatial_analysis.csv'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(f"✓ Risultati salvati: {output_path}")

    summary_path = Path(config.get('paths.output')) / 'morans_i_summary.csv'
    pd.DataFrame([mi_result]).to_csv(summary_path, index=False)
    logger.info(f"✓ Riepilogo Moran's I salvato: {summary_path}")

    logger.info("✓ Analisi spaziale completata")


if __name__ == '__main__':
    main()
