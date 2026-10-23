"""
process_ndvi.py - Calcola NDVI medio (verde da satellite) per comune.

Popola `municipality_ndvi` (vedi sql/04_ndvi.sql), covariata esplicativa
complementare a `municipality_land_cover` (CORINE) per il paper scientifico -
vedi paper/PIANO-ARTICOLO.md. Dove CORINE da' classi discrete di uso
del suolo, l'NDVI da' una misura continua di "quanto verde" c'e' anche
dentro una singola classe (es. un urbano con molti alberi vs uno senza).

Fonte: Copernicus Global Land Service (CGLS) NDVI 300m V3, composito
10-giornaliero, scaricato manualmente dall'utente (decisione 2026-07-17,
stesso pattern low-effort gia' usato per CORINE: niente account/API
Sentinel-2 vero, un prodotto NDVI gia' calcolato via Copernicus Browser/
Data Space Ecosystem). Raster GeoTIFF, EPSG:4326 (grid geografica globale -
diversamente da CLC/EPSG:3035, qui non serve riproiezione per l'area).

Il file e' a 8 bit (DN 0-255): DN 0-250 sono NDVI reale via
`NDVI = DN * 0.004 - 0.08` (range -0.08..0.92) - **verificato il
2026-07-17 direttamente sui metadati embedded del GeoTIFF reale**
(`rasterio.open(...).scales/.offsets`, non solo dalla documentazione
online, che per questo prodotto si e' rivelata imprecisa proprio sui
codici di flag, vedi sotto). DN 252-255 sono flag dedicati - valori
reali letti da `tags(1)['flag_meanings']`/`flag_values` del file:
252=Unknown (include probabilmente nuvole/altre esclusioni non
altrimenti specificate), 253=Snow, 254=Water, 255=Missing/nodata
(diversi da quanto suggerito da fonti web generiche, che parlavano di
251=missing/252=cloud/253=snow/254=sea/255=background - non affidabile,
sostituito dal valore reale). Il campo `valid_range` del file conferma
comunque 0-250, coerente con `DN_MAX_VALID` sotto. Esclusi dal calcolo,
vedi `pct_valid_pixels` per sapere quanta area del comune era
effettivamente utilizzabile (basso per comuni con laghi o coperti da
nuvole/neve nel composito scelto).

Zonal stats via rasterstats invece dell'overlay vettoriale usato per CLC
(qui il dato sorgente e' un raster, non poligoni) - approssimazione nota:
a 300m di risoluzione, i comuni molto piccoli possono ricadere su pochi
pixel; `all_touched=True` include anche i pixel solo parzialmente coperti
dal confine comunale per mitigare (non eliminare) il problema.

Nota sulla dimensione del file (2026-07-17): a differenza di CLC (gia'
ritagliato dall'utente via "Download by area" su land.copernicus.eu),
questo prodotto NDVI non ha un ritaglio per area sul portale CDSE - il
file scaricato e' **globale** (un'unica griglia mondiale, ~3GB). Leggerlo
tutto in memoria (`src.read(1)`) richiederebbe decine di GB di RAM.
`compute_ndvi()` quindi legge solo una finestra (`rasterio.windows`)
corrispondente al bounding box dei comuni piemontesi (+ margine), non
l'intero file - la dimensione del download resta comunque quella (nessun
ritaglio lato server disponibile per questo prodotto), ma la lettura e il
calcolo restano leggeri.

Usage:
    python -m src.data_acquisition.process_ndvi --raster PATH --period 2026-07-01
"""

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds, transform as window_transform
from rasterstats import zonal_stats

from src.utils.database import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

DN_SCALE = 0.004
DN_OFFSET = -0.08
DN_MAX_VALID = 250  # DN 0-250 -> NDVI reale; 251-255 sono flag (vedi docstring)
BACKGROUND_FLAG = 255  # DN "background/nodata" - usato anche come fill oltre i bordi del raster
BBOX_BUFFER_DEG = 0.05  # ~5-6 km, margine attorno al bounding box dei comuni

# Bucket descrittivi da ndvi_mean, soglie da letteratura NDVI generica
# (non tarate su Piemonte specificamente - utili per lettura rapida in
# dashboard, il valore continuo ndvi_mean resta il dato primario per
# l'analisi statistica).
VEGETATION_BINS = [
    (-1.01, 0.1, 'no_vegetation'),
    (0.1, 0.3, 'sparse'),
    (0.3, 0.5, 'moderate'),
    (0.5, 0.7, 'dense'),
    (0.7, 1.01, 'very_dense'),
]


def classify(ndvi_mean: float) -> str:
    for lo, hi, label in VEGETATION_BINS:
        if lo <= ndvi_mean < hi:
            return label
    return 'no_vegetation'


def load_municipalities() -> gpd.GeoDataFrame:
    """Tutti i 1180 comuni, in EPSG:4326 (nessuna riproiezione: il raster CGLS e' gia' in 4326)."""
    query = "SELECT municipality_id, name, geometry FROM municipalities"
    return gpd.read_postgis(query, db_manager.engine, geom_col='geometry', crs='EPSG:4326')


def compute_ndvi(municipalities: gpd.GeoDataFrame, raster_path: Path) -> pd.DataFrame:
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        munis = municipalities
        if raster_crs is not None and str(raster_crs) != str(munis.crs):
            munis = munis.to_crs(raster_crs)

        minx, miny, maxx, maxy = munis.total_bounds
        window = from_bounds(
            minx - BBOX_BUFFER_DEG, miny - BBOX_BUFFER_DEG,
            maxx + BBOX_BUFFER_DEG, maxy + BBOX_BUFFER_DEG,
            transform=src.transform,
        )
        # boundless=True + fill_value=BACKGROUND_FLAG: il buffer puo'
        # sconfinare oltre i bordi del raster globale, boundless gestisce
        # il caso senza dover ritagliare manualmente la finestra.
        dn = src.read(1, window=window, boundless=True, fill_value=BACKGROUND_FLAG).astype('float32')
        affine = window_transform(window, src.transform)

    valid_mask = (dn >= 0) & (dn <= DN_MAX_VALID)
    ndvi = np.where(valid_mask, dn * DN_SCALE + DN_OFFSET, np.nan)

    ndvi_stats = zonal_stats(
        munis.geometry, ndvi, affine=affine, nodata=np.nan,
        stats=['mean', 'min', 'max', 'std', 'count'], all_touched=True,
    )
    # Secondo passaggio sul DN grezzo per calcolare pct_valid_pixels: nodata
    # fuori dal range 0-255 del dato originale (mai presente per davvero),
    # cosi' il conteggio include tutti i pixel intersecati, mascherati o no.
    total_stats = zonal_stats(
        munis.geometry, dn, affine=affine, nodata=-1,
        stats=['count'], all_touched=True,
    )

    rows = []
    for mid, name, ndvi_s, total_s in zip(
        munis['municipality_id'], munis['name'], ndvi_stats, total_stats
    ):
        total_px = total_s['count'] or 0
        valid_px = ndvi_s['count'] or 0
        mean = ndvi_s['mean']
        if mean is None or total_px == 0:
            logger.warning(f"{name}: nessun pixel del raster interseca il comune, skip")
            continue
        rows.append({
            'municipality_id': mid,
            'ndvi_mean': mean,
            'ndvi_min': ndvi_s['min'],
            'ndvi_max': ndvi_s['max'],
            'ndvi_stddev': ndvi_s['std'],
            'pct_valid_pixels': 100.0 * valid_px / total_px,
            'vegetation_class': classify(mean),
        })
    return pd.DataFrame(rows)


def save_results(df: pd.DataFrame, acquisition_period: str, source_product: str) -> None:
    for _, row in df.iterrows():
        db_manager.execute_update(
            """
            INSERT INTO municipality_ndvi
                (municipality_id, ndvi_mean, ndvi_min, ndvi_max, ndvi_stddev,
                 pct_valid_pixels, vegetation_class, acquisition_period, source_product)
            VALUES (:mid, :mean, :min, :max, :std, :pct_valid, :veg_class, :period, :source)
            ON CONFLICT (municipality_id) DO UPDATE SET
                ndvi_mean = EXCLUDED.ndvi_mean,
                ndvi_min = EXCLUDED.ndvi_min,
                ndvi_max = EXCLUDED.ndvi_max,
                ndvi_stddev = EXCLUDED.ndvi_stddev,
                pct_valid_pixels = EXCLUDED.pct_valid_pixels,
                vegetation_class = EXCLUDED.vegetation_class,
                acquisition_period = EXCLUDED.acquisition_period,
                source_product = EXCLUDED.source_product,
                computed_at = CURRENT_TIMESTAMP
            """,
            {
                'mid': int(row['municipality_id']),
                'mean': float(row['ndvi_mean']),
                'min': float(row['ndvi_min']) if pd.notna(row['ndvi_min']) else None,
                'max': float(row['ndvi_max']) if pd.notna(row['ndvi_max']) else None,
                'std': float(row['ndvi_stddev']) if pd.notna(row['ndvi_stddev']) else None,
                'pct_valid': float(row['pct_valid_pixels']),
                'veg_class': row['vegetation_class'],
                'period': acquisition_period,
                'source': source_product,
            },
        )


def main(raster_path: str, acquisition_period: str, source_product: str):
    logger.info("Carico comuni da PostGIS...")
    municipalities = load_municipalities()
    logger.info(f"  {len(municipalities)} comuni")

    logger.info(f"Carico raster NDVI da {raster_path}...")
    result = compute_ndvi(municipalities, Path(raster_path))

    logger.info("Salvo risultati nel DB...")
    save_results(result, acquisition_period, source_product)
    skipped = len(municipalities) - len(result)
    logger.info(f"NDVI calcolato per {len(result)}/{len(municipalities)} comuni.")
    if skipped:
        logger.warning(f"{skipped} comuni fuori dalla copertura del raster (nessun pixel intersecato).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--raster', required=True, help="Path al GeoTIFF NDVI (banda 1 = DN CGLS 0-255)")
    parser.add_argument('--period', required=True, help="Composito 10-giornaliero, es. 2026-07-01")
    parser.add_argument('--source', default='CGLS NDVI 300m V3')
    args = parser.parse_args()
    main(args.raster, args.period, args.source)
