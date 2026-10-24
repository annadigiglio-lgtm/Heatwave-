"""
download_data.py - Acquisizione Dati da Fonti Pubbliche

Script per download di dati climatici da Open-Meteo API.
Generate dati geografici di riferimento (province, comuni).

Sources:
    - Open-Meteo: API meteorologica free (2000-2026) - NO API KEY REQUIRED
    - Generated geometries: Province e comuni piemontesi

Usage:
    python src/data_acquisition/download_data.py --years 2000:2026 --regions all
    
Output:
    - data/raw/temperature_data.csv (1.7M record)
    - data/external/provinces.csv (8 province)
    - data/external/municipalities.csv (50 comuni)
"""

import argparse
import json
import os
import zipfile
from datetime import datetime, timedelta
from io import BytesIO, StringIO
from pathlib import Path
from typing import List, Optional

import pandas as pd
import requests
import time

from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WeatherDataDownloader:
    """Downloader per dati meteorologici da API Open-Meteo."""
    
    BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
    PIEMONTE_REGIONS = {
        "Torino": (45.0730, 7.6866),
        "Alessandria": (44.9116, 8.6386),
        "Asti": (44.8988, 8.1917),
        "Biella": (45.5589, 8.0555),
        "Cuneo": (44.3935, 7.5412),
        "Novara": (45.4469, 8.6236),
        "Verbano-Cusio-Ossola": (45.9308, 8.5608),
        "Vercelli": (45.3203, 8.4266),
    }
    
    def __init__(self):
        """Inizializza il downloader."""
        self.data_path = Path(config.get('paths.raw_data'))
        self.data_path.mkdir(parents=True, exist_ok=True)
    
    def download_historical_data(
        self,
        region: str,
        start_date: str = "2000-01-01",
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Scarica dati storici da Open-Meteo per uno degli 8 capoluoghi
        hardcoded in PIEMONTE_REGIONS.

        Args:
            region (str): Regione piemontese
            start_date (str): Data inizio (YYYY-MM-DD)
            end_date (str): Data fine (YYYY-MM-DD)

        Returns:
            pd.DataFrame: Dataframe con dati temperature
        """
        if region not in self.PIEMONTE_REGIONS:
            logger.error(f"Regione non riconosciuta: {region}")
            raise ValueError(f"Regione non trovata: {region}")

        latitude, longitude = self.PIEMONTE_REGIONS[region]
        return self.download_for_coordinates(region, latitude, longitude, start_date, end_date)

    def download_for_coordinates(
        self,
        name: str,
        latitude: float,
        longitude: float,
        start_date: str = "2000-01-01",
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Scarica dati storici da Open-Meteo per una coppia di coordinate
        arbitraria (non limitata agli 8 capoluoghi) — usata per estendere
        la copertura ad altri comuni, vedi
        `src/data_acquisition/download_extra_municipalities.py`.

        Args:
            name (str): Nome del comune (solo per log/colonna 'province')
            latitude (float): Latitudine
            longitude (float): Longitudine
            start_date (str): Data inizio (YYYY-MM-DD)
            end_date (str): Data fine (YYYY-MM-DD)

        Returns:
            pd.DataFrame: Dataframe con dati temperature
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        region = name
        logger.info(f"Download dati {region} ({start_date} - {end_date})")

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum",
            "timezone": "Europe/Rome"
        }
        
        max_retries = 5
        backoff_seconds = 5

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(
                    self.BASE_URL,
                    params=params,
                    timeout=30
                )

                if response.status_code == 429:
                    wait = int(response.headers.get('Retry-After', backoff_seconds))
                    logger.warning(
                        f"Rate limit raggiunto per {region}, "
                        f"attesa {wait}s (tentativo {attempt}/{max_retries})"
                    )
                    time.sleep(wait)
                    backoff_seconds *= 2
                    continue

                response.raise_for_status()
                data = response.json()

                # Trasforma in DataFrame
                df = pd.DataFrame({
                    'date': pd.to_datetime(data['daily']['time']),
                    'temp_max': data['daily']['temperature_2m_max'],
                    'temp_min': data['daily']['temperature_2m_min'],
                    'temp_mean': data['daily']['temperature_2m_mean'],
                    'precipitation': data['daily']['precipitation_sum'],
                    'province': region,
                    'data_source': 'OpenMeteo'
                })

                logger.info(f"✓ Downloaded {len(df)} records for {region}")
                return df

            except requests.RequestException as e:
                logger.error(f"✗ Errore download: {e}")
                raise

        raise RuntimeError(f"Rate limit persistente per {region} dopo {max_retries} tentativi")
    
    def download_all_regions(
        self,
        start_date: str = "2000-01-01",
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Scarica dati per tutte le province piemontesi.
        
        Args:
            start_date (str): Data inizio
            end_date (str): Data fine
            
        Returns:
            pd.DataFrame: Dataframe consolidato
        """
        logger.info("Inizio download per tutte le province...")
        
        all_data = []
        
        for region in self.PIEMONTE_REGIONS.keys():
            try:
                df = self.download_historical_data(region, start_date, end_date)
                all_data.append(df)
                time.sleep(3)  # Rate limiting
            except Exception as e:
                logger.error(f"Errore download {region}: {e}")
                continue
        
        if all_data:
            consolidated = pd.concat(all_data, ignore_index=True)
            logger.info(f"✓ Download completato: {len(consolidated)} records totali")
            return consolidated
        else:
            raise RuntimeError("Nessun dato scaricato")
    
    def save_data(self, df: pd.DataFrame, filename: str) -> None:
        """
        Salva dataframe in CSV.
        
        Args:
            df (pd.DataFrame): Dataframe da salvare
            filename (str): Nome file
        """
        filepath = self.data_path / filename
        df.to_csv(filepath, index=False)
        logger.info(f"✓ Dati salvati: {filepath}")


class CopernicusERA5Downloader:
    """Downloader per i dati Copernicus ERA5 dal Climate Data Store."""

    def __init__(self):
        self.raw_path = Path(config.get('paths.raw_data'))
        self.raw_path.mkdir(parents=True, exist_ok=True)
        self.api_url = config.get('data_sources.copernicus.url')
        self.dataset = config.get('data_sources.copernicus.dataset')
        self.variables = config.get('data_sources.copernicus.variables') or [
            '2m_temperature', 'total_precipitation', 'surface_pressure'
        ]
        self.area = config.get('data_sources.copernicus.area')
        self.client = self._create_cds_client()

    def _create_cds_client(self) -> Optional["cdsapi.Client"]:
        api_url = self.api_url or os.getenv('CDS_URL')
        api_key = os.getenv('CDS_KEY')

        if not api_key:
            logger.warning('CDS_KEY non impostata. Il download Copernicus potrebbe fallire.')

        try:
            import cdsapi
        except Exception:
            logger.warning('cdsapi non installato; Copernicus download disabilitato.')
            return None

        return cdsapi.Client(url=api_url, key=api_key)

    def download_era5(self, start_year: int, end_year: int) -> Path:
        """Scarica dataset ERA5 per il range di anni configurato."""
        file_name = f'copernicus_era5_{start_year}_{end_year}.nc'
        target_file = self.raw_path / file_name

        if target_file.exists():
            logger.info(f'File Copernicus già presente: {target_file}')
            return target_file

        years = [str(year) for year in range(start_year, end_year + 1)]
        months = [f'{month:02d}' for month in range(1, 13)]
        days = [f'{day:02d}' for day in range(1, 32)]

        request_payload = {
            'product_type': config.get('data_sources.copernicus.product_type', 'reanalysis'),
            'format': config.get('data_sources.copernicus.format', 'netcdf'),
            'variable': self.variables,
            'year': years,
            'month': months,
            'day': days,
            'time': ['00:00'],
            'area': self.area,
        }

        logger.info(f'Download Copernicus ERA5 {start_year}-{end_year} in {target_file}')
        self.client.retrieve(self.dataset, request_payload, target_file.as_posix())
        logger.info(f'✓ File Copernicus salvato: {target_file}')
        return target_file


class ArpaPiemonteDownloader:
    """
    Downloader ARPA Piemonte per dati climatici e meteo locali.

    NOTA (2026-07-18): l'URL configurato in `config.yaml`
    (`arpa_piemonte.url`) risponde 404 - non e' mai stato un endpoint dati
    reale. Per la validazione ARPA (fase 1 del piano paper, vedi
    paper/PIANO-ARTICOLO.md) usare invece
    `src/data_acquisition/download_arpa.py`, che usa la vera API REST
    pubblica di ARPA Piemonte (`utility.arpa.piemonte.it/meteoidro/`).
    Questa classe resta cosi' com'era, non funzionante, per riferimento
    storico - vedi docs/pages/data-sources.md.
    """

    def __init__(self):
        self.raw_path = Path(config.get('paths.raw_data'))
        self.raw_path.mkdir(parents=True, exist_ok=True)
        self.url = config.get('data_sources.arpa_piemonte.url')

    def download_station_data(self) -> Path:
        """Scarica dati stazione ARPA Piemonte dal link configurato."""
        if not self.url:
            raise ValueError('URL ARPA Piemonte non configurato in config.yaml')

        target_file = self.raw_path / 'arpa_piemonte_climate_data.csv'
        headers = {'User-Agent': 'HeatwavePiemonte/1.0'}

        logger.info(f'Download ARPA Piemonte da {self.url}')
        response = requests.get(self.url, headers=headers, timeout=60)
        response.raise_for_status()

        if 'csv' in response.headers.get('content-type', '') or self.url.lower().endswith('.csv'):
            df = pd.read_csv(StringIO(response.text))
            df.to_csv(target_file, index=False)
        else:
            target_file.write_bytes(response.content)

        logger.info(f'✓ Dati ARPA Piemonte salvati: {target_file}')
        return target_file


class IstatGeodataDownloader:
    """Downloader dati geografici amministrativi ISTAT."""

    def __init__(self):
        self.external_path = Path(config.get('paths.external_data'))
        self.external_path.mkdir(parents=True, exist_ok=True)
        self.municipalities_url = config.get('data_sources.istat.municipalities_url')
        self.provinces_url = config.get('data_sources.istat.provinces_url')

    def download_municipalities(self) -> Path:
        """
        Scarica lo shapefile ISTAT dei confini comunali (zip), filtra i comuni
        piemontesi (COD_REG == 1) e salva i risultati in GeoJSON + CSV
        (quest'ultimo pronto per il caricamento in `municipalities`).
        """
        if not self.municipalities_url:
            raise ValueError('URL ISTAT non configurato per i comuni')

        import geopandas as gpd

        confini_dir = self.external_path / 'istat_confini'
        confini_dir.mkdir(parents=True, exist_ok=True)
        zip_path = confini_dir / Path(self.municipalities_url).name

        if not zip_path.exists():
            logger.info(f'Download ISTAT da {self.municipalities_url}')
            response = requests.get(self.municipalities_url, timeout=120)
            response.raise_for_status()
            zip_path.write_bytes(response.content)
        else:
            logger.info(f'File ISTAT già presente: {zip_path}')

        with zipfile.ZipFile(zip_path) as z:
            z.extractall(confini_dir)

        shp_candidates = list(confini_dir.rglob('Com*_WGS84.shp'))
        if not shp_candidates:
            raise RuntimeError(f'Shapefile comuni non trovato in {confini_dir}')

        # I file ISTAT non includono un .cpg; l'attribute table (.dbf) è
        # codificata in UTF-8, non cp1252. FIX 2026-07-15: la versione
        # precedente di questo fix usava encoding='cp1252', basata su una
        # verifica fatta guardando il testo stampato a terminale — ma il
        # terminale stesso mostrava un mojibake che "sembrava" corretto per
        # coincidenza. Verificato a livello di byte
        # (`name.encode('utf-8')`): cp1252 produce una doppia codifica UTF-8
        # (es. "Agliè" -> b'Agli\xc3\x83\xc2\xa8' invece di
        # b'Agli\xc3\xa8'), corrompendo 28 dei 1180 nomi di comuni nel DB
        # reale. utf-8 esplicito dà il risultato corretto.
        gdf = gpd.read_file(shp_candidates[0], encoding='utf-8')
        piemonte = gdf[gdf['COD_REG'] == 1].copy()

        # Area calcolata nel CRS proiettato originale (UTM32, metri) prima
        # di riproiettare in 4326, dove i gradi non sono unità di superficie.
        piemonte['area_km2'] = piemonte.geometry.area / 1_000_000
        piemonte = piemonte.to_crs(epsg=4326)
        piemonte['istat_code'] = piemonte['PRO_COM'].apply(lambda x: f'{int(x):06d}')
        piemonte['province_istat_code'] = piemonte['COD_PROV'].apply(lambda x: f'{int(x):03d}')
        piemonte = piemonte.rename(columns={'COMUNE': 'name'})

        output_columns = ['istat_code', 'province_istat_code', 'name', 'area_km2', 'geometry']
        geojson_path = self.external_path / 'istat_municipalities.geojson'
        piemonte[output_columns].to_file(geojson_path, driver='GeoJSON')

        csv_path = self.external_path / 'municipalities.csv'
        csv_df = piemonte[['istat_code', 'province_istat_code', 'name', 'area_km2']].copy()
        csv_df['geometry_wkt'] = piemonte.geometry.to_wkt()
        csv_df.to_csv(csv_path, index=False, encoding='utf-8')

        logger.info(f'✓ {len(piemonte)} comuni piemontesi salvati: {geojson_path}, {csv_path}')
        return csv_path

    def download_provinces(self) -> Path:
        return self._download_geo_file(self.provinces_url, 'istat_provinces.geojson')

    def _download_geo_file(self, url: str, filename: str) -> Path:
        if not url:
            raise ValueError(f'URL ISTAT non configurato per {filename}')

        logger.info(f'Download ISTAT da {url}')
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        output_path = self.external_path / filename

        content_type = response.headers.get('content-type', '')
        if 'json' in content_type or url.lower().endswith(('geojson', '.json')):
            geojson_text = response.text
            try:
                import geopandas as gpd
                gdf = gpd.read_file(StringIO(geojson_text))
                gdf.to_file(output_path, driver='GeoJSON')
            except Exception:
                # Fallback: write raw geojson
                output_path.write_text(geojson_text, encoding='utf-8')
        else:
            output_path.write_bytes(response.content)

        logger.info(f'✓ Dati ISTAT salvati: {output_path}')
        return output_path


class OpenStreetMapDownloader:
    """Downloader OSM tramite Nominatim per boundary amministrativi."""

    def __init__(self):
        self.external_path = Path(config.get('paths.external_data'))
        self.external_path.mkdir(parents=True, exist_ok=True)
        self.nominatim_url = config.get('data_sources.openstreetmap.nominatim_url')
        self.user_agent = os.getenv('OSM_USER_AGENT') or config.get('data_sources.openstreetmap.user_agent')

    def download_region_boundary(self, query: str = 'Regione Piemonte, Italy') -> Path:
        if not self.nominatim_url:
            raise ValueError('Nominatim URL non configurato in config.yaml')

        params = {
            'q': query,
            'format': 'jsonv2',
            'polygon_geojson': 1,
            'limit': 1,
        }
        headers = {'User-Agent': self.user_agent}

        logger.info(f'Download confine OSM per: {query}')
        response = requests.get(self.nominatim_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        results = response.json()
        if not results:
            raise RuntimeError(f'Nessun risultato OSM per query: {query}')

        feature = results[0]
        geojson = {
            'type': 'FeatureCollection',
            'features': [{
                'type': 'Feature',
                'properties': {
                    'display_name': feature.get('display_name'),
                    'osm_type': feature.get('osm_type'),
                    'osm_id': feature.get('osm_id'),
                },
                'geometry': feature.get('geojson'),
            }],
        }

        output_path = self.external_path / 'osm_piemonte_boundary.geojson'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)

        logger.info(f'✓ Confine OSM salvato: {output_path}')
        return output_path


class ReferenceDataManager:
    """Orchestratore per il download dei dati di riferimento geografici."""

    def __init__(self):
        self.istat_downloader = IstatGeodataDownloader()
        self.osm_downloader = OpenStreetMapDownloader()
        self.arpa_downloader = ArpaPiemonteDownloader()

    def download_all_reference_data(self) -> None:
        self.arpa_downloader.download_station_data()
        self.istat_downloader.download_municipalities()
        self.istat_downloader.download_provinces()
        self.osm_downloader.download_region_boundary()


def parse_sources(source_list: str) -> List[str]:
    if source_list.lower() in ('all', '*'):
        return ['open_meteo', 'copernicus', 'arpa_piemonte', 'istat', 'openstreetmap']
    return [source.strip() for source in source_list.split(',') if source.strip()]


def main():
    """Funzione principale."""
    parser = argparse.ArgumentParser(
        description='Download dati climatici per Heatwave Piemonte'
    )
    parser.add_argument(
        '--years',
        type=str,
        default='2000:2026',
        help='Range anni (es. 2000:2026)'
    )
    parser.add_argument(
        '--regions',
        type=str,
        default='all',
        help='Province (es. Torino,Alessandria o "all")'
    )
    parser.add_argument(
        '--sources',
        type=str,
        default='open_meteo,copernicus',
        help='Sorgenti dati da scaricare (open_meteo,copernicus,arpa_piemonte,istat,openstreetmap,all)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='temperature_data.csv',
        help='Nome file output per i dati Open-Meteo'
    )

    args = parser.parse_args()

    start_year, end_year = map(int, args.years.split(':'))
    start_date = f'{start_year}-01-01'
    end_date = f'{end_year}-12-31'
    sources = parse_sources(args.sources)

    logger.info('=' * 70)
    logger.info('HEATWAVE PIEMONTE - Data Download')
    logger.info('=' * 70)
    logger.info(f'Periodo: {start_date} - {end_date}')
    logger.info(f'Sorgenti: {sources}')

    try:
        if 'open_meteo' in sources:
            weather_downloader = WeatherDataDownloader()
            df_weather = weather_downloader.download_all_regions(start_date, end_date)
            weather_downloader.save_data(df_weather, args.output)

        if 'copernicus' in sources:
            copernicus_downloader = CopernicusERA5Downloader()
            copernicus_downloader.download_era5(start_year, end_year)

        if 'arpa_piemonte' in sources:
            arpa_downloader = ArpaPiemonteDownloader()
            arpa_downloader.download_station_data()

        if 'istat' in sources or 'openstreetmap' in sources:
            ref_manager = ReferenceDataManager()
            if 'istat' in sources:
                ref_manager.istat_downloader.download_municipalities()
                ref_manager.istat_downloader.download_provinces()
            if 'openstreetmap' in sources:
                ref_manager.osm_downloader.download_region_boundary()

        logger.info('=' * 70)
        logger.info('✓ Download completato con successo')
        logger.info('=' * 70)

    except Exception as e:
        logger.error(f'✗ Errore: {e}')
        raise


if __name__ == '__main__':
    main()
