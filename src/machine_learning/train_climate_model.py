"""Addestra, valuta e salva la Pipeline K-Means sui dati PostgreSQL/PostGIS."""

from pathlib import Path

import pandas as pd

from src.analysis.spatial_analysis import load_municipality_features
from src.machine_learning.climate_clustering import (
    fit_climate_model,
    predict_clusters,
    save_model,
)
from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    data = load_municipality_features()
    pipeline, metadata, evaluation = fit_climate_model(data)
    model_path, metadata_path = save_model(pipeline, metadata)

    result = data.copy()
    result['climate_cluster'] = predict_clusters(result, pipeline, metadata)
    output_dir = Path(config.get('paths.output'))
    output_dir.mkdir(parents=True, exist_ok=True)
    evaluation.to_csv(output_dir / 'climate_kmeans_evaluation.csv', index=False)
    result.to_csv(output_dir / 'climate_kmeans_clusters.csv', index=False)

    logger.info(f"Comuni usati: {metadata['n_observations']}")
    logger.info(f"k selezionato: {metadata['selected_k']}")
    logger.info(f"Silhouette score: {metadata['silhouette_score']:.4f}")
    logger.info(f'Modello salvato: {model_path}')
    logger.info(f'Metadati salvati: {metadata_path}')


if __name__ == '__main__':
    main()
