"""
spatial_regression.py - Modello esplicativo: temperatura ~ covariate.

Prima fase quantitativa verso il modello del paper scientifico (fase 4 del
piano in paper/PIANO-ARTICOLO.md). OLS su `temp_mean_avg` (media
2000-2025, stessa variabile gia' usata per l'indice di Moran "grezzo" in
spatial_analysis.py: I=0.132, p=0.001 su 63 comuni) contro le covariate
esplicative ora disponibili in DB: elevazione, densita' di popolazione,
% uso del suolo urbano (CORINE), NDVI medio.

Dato che i comuni piu' vicini hanno temperature spazialmente correlate
(Moran's I sui dati grezzi gia' significativo), i residui di un OLS
classico potrebbero violare l'assunzione di indipendenza alla base dei
test di significativita' dei coefficienti. Il check minimo richiesto dal
piano e' l'indice di Moran sui **residui**: se resta significativo, un
OLS classico non e' adeguato e serve un modello a errore/lag spaziale
vero.

**Seconda fase (2026-07-17)**: la prima esecuzione (OLS + Moran's I sui
residui, con la matrice pesi inverso-distanza "a mano" di
spatial_analysis.py) ha confermato autocorrelazione residua significativa
(I=0.081, p=0.001 su 63 comuni) - qui sotto il modello vero e proprio, via
`spreg`/`libpysal` (non a mano come Moran's I: qui la stima
(massima verosimiglianza) e' piu' delicata, meglio una libreria testata).
Segue la regola di decisione di Anselin: test LM-lag/LM-error (e le
versioni robuste) su un OLS con pesi spaziali KNN, poi si stima il
modello (lag o errore) indicato dal test robusto piu' significativo.

Usage:
    python -m src.analysis.spatial_regression
"""

from pathlib import Path

import numpy as np
import pandas as pd
import spreg
import statsmodels.api as sm
from libpysal.weights import KNN
from sqlalchemy import text
from statsmodels.stats.outliers_influence import variance_inflation_factor

from src.analysis.spatial_analysis import build_inverse_distance_weights, morans_i_permutation_test
from src.utils.config import config
from src.utils.database import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

FEATURES = ['elevation_m', 'population_density', 'pct_urban', 'ndvi_mean']
TARGET = 'temp_mean_avg'
VIF_WARNING_THRESHOLD = 5.0
KNN_K = 5  # vicini per la matrice pesi spaziali usata da spreg (KNN invece di
           # inverso-distanza: evita nodi isolati/pesi degeneri con punti irregolari)


def load_regression_data() -> pd.DataFrame:
    """
    Comuni con dati di temperatura reali (63) e tutte le covariate
    esplicative gia' popolate in DB: elevazione e popolazione da
    `municipalities`, % urbano da `municipality_land_cover` (CORINE),
    NDVI medio da `municipality_ndvi`.
    """
    query = text("""
        SELECT
            m.name AS municipality_name,
            ST_X(ST_Centroid(m.geometry)) AS lon,
            ST_Y(ST_Centroid(m.geometry)) AS lat,
            AVG(k.temp_mean_annual)::float AS temp_mean_avg,
            m.elevation_m::float AS elevation_m,
            (m.population::float / NULLIF(m.area_km2, 0)) AS population_density,
            lc.pct_urban::float AS pct_urban,
            n.ndvi_mean::float AS ndvi_mean
        FROM kpi_annual_by_municipality k
        JOIN municipalities m ON k.municipality_id = m.municipality_id
        JOIN municipality_land_cover lc ON lc.municipality_id = m.municipality_id
        JOIN municipality_ndvi n ON n.municipality_id = m.municipality_id
        GROUP BY m.name, m.geometry, m.elevation_m, m.population, m.area_km2,
                 lc.pct_urban, n.ndvi_mean
        ORDER BY m.name
    """)
    with db_manager.engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    columns = ['municipality_name', 'lon', 'lat', TARGET] + FEATURES
    df = pd.DataFrame(rows, columns=columns)

    missing = df[FEATURES + [TARGET]].isna().any(axis=1)
    if missing.any():
        logger.warning(
            f"{missing.sum()} comuni con covariate mancanti, esclusi dal modello: "
            f"{df.loc[missing, 'municipality_name'].tolist()}"
        )
        df = df.loc[~missing].reset_index(drop=True)
    return df


def compute_vif(df: pd.DataFrame, features: list) -> pd.DataFrame:
    """VIF per covariata (>5 multicollinearita' da tenere d'occhio, >10 grave)."""
    x = sm.add_constant(df[features])
    vif = pd.DataFrame({
        'feature': x.columns,
        'vif': [variance_inflation_factor(x.values, i) for i in range(x.shape[1])],
    })
    return vif[vif['feature'] != 'const'].reset_index(drop=True)


def fit_ols(df: pd.DataFrame, features: list, target: str = TARGET):
    x = sm.add_constant(df[features])
    y = df[target]
    return sm.OLS(y, x).fit()


def build_knn_weights(df: pd.DataFrame, k: int = KNN_K) -> KNN:
    """Matrice pesi spaziali KNN (row-standardized) da lon/lat, per spreg."""
    coords = df[['lon', 'lat']].to_numpy()
    w = KNN.from_array(coords, k=k)
    w.transform = 'r'
    return w


def run_lm_diagnostics(df: pd.DataFrame, features: list, w: KNN, target: str = TARGET) -> spreg.OLS:
    """
    OLS via spreg con diagnostica di dipendenza spaziale (Moran's I sui
    residui, test del Moltiplicatore di Lagrange lag/error e versioni
    robuste) - usati per decidere quale modello spaziale stimare.
    """
    y = df[[target]].to_numpy()
    x = df[features].to_numpy()
    return spreg.OLS(
        y, x, w=w, spat_diag=True, moran=True, nonspat_diag=True,
        name_y=target, name_x=features,
    )


def select_spatial_model(ols_diag: spreg.OLS, alpha: float = 0.05) -> str:
    """
    Regola di decisione di Anselin (Anselin & Rey 1991): sceglie tra
    modello a lag spaziale, a errore spaziale, o nessuno dei due, in base
    ai test LM (robusti quando entrambi i test semplici sono
    significativi, per distinguere lag "vero" da errore "vero" quando
    sono correlati tra loro).
    """
    lm_lag_p = ols_diag.lm_lag[1]
    lm_error_p = ols_diag.lm_error[1]
    rlm_lag_p = ols_diag.rlm_lag[1]
    rlm_error_p = ols_diag.rlm_error[1]

    lag_sig = lm_lag_p < alpha
    error_sig = lm_error_p < alpha

    if not lag_sig and not error_sig:
        return 'none'
    if lag_sig and not error_sig:
        return 'lag'
    if error_sig and not lag_sig:
        return 'error'
    # Entrambi significativi: usa le versioni robuste per decidere.
    if rlm_lag_p < alpha and rlm_error_p >= alpha:
        return 'lag'
    if rlm_error_p < alpha and rlm_lag_p >= alpha:
        return 'error'
    # Ambiguo (entrambe le robuste significative, o nessuna): il residuo
    # potrebbe avere sia componente lag sia errore - si sceglie il
    # modello con la robusta più significativa come scelta pragmatica,
    # da segnalare esplicitamente come caso limite.
    return 'lag' if rlm_lag_p < rlm_error_p else 'error'


def fit_spatial_model(df: pd.DataFrame, features: list, w: KNN, model_type: str, target: str = TARGET):
    y = df[[target]].to_numpy()
    x = df[features].to_numpy()
    if model_type == 'lag':
        return spreg.ML_Lag(y, x, w=w, name_y=target, name_x=features)
    if model_type == 'error':
        return spreg.ML_Error(y, x, w=w, name_y=target, name_x=features)
    raise ValueError(f"model_type sconosciuto: {model_type}")


def log_spatial_model(model, model_type: str) -> None:
    logger.info(f"\n{model.summary}")
    spatial_param_name = 'rho (lag)' if model_type == 'lag' else 'lambda (errore)'
    spatial_param = model.rho if model_type == 'lag' else model.lam
    logger.info(f"{spatial_param_name} = {float(np.asarray(spatial_param)):.4f} — pseudo R² = {model.pr2:.3f}")


def main():
    logger.info("=" * 70)
    logger.info("MODELLO ESPLICATIVO: temperatura ~ elevazione + popolazione + uso del suolo + NDVI")
    logger.info("=" * 70)

    df = load_regression_data()
    logger.info(f"{len(df)} comuni con tutte le covariate disponibili")

    vif = compute_vif(df, FEATURES)
    logger.info("VIF (Variance Inflation Factor):")
    for _, row in vif.iterrows():
        flag = " <- ALTA multicollinearita'" if row['vif'] > VIF_WARNING_THRESHOLD else ""
        logger.info(f"  {row['feature']}: {row['vif']:.2f}{flag}")

    model = fit_ols(df, FEATURES)
    logger.info("\n" + model.summary().as_text())

    df['residual'] = model.resid
    w = build_inverse_distance_weights(df)
    mi_result = morans_i_permutation_test(df['residual'].to_numpy(), w)
    logger.info(
        f"Moran's I sui residui OLS: {mi_result['morans_i']} "
        f"(atteso sotto casualita': {mi_result['expected_i_random']}, "
        f"p={mi_result['p_value_permutation']})"
    )
    if mi_result['p_value_permutation'] < 0.05:
        logger.warning(
            "Residui ancora spazialmente autocorrelati (p<0.05): un OLS classico "
            "non e' adeguato per l'inferenza, serve un modello a errore/lag spaziale."
        )
    else:
        logger.info(
            "Residui senza autocorrelazione spaziale significativa: l'OLS classico "
            "e' statisticamente adeguato per queste covariate."
        )

    output_path = Path(config.get('paths.output')) / 'spatial_regression.csv'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    summary_path = Path(config.get('paths.output')) / 'spatial_regression_summary.txt'
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(model.summary().as_text())
        f.write('\n\nVIF:\n')
        f.write(vif.to_string(index=False))
        f.write(f"\n\nMoran's I sui residui OLS: {mi_result}\n")
    logger.info(f"Risultati salvati: {output_path}, {summary_path}")

    # --- Fase 2: modello spaziale vero e proprio (lag o errore, deciso via LM) ---
    logger.info("=" * 70)
    logger.info(f"MODELLO SPAZIALE (spreg/libpysal, KNN k={KNN_K})")
    logger.info("=" * 70)

    w_knn = build_knn_weights(df)
    ols_diag = run_lm_diagnostics(df, FEATURES, w_knn)
    logger.info(
        f"LM-lag: stat={ols_diag.lm_lag[0]:.3f} p={ols_diag.lm_lag[1]:.4f} | "
        f"LM-error: stat={ols_diag.lm_error[0]:.3f} p={ols_diag.lm_error[1]:.4f}"
    )
    logger.info(
        f"Robust LM-lag: stat={ols_diag.rlm_lag[0]:.3f} p={ols_diag.rlm_lag[1]:.4f} | "
        f"Robust LM-error: stat={ols_diag.rlm_error[0]:.3f} p={ols_diag.rlm_error[1]:.4f}"
    )

    model_type = select_spatial_model(ols_diag)
    spatial_summary_path = Path(config.get('paths.output')) / 'spatial_regression_spatial_model.txt'

    if model_type == 'none':
        logger.info(
            "Test LM (KNN k=5) non significativi: con questa specificazione dei pesi "
            "spaziali, l'OLS risulterebbe adeguato — in disaccordo col Moran's I sui "
            "residui (pesi inverso-distanza) sopra. La scelta del modello spaziale è "
            "sensibile alla definizione della matrice pesi: da riesaminare quando il "
            "campione di comuni crescerà."
        )
        with open(spatial_summary_path, 'w', encoding='utf-8') as f:
            f.write(ols_diag.summary)
    else:
        logger.info(f"Regola di Anselin → modello selezionato: SPATIAL {model_type.upper()}")
        spatial_model = fit_spatial_model(df, FEATURES, w_knn, model_type)
        log_spatial_model(spatial_model, model_type)
        with open(spatial_summary_path, 'w', encoding='utf-8') as f:
            f.write(ols_diag.summary)
            f.write('\n\n')
            f.write(spatial_model.summary)
    logger.info(f"Risultati modello spaziale salvati: {spatial_summary_path}")

    logger.info("Modello esplicativo completato")


if __name__ == '__main__':
    main()
