"""Caricamento database PostgreSQL/PostGIS per Heatwave Piemonte."""

import os
from pathlib import Path
from typing import Optional

from loguru import logger
from sqlalchemy import text

from src.utils.config import config
from src.utils.database import db_manager


class DatabaseLoader:
    """Loader per schema e dati nel database."""

    def __init__(self):
        self.sql_path = Path(__file__).resolve().parents[2] / 'sql' / '01_init_database.sql'
        if not self.sql_path.exists():
            raise FileNotFoundError(f'SQL script non trovato: {self.sql_path}')

    def initialize_schema(self) -> None:
        """Esegue lo script SQL di inizializzazione dello schema."""
        logger.info(f'Inizializzazione schema DB da: {self.sql_path}')
        sql_script = self.sql_path.read_text(encoding='utf-8')

        with db_manager.engine.begin() as conn:
            # Esegue lo script sul cursore DBAPI grezzo, non tramite
            # exec_driver_sql: quest'ultimo passa sempre un dict di parametri
            # (anche vuoto) a psycopg2, che quindi prova a interpretare ogni
            # "%" letterale nello script come segnaposto di parametro
            # (paramstyle pyformat) e fallisce non appena il testo ne
            # contiene uno non riconducibile a un placeholder valido.
            cursor = conn.connection.cursor()
            cursor.execute(sql_script)

        logger.success('Schema database creato/aggiornato con successo')

    def verify_schema(self) -> Optional[dict]:
        """Verifica la presenza delle tabelle principali."""
        query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('provinces', 'municipalities', 'temperature');"
        try:
            with db_manager.engine.connect() as conn:
                result = conn.execute(text(query)).fetchall()
            tables = [row[0] for row in result]
            logger.info(f'Tabelle trovate: {tables}')
            return {'tables': tables}
        except Exception as exc:
            logger.error(f'Errore verifica schema: {exc}')
            return None

    def insert_municipalities(self, csv_path: Optional[Path] = None) -> int:
        """
        Carica i comuni piemontesi (dati reali ISTAT, vedi
        `IstatGeodataDownloader.download_municipalities`) nella tabella
        `municipalities`, risolvendo `province_id` a partire dal codice
        ISTAT di provincia.
        """
        import pandas as pd

        if csv_path is None:
            csv_path = Path(config.get('paths.external_data')) / 'municipalities.csv'
        if not csv_path.exists():
            raise FileNotFoundError(
                f'{csv_path} non trovato. Esegui prima '
                'IstatGeodataDownloader.download_municipalities().'
            )

        # keep_default_na=False evita che pandas trasformi in NaN il nome del
        # comune "None" (provincia di Torino) o altri valori testuali che
        # coincidono con le stringhe NA di default di pandas.
        df = pd.read_csv(
            csv_path,
            dtype={'istat_code': str, 'province_istat_code': str},
            keep_default_na=False,
            na_values=[''],
        )

        with db_manager.engine.begin() as conn:
            province_rows = conn.execute(text('SELECT province_id, istat_code FROM provinces')).fetchall()
        province_map = {row.istat_code: row.province_id for row in province_rows}

        missing_provinces = set(df['province_istat_code']) - set(province_map)
        if missing_provinces:
            raise ValueError(f'Codici provincia ISTAT non trovati in provinces: {missing_provinces}')

        records = [
            {
                'province_id': province_map[row.province_istat_code],
                'name': row.name,
                'istat_code': row.istat_code,
                'geometry_wkt': row.geometry_wkt,
                'area_km2': row.area_km2,
            }
            for row in df.itertuples(index=False)
        ]

        query = text(
            "INSERT INTO municipalities (province_id, name, istat_code, geometry, area_km2) "
            "VALUES (:province_id, :name, :istat_code, ST_Multi(ST_GeomFromText(:geometry_wkt, 4326)), :area_km2) "
            "ON CONFLICT (istat_code) DO NOTHING"
        )

        with db_manager.engine.begin() as conn:
            conn.execute(query, records)

        logger.success(f'{len(records)} comuni inseriti/aggiornati in municipalities')
        return len(records)

    def insert_temperature(self, csv_path: Optional[Path] = None, page_size: int = 5000) -> int:
        """
        Carica `data/processed/temperature_clean.csv` nella tabella
        `temperature` a batch.

        I dati Open-Meteo sono per provincia (una stazione = il capoluogo),
        non per comune: ogni riga viene associata al comune capoluogo di
        provincia (unico comune per cui esiste davvero una misura). Gli
        altri comuni della provincia restano senza dati di temperatura —
        vedi [ETL](../../docs/pages/etl-pipeline.md) per la motivazione.
        """
        import pandas as pd
        from psycopg2.extras import execute_values

        if csv_path is None:
            csv_path = Path(config.get('paths.processed_data')) / 'temperature_clean.csv'
        if not csv_path.exists():
            raise FileNotFoundError(
                f'{csv_path} non trovato. Esegui prima '
                'src.data_processing.clean_data (DataCleaner.clean_data).'
            )

        df = pd.read_csv(csv_path, parse_dates=['date'])

        # Nome del comune capoluogo per provincia: coincide col nome della
        # provincia per 7 province su 8. Eccezione: la provincia
        # "Verbano-Cusio-Ossola" (nome dell'ente, nato dalla fusione di più
        # aree) ha come capoluogo il comune di Verbania.
        capital_name_by_province = {'Verbano-Cusio-Ossola': 'Verbania'}

        with db_manager.engine.begin() as conn:
            province_rows = conn.execute(text('SELECT province_id, name FROM provinces')).fetchall()
            municipality_rows = conn.execute(text(
                'SELECT m.municipality_id, m.name, p.name AS province_name '
                'FROM municipalities m JOIN provinces p ON m.province_id = p.province_id'
            )).fetchall()

        province_map = {row.name: row.province_id for row in province_rows}
        municipality_by_province_and_name = {
            (row.province_name, row.name): row.municipality_id for row in municipality_rows
        }
        capital_map = {}
        for province_name in province_map:
            capital_name = capital_name_by_province.get(province_name, province_name)
            municipality_id = municipality_by_province_and_name.get((province_name, capital_name))
            if municipality_id is not None:
                capital_map[province_name] = municipality_id

        missing_capitals = set(df['province']) - set(capital_map)
        if missing_capitals:
            raise ValueError(f'Comune capoluogo non trovato per le province: {missing_capitals}')

        records = [
            (
                capital_map[row.province],
                province_map[row.province],
                row.date.date(),
                float(row.temp_mean),
                float(row.temp_max),
                float(row.temp_min),
                float(row.precipitation),
                row.data_source,
                int(row.quality_flag),
            )
            for row in df.itertuples(index=False)
        ]

        insert_sql = (
            "INSERT INTO temperature "
            "(municipality_id, province_id, date, temp_mean, temp_max, temp_min, "
            "precipitation, data_source, quality_flag) VALUES %s"
        )

        with db_manager.engine.begin() as conn:
            cursor = conn.connection.cursor()
            execute_values(cursor, insert_sql, records, page_size=page_size)

        logger.success(f'{len(records)} righe inserite in temperature')
        return len(records)

    def insert_temperature_for_municipalities(self, csv_path: Path, page_size: int = 5000) -> int:
        """
        Carica un CSV di temperature (già pulito da `DataCleaner`) che
        contiene già `municipality_id` per riga — a differenza di
        `insert_temperature()`, non serve risolvere il comune capoluogo per
        nome: usato per estendere la copertura oltre gli 8 capoluoghi (vedi
        `src/data_acquisition/download_extra_municipalities.py`).
        """
        import pandas as pd
        from psycopg2.extras import execute_values

        if not csv_path.exists():
            raise FileNotFoundError(f'{csv_path} non trovato.')

        df = pd.read_csv(csv_path, parse_dates=['date'])

        with db_manager.engine.begin() as conn:
            municipality_rows = conn.execute(
                text('SELECT municipality_id, province_id FROM municipalities')
            ).fetchall()
        province_by_municipality = {row.municipality_id: row.province_id for row in municipality_rows}

        missing = set(df['municipality_id']) - set(province_by_municipality)
        if missing:
            raise ValueError(f'municipality_id non trovati in municipalities: {missing}')

        records = [
            (
                int(row.municipality_id),
                province_by_municipality[row.municipality_id],
                row.date.date(),
                float(row.temp_mean),
                float(row.temp_max),
                float(row.temp_min),
                float(row.precipitation),
                row.data_source,
                int(row.quality_flag),
            )
            for row in df.itertuples(index=False)
        ]

        insert_sql = (
            "INSERT INTO temperature "
            "(municipality_id, province_id, date, temp_mean, temp_max, temp_min, "
            "precipitation, data_source, quality_flag) VALUES %s"
        )

        with db_manager.engine.begin() as conn:
            cursor = conn.connection.cursor()
            execute_values(cursor, insert_sql, records, page_size=page_size)

        logger.success(f'{len(records)} righe inserite in temperature (comuni extra)')
        return len(records)

    def insert_arpa_temperature(self, csv_path: Optional[Path] = None, page_size: int = 5000) -> int:
        """
        Carica `data/raw/arpa_temperature.csv` (osservazioni di stazione
        reali ARPA Piemonte, vedi `src/data_acquisition/download_arpa.py`)
        nella tabella `arpa_temperature`, per la validazione delle stime
        Open-Meteo in `temperature`.
        """
        import pandas as pd
        from psycopg2.extras import execute_values

        if csv_path is None:
            csv_path = Path(config.get('paths.raw_data')) / 'arpa_temperature.csv'
        if not csv_path.exists():
            raise FileNotFoundError(
                f'{csv_path} non trovato. Esegui prima '
                'src.data_acquisition.download_arpa.'
            )

        df = pd.read_csv(csv_path, parse_dates=['date'])

        records = [
            (
                int(row.municipality_id),
                row.station_code,
                row.station_name,
                row.date.date(),
                None if pd.isna(row.temp_mean) else float(row.temp_mean),
                None if pd.isna(row.temp_max) else float(row.temp_max),
                None if pd.isna(row.temp_min) else float(row.temp_min),
            )
            for row in df.itertuples(index=False)
        ]

        insert_sql = (
            "INSERT INTO arpa_temperature "
            "(municipality_id, station_code, station_name, date, temp_mean, temp_max, temp_min) VALUES %s "
            "ON CONFLICT (station_code, date) DO NOTHING"
        )

        with db_manager.engine.begin() as conn:
            cursor = conn.connection.cursor()
            execute_values(cursor, insert_sql, records, page_size=page_size)

        logger.success(f'{len(records)} righe inserite/aggiornate in arpa_temperature')
        return len(records)

    def insert_sample_province(self) -> None:
        """Inserisce un record di prova nella tabella provinces."""
        query = text(
            "INSERT INTO provinces (name, istat_code, geometry, area_km2, population) "
            "VALUES (:name, :istat_code, ST_SetSRID(ST_Point(:lon, :lat), 4326), :area, :population) "
            "ON CONFLICT (name) DO NOTHING"
        )
        params = {
            'name': 'Test Comune Piemonte',
            'istat_code': '999',
            'lon': 7.6866,
            'lat': 45.0730,
            'area': 10.0,
            'population': 1000,
        }

        with db_manager.engine.begin() as conn:
            conn.execute(query, params)

        logger.success('Record di prova inserito in provinces')


def main():
    loader = DatabaseLoader()
    loader.initialize_schema()
    verification = loader.verify_schema()
    if not verification:
        logger.error('Verifica schema fallita: tabelle mancanti.')
        return

    if 'municipalities' in verification['tables']:
        try:
            loader.insert_municipalities()
        except FileNotFoundError as e:
            logger.warning(str(e))

    if 'temperature' in verification['tables']:
        try:
            loader.insert_temperature()
        except FileNotFoundError as e:
            logger.warning(str(e))

    logger.info('Caricamento DB completato.')


if __name__ == '__main__':
    main()
