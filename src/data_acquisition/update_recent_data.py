"""
update_recent_data.py - Estende la serie storica fino a oggi per tutti i
comuni già presenti in `temperature`.

Motivazione: il download iniziale (8 capoluoghi) e le due estensioni
successive (a 44, poi a 300 comuni) si fermavano al 31/12/2025. Questo
script scarica solo il **delta** (dal 1° gennaio dell'anno corrente a
oggi) per tutti i comuni già scaricati, così la serie arriva fino
all'ultimo giorno realmente disponibile su Open-Meteo (di norma "oggi
stesso", verificato: nessun ritardo riscontrato per Torino il 2026-07-16).

Non ridownloada mai 2000-2025 (evita duplicati: `temperature` non ha un
vincolo di unicità su (municipality_id, date), quindi un doppio insert
sullo stesso periodo creerebbe righe duplicate silenziosamente).

**Salvataggio incrementale** (2026-07-17, stessa lezione imparata con
`download_extra_municipalities.py`): il rate limit giornaliero di
Open-Meteo può scattare senza preavviso a metà esecuzione — ogni comune
scaricato con successo viene subito appeso al CSV di output, non solo
alla fine.

Usage:
    python -m src.data_acquisition.update_recent_data
"""

from datetime import date
from pathlib import Path

import pandas as pd
import time

from src.data_acquisition.download_data import WeatherDataDownloader
from src.utils.config import config
from src.utils.database import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_municipalities_with_data() -> pd.DataFrame:
    """
    Comuni già presenti in `temperature`, con centroide della geometria.

    Ordinati con i comuni che hanno anche copertura ARPA per primi (`has_arpa`
    DESC): la quota giornaliera Open-Meteo è imprevedibile (vedi
    wiki/pages/data-sources.md) e può bloccare il run a metà, quindi
    conviene garantire prima il delta dei comuni utili al confronto
    ARPA/Open-Meteo, poi il resto in ordine alfabetico.
    """
    query = """
        SELECT DISTINCT m.municipality_id, m.name,
               ST_Y(ST_Centroid(m.geometry)) AS lat,
               ST_X(ST_Centroid(m.geometry)) AS lon,
               EXISTS (
                   SELECT 1 FROM arpa_temperature a WHERE a.municipality_id = m.municipality_id
               ) AS has_arpa
        FROM municipalities m
        JOIN temperature t ON t.municipality_id = m.municipality_id
        ORDER BY has_arpa DESC, m.name
    """
    rows = db_manager.execute_query(query)
    columns = ['municipality_id', 'name', 'lat', 'lon', 'has_arpa']
    return pd.DataFrame(rows, columns=columns)


def latest_date_per_municipality() -> dict:
    """Ultima data già presente in `temperature` per ciascun comune."""
    rows = db_manager.execute_query(
        'SELECT municipality_id, MAX(date) FROM temperature GROUP BY municipality_id;'
    )
    return {row[0]: row[1] for row in rows}


def download_recent(municipalities: pd.DataFrame, latest_dates: dict, end_date: str, output_path: Path) -> int:
    """
    Scarica solo il delta (dal giorno dopo l'ultima data nota fino a
    end_date) per comune, **appendendo ogni comune al CSV non appena
    scaricato** — un'interruzione a metà (es. rate limit giornaliero) non
    fa perdere il lavoro già fatto.

    Returns:
        int: numero di comuni aggiornati con successo in questa esecuzione
    """
    downloader = WeatherDataDownloader()
    file_exists = output_path.exists()
    n_success = 0
    n_failed = 0

    for _, row in municipalities.iterrows():
        last_known = latest_dates.get(row['municipality_id'])
        start_date = (last_known + pd.Timedelta(days=1)).strftime('%Y-%m-%d') if last_known else '2000-01-01'
        if start_date > end_date:
            continue
        try:
            df = downloader.download_for_coordinates(row['name'], row['lat'], row['lon'], start_date, end_date)
            if df.empty:
                continue
            df['municipality_id'] = row['municipality_id']

            df.to_csv(output_path, mode='a', header=not file_exists, index=False)
            file_exists = True
            n_success += 1

            time.sleep(3)
        except Exception as e:
            logger.error(f"Errore download {row['name']}: {e}")
            n_failed += 1
            continue

    logger.info(f"✓ Aggiornamento completato in questa esecuzione: {n_success} comuni riusciti, {n_failed} falliti")
    return n_success


def main():
    logger.info("=" * 70)
    logger.info("AGGIORNAMENTO DATI RECENTI (fino ad oggi)")
    logger.info("=" * 70)

    today = date.today().strftime('%Y-%m-%d')
    municipalities = load_municipalities_with_data()
    latest_dates = latest_date_per_municipality()
    n_arpa = int(municipalities['has_arpa'].sum())
    logger.info(
        f"{len(municipalities)} comuni con dati ({n_arpa} con copertura ARPA, scaricati per primi); "
        f"aggiornamento fino al {today}"
    )

    output_path = Path(config.get('paths.raw_data')) / 'temperature_data_recent.csv'
    n_success = download_recent(municipalities, latest_dates, today, output_path)

    logger.info(f"✓ Dati salvati incrementalmente in: {output_path} ({n_success} comuni aggiornati in questa esecuzione)")


if __name__ == '__main__':
    main()
