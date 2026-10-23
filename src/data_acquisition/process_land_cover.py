"""
process_land_cover.py - Calcola % uso del suolo (CORINE Land Cover) per comune.

Popola `municipality_land_cover` (vedi sql/03_land_cover.sql), covariata
esplicativa mancante per il paper scientifico - vedi
paper/PIANO-ARTICOLO.md.

Fonte: CORINE Land Cover 2018 vettoriale (Copernicus Land Monitoring
Service), scaricato manualmente dall'utente via "Download by area" (decisione
2026-07-16 di non usare l'API CLMS con token JWT: dataset aggiornato ogni
~6 anni, non serve automazione). File GeoPackage, EPSG:3035 (proiezione
equal-area usata da CLC, mantenuta per calcoli di area corretti - stessa
lezione gia' imparata per municipalities.area_km2, vedi data-sources.md),
52.794 poligoni, campo `Code_18` = codice CLC a 3 cifre.

Metodo: overlay geopandas tra le geometrie comunali (reproiettate in
EPSG:3035 per l'occasione) e i poligoni CLC. Le percentuali sono aggregate
alle 5 categorie di Livello 1 CLC (primo carattere del codice a 3 cifre):
1=Artificiale, 2=Agricolo, 3=Forestale/seminaturale, 4=Zone umide,
5=Corpi idrici. I codici speciali (990/995/999 - non classificato/nodata,
vedi data/external/clc_legend.csv) finiscono in "other".

Scomposizione di "Artificiale/urbano" (2026-07-16): un unico pct_urban
confonde superfici con proprieta' termiche molto diverse (residenziale,
industriale, verde urbano...) - rilevante per l'ipotesi originale del paper
su citta'/industria come fattori esplicativi. Sotto-classi (sommano a
pct_urban, salvo arrotondamento):
- residential: 111 (continuous urban fabric), 112 (discontinuous urban fabric)
- industrial_commercial: 121 (industrial or commercial units)
- transport: 122 (road/rail), 123 (port areas), 124 (airports)
- urban_green: 141 (green urban areas), 142 (sport and leisure facilities)
- extraction_construction: 131 (mineral extraction), 132 (dump sites),
  133 (construction sites) - suolo nudo di origine antropica, non verde
  ne' propriamente edificato

Usage:
    python -m src.data_acquisition.process_land_cover [--gpkg PATH]
"""

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd

from src.utils.database import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

CLC_CRS = "EPSG:3035"

LEVEL1_LABELS = {
    '1': 'urban',
    '2': 'agricultural',
    '3': 'forest_seminatural',
    '4': 'wetland',
    '5': 'water',
}
ALL_CATEGORIES = list(LEVEL1_LABELS.values()) + ['other']

# Sotto-classi del solo Livello 1 "urbano" (vedi docstring del modulo).
URBAN_SUBCLASS = {
    '111': 'residential', '112': 'residential',
    '121': 'industrial_commercial',
    '122': 'transport', '123': 'transport', '124': 'transport',
    '131': 'extraction_construction', '132': 'extraction_construction', '133': 'extraction_construction',
    '141': 'urban_green', '142': 'urban_green',
}
ALL_URBAN_SUBCLASSES = ['residential', 'industrial_commercial', 'transport', 'urban_green', 'extraction_construction']


def load_municipalities() -> gpd.GeoDataFrame:
    """Tutti i 1180 comuni, riproiettati in EPSG:3035 (equal-area, come CLC)."""
    query = "SELECT municipality_id, name, geometry FROM municipalities"
    gdf = gpd.read_postgis(query, db_manager.engine, geom_col='geometry', crs='EPSG:4326')
    return gdf.to_crs(CLC_CRS)


def load_clc(path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    codes = gdf['Code_18'].astype(str)
    gdf['level1'] = codes.str[0].map(LEVEL1_LABELS).fillna('other')
    gdf['urban_subclass'] = codes.map(URBAN_SUBCLASS).fillna('n/a')
    return gdf[['level1', 'urban_subclass', 'geometry']]


def compute_land_cover(municipalities: gpd.GeoDataFrame, clc: gpd.GeoDataFrame) -> pd.DataFrame:
    """Overlay + aggregazione: % area per categoria di Livello 1 (e sotto-classi urbane) per comune."""
    overlay = gpd.overlay(municipalities[['municipality_id', 'geometry']], clc, how='intersection')
    overlay['area_m2'] = overlay.geometry.area

    by_class = overlay.groupby(['municipality_id', 'level1'])['area_m2'].sum().unstack(fill_value=0.0)
    by_class = by_class.reindex(columns=ALL_CATEGORIES, fill_value=0.0)

    urban_rows = overlay[overlay['level1'] == 'urban']
    by_subclass = urban_rows.groupby(['municipality_id', 'urban_subclass'])['area_m2'].sum().unstack(fill_value=0.0)
    by_subclass = by_subclass.reindex(columns=ALL_URBAN_SUBCLASSES, fill_value=0.0)

    # reindex(fill_value=...) riempie solo le righe assenti dall'indice, non
    # i NaN prodotti dall'allineamento di .div() quando un comune non ha
    # nessuna riga in overlay/urban_rows (bug trovato testando: comuni con
    # pct_urban=0 avevano le sotto-classi urbane a NaN invece che 0) - serve
    # fillna esplicito dopo la divisione.
    total_area = municipalities.set_index('municipality_id').geometry.area
    pct = by_class.div(total_area, axis=0) * 100
    pct = pct.reindex(total_area.index, fill_value=0.0).fillna(0.0)

    pct_subclass = by_subclass.div(total_area, axis=0) * 100
    pct_subclass = pct_subclass.reindex(total_area.index, fill_value=0.0).fillna(0.0)

    result = pct.join(pct_subclass).reset_index()
    result['dominant_class'] = pct.idxmax(axis=1).values
    return result


def save_results(df: pd.DataFrame, year: int) -> None:
    for _, row in df.iterrows():
        db_manager.execute_update(
            """
            INSERT INTO municipality_land_cover
                (municipality_id, pct_urban, pct_agricultural, pct_forest_seminatural,
                 pct_wetland, pct_water, pct_other, dominant_class, source_year,
                 pct_residential, pct_industrial_commercial, pct_transport,
                 pct_urban_green, pct_extraction_construction)
            VALUES (:mid, :urban, :agri, :forest, :wetland, :water, :other, :dominant, :year,
                    :residential, :industrial, :transport, :urban_green, :extraction)
            ON CONFLICT (municipality_id) DO UPDATE SET
                pct_urban = EXCLUDED.pct_urban,
                pct_agricultural = EXCLUDED.pct_agricultural,
                pct_forest_seminatural = EXCLUDED.pct_forest_seminatural,
                pct_wetland = EXCLUDED.pct_wetland,
                pct_water = EXCLUDED.pct_water,
                pct_other = EXCLUDED.pct_other,
                dominant_class = EXCLUDED.dominant_class,
                source_year = EXCLUDED.source_year,
                pct_residential = EXCLUDED.pct_residential,
                pct_industrial_commercial = EXCLUDED.pct_industrial_commercial,
                pct_transport = EXCLUDED.pct_transport,
                pct_urban_green = EXCLUDED.pct_urban_green,
                pct_extraction_construction = EXCLUDED.pct_extraction_construction,
                computed_at = CURRENT_TIMESTAMP
            """,
            {
                'mid': int(row['municipality_id']),
                'urban': float(row['urban']),
                'agri': float(row['agricultural']),
                'forest': float(row['forest_seminatural']),
                'wetland': float(row['wetland']),
                'water': float(row['water']),
                'other': float(row['other']),
                'dominant': row['dominant_class'],
                'year': year,
                'residential': float(row['residential']),
                'industrial': float(row['industrial_commercial']),
                'transport': float(row['transport']),
                'urban_green': float(row['urban_green']),
                'extraction': float(row['extraction_construction']),
            },
        )


def main(gpkg_path: str, year: int = 2018):
    logger.info("Carico comuni da PostGIS...")
    municipalities = load_municipalities()
    logger.info(f"  {len(municipalities)} comuni")

    logger.info(f"Carico CORINE Land Cover da {gpkg_path}...")
    clc = load_clc(Path(gpkg_path))
    logger.info(f"  {len(clc)} poligoni CLC")

    logger.info("Calcolo overlay geopandas (puo' richiedere qualche minuto)...")
    result = compute_land_cover(municipalities, clc)

    logger.info("Salvo risultati nel DB...")
    save_results(result, year)
    logger.info(f"Uso del suolo calcolato per {len(result)} comuni.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpkg', default='U2018_CLC2018_V2020_20u1.gpkg')
    parser.add_argument('--year', type=int, default=2018)
    args = parser.parse_args()
    main(args.gpkg, args.year)
