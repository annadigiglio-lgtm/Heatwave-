"""
validate_arpa.py - Validazione delle temperature Open-Meteo contro
osservazioni di stazione reali ARPA Piemonte.

Contesto: fase 1 del piano paper (paper/PIANO-ARTICOLO.md). Le
temperature in `temperature` sono dati di rianalisi/modello (Open-Meteo), non
osservazioni dirette - un revisore lo contesterebbe per primo. Questo modulo
confronta, per i comuni dove esiste una stazione ARPA reale (vedi
`src/data_acquisition/download_arpa.py`), le due serie sullo stesso
(comune, data) e calcola bias/RMSE/correlazione.

Usage:
    python -m src.analysis.validate_arpa
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.utils.config import config
from src.utils.database import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_paired_temperatures() -> pd.DataFrame:
    """
    Carica, per i soli comuni con una stazione ARPA corrispondente, le
    coppie (temp_max/temp_min/temp_mean Open-Meteo, temp_max/temp_min/temp_mean
    ARPA) sulla stessa data.

    Returns:
        pd.DataFrame: una riga per (comune, data) con entrambe le serie.
    """
    query = """
        SELECT
            m.municipality_id,
            m.name AS municipality_name,
            t.date,
            t.temp_max AS om_temp_max,
            t.temp_min AS om_temp_min,
            t.temp_mean AS om_temp_mean,
            a.temp_max AS arpa_temp_max,
            a.temp_min AS arpa_temp_min,
            a.temp_mean AS arpa_temp_mean,
            a.station_name
        FROM temperature t
        JOIN arpa_temperature a
            ON a.municipality_id = t.municipality_id AND a.date = t.date
        JOIN municipalities m ON m.municipality_id = t.municipality_id
        ORDER BY m.name, t.date
    """
    rows = db_manager.execute_query(query)
    df = pd.DataFrame(rows, columns=[
        'municipality_id', 'municipality_name', 'date',
        'om_temp_max', 'om_temp_min', 'om_temp_mean',
        'arpa_temp_max', 'arpa_temp_min', 'arpa_temp_mean', 'station_name',
    ])
    logger.info(
        f"Coppie di osservazioni caricate: {len(df)} giorni, "
        f"{df['municipality_name'].nunique()} comuni con stazione ARPA"
    )
    return df


def validation_metrics(observed: pd.Series, reference: pd.Series) -> dict:
    """
    Metriche di validazione di `observed` (Open-Meteo) contro `reference`
    (ARPA, trattata come verita' di terra) su coppie non-null.

    Returns:
        dict: n, bias medio (observed - reference), MAE, RMSE, correlazione
        di Pearson (r, p-value).
    """
    paired = pd.DataFrame({'observed': observed, 'reference': reference}).dropna()
    if len(paired) < 2:
        return {'n_days': len(paired), 'bias': np.nan, 'mae': np.nan, 'rmse': np.nan, 'r': np.nan, 'r_p_value': np.nan}

    diff = paired['observed'] - paired['reference']
    r, p_value = stats.pearsonr(paired['observed'], paired['reference'])
    return {
        'n_days': len(paired),
        'bias': diff.mean(),
        'mae': diff.abs().mean(),
        'rmse': np.sqrt((diff ** 2).mean()),
        'r': r,
        'r_p_value': p_value,
    }


def validate_all_municipalities(paired: pd.DataFrame) -> pd.DataFrame:
    """Calcola le metriche di validazione (su temp_max/temp_min/temp_mean) per ciascun comune."""
    results = []
    for name, group in paired.groupby('municipality_name'):
        row = {'municipality_name': name, 'station_name': group['station_name'].iloc[0]}
        for var in ('temp_max', 'temp_min', 'temp_mean'):
            metrics = validation_metrics(group[f'om_{var}'], group[f'arpa_{var}'])
            row.update({f'{var}_{k}': v for k, v in metrics.items()})
        results.append(row)
    return pd.DataFrame(results).sort_values('municipality_name').reset_index(drop=True)


def save_results(df: pd.DataFrame, filename: str = 'arpa_validation.csv') -> Path:
    """Salva i risultati in `output/`."""
    output_path = Path(config.get('paths.output')) / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(f"✓ Risultati salvati: {output_path}")
    return output_path


def hot_day_bias(paired: pd.DataFrame, thresholds=(30.0, 35.0)) -> pd.DataFrame:
    """
    Bias/MAE/RMSE su `temp_max` ristretto ai giorni **davvero caldi**
    (ARPA, trattata come verita' di terra, sopra soglia) confrontati contro
    la media su tutti i giorni. Le rianalisi come Open-Meteo tendono a
    sottostimare gli estremi piu' della media - questa e' la verifica
    diretta, dato che il progetto misura ondate di calore, non temperature
    medie.
    """
    rows = []
    all_days = validation_metrics(paired['om_temp_max'], paired['arpa_temp_max'])
    rows.append({'condition': 'tutti i giorni', **all_days})
    for threshold in thresholds:
        hot = paired[paired['arpa_temp_max'] > threshold]
        metrics = validation_metrics(hot['om_temp_max'], hot['arpa_temp_max'])
        rows.append({'condition': f'ARPA temp_max > {threshold:.0f}°C', **metrics})
    return pd.DataFrame(rows)


def identify_heatwaves_from_series(
    dates: pd.Series, temp_max: pd.Series, threshold: float = 35.0, min_duration: int = 3
) -> list[dict]:
    """
    Replica in Python, su una singola serie (comune), la stessa logica di
    `identify_heatwaves()` (SQL, vedi sql/01_init_database.sql): sequenze di
    giorni **calendariali consecutivi** con temp_max > soglia, lunghe almeno
    `min_duration`.
    """
    df = pd.DataFrame({'date': pd.to_datetime(dates), 'temp_max': temp_max}).dropna()
    df = df[df['temp_max'] > threshold].sort_values('date')
    if df.empty:
        return []

    dates_arr = df['date'].to_numpy()
    temps_arr = df['temp_max'].to_numpy()
    events = []
    streak_start, streak_max, streak_len = dates_arr[0], temps_arr[0], 1

    for i in range(1, len(dates_arr)):
        if dates_arr[i] == dates_arr[i - 1] + np.timedelta64(1, 'D'):
            streak_len += 1
            streak_max = max(streak_max, temps_arr[i])
        else:
            if streak_len >= min_duration:
                events.append({'start_date': streak_start, 'end_date': dates_arr[i - 1],
                                'duration_days': streak_len, 'max_temp': streak_max})
            streak_start, streak_max, streak_len = dates_arr[i], temps_arr[i], 1

    if streak_len >= min_duration:
        events.append({'start_date': streak_start, 'end_date': dates_arr[-1],
                        'duration_days': streak_len, 'max_temp': streak_max})
    return events


def build_arpa_heatwave_events(threshold: float = 35.0, min_duration: int = 3) -> pd.DataFrame:
    """Identifica le ondate di calore sui dati ARPA (verita' di terra) per i 51 comuni con stazione."""
    query = """
        SELECT a.municipality_id, m.name AS municipality_name, a.date, a.temp_max
        FROM arpa_temperature a
        JOIN municipalities m ON m.municipality_id = a.municipality_id
        ORDER BY a.municipality_id, a.date
    """
    rows = db_manager.execute_query(query)
    df = pd.DataFrame(rows, columns=['municipality_id', 'municipality_name', 'date', 'temp_max'])

    events = []
    for (municipality_id, name), group in df.groupby(['municipality_id', 'municipality_name']):
        for event in identify_heatwaves_from_series(group['date'], group['temp_max'], threshold, min_duration):
            events.append({'municipality_id': municipality_id, 'municipality_name': name, **event})
    return pd.DataFrame(events)


def load_om_heatwave_events(municipality_ids: list[int], threshold: float = 35.0) -> pd.DataFrame:
    """Carica le ondate di calore gia' identificate su Open-Meteo (`heatwave_events`) per gli stessi comuni."""
    from sqlalchemy import text as sql_text

    query = sql_text("""
        SELECT h.municipality_id, m.name AS municipality_name, h.start_date, h.end_date,
               h.duration_days, h.max_temp
        FROM heatwave_events h
        JOIN municipalities m ON m.municipality_id = h.municipality_id
        WHERE h.municipality_id = ANY(:municipality_ids) AND h.heat_threshold = :threshold
        ORDER BY h.municipality_id, h.start_date
    """)
    with db_manager.engine.connect() as conn:
        df = pd.read_sql(query, conn, params={'municipality_ids': municipality_ids, 'threshold': threshold})
    return df


def _events_overlap(a_start, a_end, b_start, b_end) -> bool:
    # om_events arriva da Postgres come datetime.date, arpa_events come
    # pd.Timestamp (via identify_heatwaves_from_series) - normalizzati
    # entrambi prima di confrontare, altrimenti pandas solleva TypeError.
    a_start, a_end, b_start, b_end = (pd.Timestamp(x) for x in (a_start, a_end, b_start, b_end))
    return a_start <= b_end and b_start <= a_end


def compare_heatwave_events(om_events: pd.DataFrame, arpa_events: pd.DataFrame) -> dict:
    """
    Confronta gli eventi Open-Meteo (predetti) con quelli ARPA (verita' di
    terra) per sovrapposizione temporale nello stesso comune - non richiede
    date identiche, solo che i due intervalli si intersechino.

    Returns:
        dict: conteggi e precision/recall (ARPA come ground truth).
    """
    om_confirmed = 0
    for _, om in om_events.iterrows():
        candidates = arpa_events[arpa_events['municipality_id'] == om['municipality_id']]
        if any(_events_overlap(om['start_date'], om['end_date'], c['start_date'], c['end_date'])
               for _, c in candidates.iterrows()):
            om_confirmed += 1

    arpa_confirmed = 0
    for _, arpa in arpa_events.iterrows():
        candidates = om_events[om_events['municipality_id'] == arpa['municipality_id']]
        if any(_events_overlap(arpa['start_date'], arpa['end_date'], c['start_date'], c['end_date'])
               for _, c in candidates.iterrows()):
            arpa_confirmed += 1

    n_om, n_arpa = len(om_events), len(arpa_events)
    return {
        'n_om_events': n_om,
        'n_arpa_events': n_arpa,
        'om_events_confirmed_by_arpa': om_confirmed,
        'arpa_events_confirmed_by_om': arpa_confirmed,
        'precision': om_confirmed / n_om if n_om else np.nan,  # delle ondate OM, quante sono reali
        'recall': arpa_confirmed / n_arpa if n_arpa else np.nan,  # delle ondate reali, quante OM cattura
    }


def load_arpa_annual_temperature(municipality_ids: list[int]) -> pd.DataFrame:
    """Media annuale di `temp_mean` ARPA per comune - stessa granularita' di `kpi_annual_by_municipality`."""
    from sqlalchemy import text as sql_text

    query = sql_text("""
        SELECT a.municipality_id, m.name AS municipality_name,
               EXTRACT(YEAR FROM a.date)::int AS year,
               AVG(a.temp_mean) AS temp_mean_annual
        FROM arpa_temperature a
        JOIN municipalities m ON m.municipality_id = a.municipality_id
        WHERE a.municipality_id = ANY(:municipality_ids) AND a.temp_mean IS NOT NULL
        GROUP BY a.municipality_id, m.name, EXTRACT(YEAR FROM a.date)
        ORDER BY m.name, year
    """)
    with db_manager.engine.connect() as conn:
        df = pd.read_sql(query, conn, params={'municipality_ids': municipality_ids})
    return df


def compare_trends(arpa_annual: pd.DataFrame) -> pd.DataFrame:
    """
    Confronta il trend di riscaldamento (Mann-Kendall + regressione lineare,
    stesse funzioni pure di `src/analysis/trend_analysis.py`) calcolato su
    ARPA (verita' di terra) contro quello gia' salvato in
    `output/trend_analysis.csv` (Open-Meteo), comune per comune.
    """
    from src.analysis.trend_analysis import linear_trend, mann_kendall_trend

    om_trends_path = Path(config.get('paths.output')) / 'trend_analysis.csv'
    om_trends = pd.read_csv(om_trends_path)

    rows = []
    for name, group in arpa_annual.groupby('municipality_name'):
        group = group.sort_values('year')
        if len(group) < 4:  # troppo pochi anni per un test Mann-Kendall affidabile
            continue
        mk = mann_kendall_trend(group['temp_mean_annual'])
        lr = linear_trend(group['year'], group['temp_mean_annual'])
        row = {
            'municipality_name': name,
            'arpa_n_years': len(group),
            'arpa_mk_trend': mk['mk_trend'],
            'arpa_mk_p_value': mk['mk_p_value'],
            'arpa_slope_per_decade': lr['lr_slope_per_decade'],
            'arpa_lr_p_value': lr['lr_p_value'],
        }
        om_row = om_trends[om_trends['municipality_name'] == name]
        if not om_row.empty:
            om_row = om_row.iloc[0]
            row.update({
                'om_n_years': om_row['n_years'],
                'om_mk_trend': om_row['mk_trend'],
                'om_mk_p_value': om_row['mk_p_value'],
                'om_slope_per_decade': om_row['lr_slope_per_decade'],
                'om_lr_p_value': om_row['lr_p_value'],
            })
        rows.append(row)
    return pd.DataFrame(rows).sort_values('municipality_name').reset_index(drop=True)


def main():
    logger.info("=" * 70)
    logger.info("VALIDAZIONE OPEN-METEO vs ARPA PIEMONTE (dati di stazione reali)")
    logger.info("=" * 70)

    paired = load_paired_temperatures()
    if paired.empty:
        logger.error("Nessuna coppia di osservazioni trovata - arpa_temperature e' vuota?")
        return

    results = validate_all_municipalities(paired)
    save_results(results)

    logger.info(f"\nRiepilogo per comune (bias/RMSE su temp_max, °C):")
    for _, row in results.iterrows():
        logger.info(
            f"{row['municipality_name']:25s} n={row['temp_max_n_days']:5.0f}  "
            f"bias={row['temp_max_bias']:+.2f}  rmse={row['temp_max_rmse']:.2f}  "
            f"r={row['temp_max_r']:.3f}"
        )

    logger.info("\nAggregato su tutti i comuni (temp_max):")
    logger.info(f"  bias medio:  {results['temp_max_bias'].mean():+.2f} °C")
    logger.info(f"  MAE medio:   {results['temp_max_mae'].mean():.2f} °C")
    logger.info(f"  RMSE medio:  {results['temp_max_rmse'].mean():.2f} °C")
    logger.info(f"  r medio:     {results['temp_max_r'].mean():.3f}")

    # Bias sui giorni davvero caldi (ARPA come verita' di terra) vs tutti i
    # giorni - il progetto misura ondate di calore, non temperatura media.
    hot_bias = hot_day_bias(paired)
    save_results(hot_bias, filename='arpa_hot_day_bias.csv')
    logger.info("\nBias su temp_max per condizione (tutti i comuni aggregati):")
    for _, row in hot_bias.iterrows():
        logger.info(
            f"  {row['condition']:28s} n={row['n_days']:6.0f}  "
            f"bias={row['bias']:+.2f}  mae={row['mae']:.2f}  rmse={row['rmse']:.2f}  r={row['r']:.3f}"
        )

    # Confronto a livello di evento: le stesse ondate di calore identificate
    # su ARPA (verita' di terra) vs quelle gia' in heatwave_events (Open-Meteo).
    matched_ids = paired['municipality_id'].unique().tolist()
    arpa_events = build_arpa_heatwave_events()
    om_events = load_om_heatwave_events(matched_ids)
    save_results(arpa_events, filename='arpa_heatwave_events.csv')

    comparison = compare_heatwave_events(om_events, arpa_events)
    save_results(pd.DataFrame([{'n_matched_municipalities': len(matched_ids), **comparison}]),
                 filename='arpa_event_comparison_summary.csv')
    logger.info(f"\nConfronto a livello di evento (soglia 35°C/3gg, {len(matched_ids)} comuni con stazione ARPA):")
    logger.info(f"  Ondate Open-Meteo: {comparison['n_om_events']}")
    logger.info(f"  Ondate ARPA (verita' di terra): {comparison['n_arpa_events']}")
    logger.info(f"  Precision (delle ondate OM, quante sono confermate da ARPA): {comparison['precision']:.1%}")
    logger.info(f"  Recall (delle ondate ARPA reali, quante OM cattura): {comparison['recall']:.1%}")

    # Confronto trend: il riscaldamento significativo gia' trovato su
    # Open-Meteo regge anche sui dati di stazione reali?
    arpa_annual = load_arpa_annual_temperature(matched_ids)
    trend_comparison = compare_trends(arpa_annual)
    save_results(trend_comparison, filename='arpa_trend_comparison.csv')

    both = trend_comparison.dropna(subset=['om_slope_per_decade'])
    sign_agree = (np.sign(both['arpa_slope_per_decade']) == np.sign(both['om_slope_per_decade'])).mean()
    arpa_sig = (both['arpa_mk_p_value'] < 0.05).sum()
    om_sig = (both['om_mk_p_value'] < 0.05).sum()
    both_sig = ((both['arpa_mk_p_value'] < 0.05) & (both['om_mk_p_value'] < 0.05)).sum()
    slope_diff = both['om_slope_per_decade'] - both['arpa_slope_per_decade']

    logger.info(f"\nConfronto trend di riscaldamento (Mann-Kendall + regressione), {len(both)} comuni:")
    logger.info(f"  Segno della pendenza concorde ARPA/Open-Meteo: {sign_agree:.1%}")
    logger.info(f"  Trend ARPA significativo (p<0.05):       {arpa_sig}/{len(both)}")
    logger.info(f"  Trend Open-Meteo significativo (p<0.05):  {om_sig}/{len(both)}")
    logger.info(f"  Entrambi significativi:                   {both_sig}/{len(both)}")
    logger.info(f"  Differenza media di pendenza (OM - ARPA): {slope_diff.mean():+.3f} °C/decade (sd={slope_diff.std():.3f})")

    logger.info("✓ Validazione ARPA completata")


if __name__ == '__main__':
    main()
