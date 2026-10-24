"""
heatwave_stats.py - Statistiche sulle Ondate di Calore

Calcola `intensity_index` e `mean_temp` per le ondate identificate da
`identify_heatwaves()` (lasciati NULL dalla funzione SQL, vedi
docs/pages/data-model.md) e produce statistiche aggregate per comune e
per anno.

Usage:
    python -m src.analysis.heatwave_stats
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import text

from src.utils.config import config
from src.utils.database import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


def backfill_intensity_and_mean_temp() -> int:
    """
    Popola `intensity_index` (= (max_temp - heat_threshold) * duration_days)
    e `mean_temp` (media di temperature.temp_mean nel periodo dell'ondata,
    per lo stesso comune) per le righe di `heatwave_events` non ancora
    calcolate.

    Returns:
        int: numero di righe aggiornate
    """
    update_sql = text("""
        UPDATE heatwave_events h
        SET intensity_index = (h.max_temp - h.heat_threshold) * h.duration_days,
            mean_temp = sub.avg_temp
        FROM (
            SELECT
                he.heatwave_id,
                AVG(t.temp_mean) AS avg_temp
            FROM heatwave_events he
            JOIN temperature t
                ON t.municipality_id = he.municipality_id
                AND t.date BETWEEN he.start_date AND he.end_date
            GROUP BY he.heatwave_id
        ) sub
        WHERE h.heatwave_id = sub.heatwave_id
          AND (h.intensity_index IS NULL OR h.mean_temp IS NULL)
    """)

    with db_manager.engine.begin() as conn:
        result = conn.execute(update_sql)
        updated = result.rowcount

    logger.info(f"✓ {updated} ondate aggiornate (intensity_index, mean_temp)")
    return updated


def load_heatwave_events() -> pd.DataFrame:
    """Carica heatwave_events con nome comune/provincia."""
    query = """
        SELECT
            m.name AS municipality_name,
            p.name AS province_name,
            h.start_date, h.end_date, h.duration_days,
            h.max_temp, h.mean_temp, h.intensity_index, h.heat_threshold
        FROM heatwave_events h
        JOIN municipalities m ON h.municipality_id = m.municipality_id
        JOIN provinces p ON h.province_id = p.province_id
        ORDER BY h.start_date
    """
    rows = db_manager.execute_query(query)
    columns = [
        'municipality_name', 'province_name', 'start_date', 'end_date',
        'duration_days', 'max_temp', 'mean_temp', 'intensity_index', 'heat_threshold',
    ]
    return pd.DataFrame(rows, columns=columns)


def summary_by_municipality(df: pd.DataFrame) -> pd.DataFrame:
    """Statistiche aggregate per comune."""
    summary = df.groupby('municipality_name').agg(
        n_heatwaves=('duration_days', 'count'),
        avg_duration_days=('duration_days', 'mean'),
        max_duration_days=('duration_days', 'max'),
        avg_intensity=('intensity_index', 'mean'),
        max_intensity=('intensity_index', 'max'),
        avg_max_temp=('max_temp', 'mean'),
    ).round(2).sort_values('n_heatwaves', ascending=False)
    return summary.reset_index()


def frequency_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """
    Conteggio ondate per anno (frequenza), su tutti i comuni, con durata e
    intensità media associate (usate dal grafico a barre della pagina
    'Ondate di Calore' nella dashboard).
    """
    df = df.copy()
    df['year'] = pd.to_datetime(df['start_date']).dt.year
    yearly = df.groupby('year').agg(
        n_heatwaves=('duration_days', 'count'),
        avg_duration_days=('duration_days', 'mean'),
        avg_intensity=('intensity_index', 'mean'),
    )
    # Range dinamico (non più un fisso 2000-2025): un anno finale hardcoded
    # nascondeva silenziosamente le ondate rilevate nell'anno corrente
    # quando la serie storica è stata estesa fino ad oggi (bug reale
    # trovato il 2026-07-17: 16 ondate del 2026 scartate dal reindex).
    first_year = int(df['year'].min())
    last_year = int(df['year'].max())
    return (
        yearly.reindex(range(first_year, last_year + 1), fill_value=0)
        .round(2)
        .reset_index()
        .rename(columns={'index': 'year'})
    )


def save_results(df: pd.DataFrame, filename: str) -> Path:
    output_path = Path(config.get('paths.output')) / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(f"✓ Risultati salvati: {output_path}")
    return output_path


def main():
    logger.info("=" * 70)
    logger.info("STATISTICHE ONDATE DI CALORE")
    logger.info("=" * 70)

    backfill_intensity_and_mean_temp()

    df = load_heatwave_events()
    logger.info(f"Ondate totali: {len(df)}")

    by_municipality = summary_by_municipality(df)
    save_results(by_municipality, 'heatwave_stats_by_municipality.csv')
    for _, row in by_municipality.iterrows():
        logger.info(
            f"{row['municipality_name']:15s} n={row['n_heatwaves']:2.0f}  "
            f"durata media={row['avg_duration_days']:.1f}gg  "
            f"intensità media={row['avg_intensity']:.1f}"
        )

    by_year = frequency_by_year(df)
    save_results(by_year, 'heatwave_frequency_by_year.csv')

    logger.info("✓ Analisi ondate di calore completata")


if __name__ == '__main__':
    main()
