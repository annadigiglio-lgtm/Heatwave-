"""Addestra, valuta e salva il regressore della temperatura media (solo parquet)."""

from pathlib import Path

import pandas as pd

from src.machine_learning.temperature_regression import (
    CV_GROUP,
    CV_KFOLD,
    MAIN_FEATURE_SET,
    RESIDUALS_FILENAME,
    build_dataset,
    cross_validated_residuals,
    fit_temperature_model,
    save_model,
)
from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    seed = int(config.get('ml.random_seed', 42))
    cv_folds = int(config.get('ml.cv_folds', 5))
    export_dir = Path(config.get('paths.dashboard_export'))
    models_dir = Path(config.get('ml.models_dir', 'models'))

    data = build_dataset(export_dir)
    pipeline, metadata, metrics = fit_temperature_model(data, cv_folds=cv_folds, seed=seed)
    model_path, metadata_path = save_model(pipeline, metadata, models_dir)

    residuals = cross_validated_residuals(
        data, metadata['model_name'], metadata['features'], cv_folds, seed
    )
    residuals_path = export_dir / RESIDUALS_FILENAME
    residuals.to_parquet(residuals_path, index=False)

    table = metrics[[
        'model', 'feature_set', 'cv_scheme',
        'mae_mean', 'mae_std', 'rmse_mean', 'rmse_std', 'r2_mean', 'r2_std',
    ]]
    with pd.option_context('display.width', 200, 'display.max_columns', 20):
        logger.info('Metriche (media ± dev. std sui fold):\n' + table.round(3).to_string(index=False))

    main_rows = metrics[metrics['feature_set'] == MAIN_FEATURE_SET]
    for scheme in (CV_KFOLD, CV_GROUP):
        row = main_rows[
            (main_rows['model'] == metadata['model_name']) & (main_rows['cv_scheme'] == scheme)
        ].iloc[0]
        logger.info(
            f"{metadata['model_name']} {scheme}: MAE={row['mae_mean']:.3f} °C, "
            f"RMSE={row['rmse_mean']:.3f} °C, R2={row['r2_mean']:.3f}"
        )
    importance = pd.DataFrame(metadata['feature_importance'])
    logger.info('Importanza per permutazione:\n' + importance.round(4).to_string(index=False))
    logger.info(
        f"Comuni usati: {metadata['n_observations']} "
        f"(esclusi per NaN: {metadata['n_excluded']} su {metadata['n_rows_total']})"
    )
    logger.info(f"Modello scelto: {metadata['model_type']}")
    logger.info(f"Parametri migliori: {metadata['best_params'] or 'nessuna griglia'}")
    logger.info(f'Modello salvato: {model_path}')
    logger.info(f'Metadati salvati: {metadata_path}')
    logger.info(f'Residui (GroupKFold, fuori campione) salvati: {residuals_path}')


if __name__ == '__main__':
    main()
