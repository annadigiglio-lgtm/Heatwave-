"""Machine Learning di Heatwave Piemonte: clustering climatico e regressione della temperatura."""

from .climate_clustering import (
    FEATURE_COLUMNS,
    build_pipeline,
    evaluate_k_values,
    fit_climate_model,
    label_mapping,
    load_model,
    predict_clusters,
    save_model,
)
from .temperature_regression import (
    FEATURE_SETS,
    build_dataset,
    build_models,
    cross_validated_residuals,
    evaluate_models,
    fit_best_model,
    fit_temperature_model,
    select_best_model,
)
from .temperature_regression import load_model as load_temperature_model
from .temperature_regression import save_model as save_temperature_model

__all__ = [
    'FEATURE_COLUMNS',
    'FEATURE_SETS',
    'build_dataset',
    'build_models',
    'build_pipeline',
    'cross_validated_residuals',
    'evaluate_k_values',
    'evaluate_models',
    'fit_best_model',
    'fit_climate_model',
    'fit_temperature_model',
    'label_mapping',
    'load_model',
    'load_temperature_model',
    'predict_clusters',
    'save_model',
    'save_temperature_model',
    'select_best_model',
]
