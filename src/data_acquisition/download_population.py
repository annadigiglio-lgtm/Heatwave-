"""
download_population.py - Popola municipalities.population con dati ISTAT reali.

`population` esiste nello schema (`sql/01_init_database.sql`) ma non era mai
stato popolato (NULL per tutti i 1180 comuni) - vedi
paper/PIANO-ARTICOLO.md. Necessario come covariata esplicativa per
il paper scientifico (densita' demografica, uso del suolo urbano).

Fonte: demo.istat.it ("Popolazione residente per eta' e sesso"), un file ZIP
per provincia, CSV con una riga per comune/eta'/sesso; la riga con eta'=999
e' il totale per comune. Non richiede API key/account.

Investigazione 2026-07-16 (vedi paper/PIANO-ARTICOLO.md per il
dettaglio completo): il nuovo sistema SDMX (esploradati.istat.it) ha la
struttura giusta (stessi codici istat_code) ma non restituisce osservazioni
per questo dataset; il vecchio portale dati.istat.it e' dismesso (redirect
a un avviso di decommissioning). demo.istat.it e' invece un sistema attivo
e separato, con export CSV diretto via ZIP per provincia - percorso
verificato con richieste HTTP dirette.

Usage:
    python -m src.data_acquisition.download_population
"""

import io
import zipfile

import pandas as pd
import requests

from src.utils.database import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL = "https://demo.istat.it/data/posas/POSAS_{year}_it_{code}_{name}.zip"
TOTAL_AGE_CODE = '999'

# Le 8 province piemontesi con i codici ISTAT reali (vedi tabella `provinces`
# nel DB, gia' verificati contro lo shapefile ISTAT il 2026-07-04).
PROVINCES = [
    ('001', 'Torino'),
    ('002', 'Vercelli'),
    ('003', 'Novara'),
    ('004', 'Cuneo'),
    ('005', 'Asti'),
    ('006', 'Alessandria'),
    ('096', 'Biella'),
    ('103', 'Verbano-Cusio-Ossola'),
]


def download_province_population(year: int, code: str, name: str) -> pd.DataFrame:
    """Scarica il file ZIP di una provincia e restituisce il totale per comune."""
    url = BASE_URL.format(year=year, code=code, name=name)
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        csv_name = zf.namelist()[0]
        with zf.open(csv_name) as f:
            # skiprows=1: la prima riga e' un titolo descrittivo, non l'header.
            # dtype=str ovunque: la colonna eta' e' letta come stringa (mix di
            # numeri e, implicitamente, righe vuote), il confronto va fatto
            # sulla stringa '999', non sull'intero 999 (verificato: un
            # confronto numerico restituisce sempre 0 righe).
            df = pd.read_csv(f, sep=';', encoding='utf-8-sig', skiprows=1,
                              dtype=str, keep_default_na=False)

    age_col = df.columns[2]  # 'Eta'' - accentata, riferita per posizione per
                              # evitare problemi di encoding della shell/console
    totals = df[df[age_col] == TOTAL_AGE_CODE].copy()
    totals['Totale'] = totals['Totale'].astype(int)
    return totals[['Codice comune', 'Comune', 'Totale']].rename(
        columns={'Codice comune': 'istat_code', 'Comune': 'name', 'Totale': 'population'}
    )


def update_population(totals: pd.DataFrame) -> int:
    """Aggiorna municipalities.population via istat_code. Restituisce quanti comuni sono stati trovati nel DB."""
    updated = 0
    for _, row in totals.iterrows():
        result = db_manager.execute_update(
            "UPDATE municipalities SET population = :population, "
            "updated_at = CURRENT_TIMESTAMP WHERE istat_code = :istat_code",
            {'population': int(row['population']), 'istat_code': row['istat_code']},
        )
        if result:
            updated += 1
    return updated


def main(year: int = 2026):
    total_updated = 0
    total_rows = 0

    for code, name in PROVINCES:
        logger.info(f"Download popolazione {name} ({code})...")
        totals = download_province_population(year, code, name)
        total_rows += len(totals)
        updated = update_population(totals)
        total_updated += updated
        logger.info(f"  {name}: {len(totals)} comuni nel file ISTAT, {updated} aggiornati nel DB")

    logger.info(f"Popolazione aggiornata per {total_updated}/{total_rows} comuni totali (stima 1 gennaio {year}).")


if __name__ == "__main__":
    main()
