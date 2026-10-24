"""
fetch_elevation.py - Popola municipalities.elevation_m per i comuni con dati reali.

`elevation_m` esiste nello schema (`sql/01_init_database.sql`) ma non era mai
stato popolato (NULL per tutti i 1180 comuni) - vedi docs/pages/project-status.md.
Usato dalla pagina "Analisi Spaziale" della dashboard per il confronto per
fascia altitudinale (pianura/collina/montagna).

Fonte: Open-Meteo Elevation API (stessa fonte gratuita, senza API key, gia'
usata per le temperature) - https://open-meteo.com/en/docs/elevation-api.
Le coordinate usate sono il centroide della geometria di ciascun comune
(gia' presente nel DB), non le coordinate hardcoded del download originale.

Usage:
    python -m src.data_acquisition.fetch_elevation
"""

import requests

from src.utils.database import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
# L'endpoint rifiuta con 400 oltre 100 coordinate per richiesta ("Parameter
# 'latitude' and 'longitude' must not exceed 100 coordinates") - scoperto il
# 2026-07-18 quando i comuni con temperatura hanno superato quota 100.
MAX_COORDS_PER_REQUEST = 100


def get_municipalities_with_data() -> list:
    """
    Comuni con dati di temperatura reali (Open-Meteo *o* ARPA), con
    centroide della geometria. Estesa il 2026-07-18 per includere anche i
    167 comuni solo-ARPA (prima restava solo su Open-Meteo, lasciando
    `elevation_m` NULL per loro e rompendo il confronto per fascia
    altitudinale in modalità "Solo ARPA" della dashboard).
    """
    query = """
        SELECT DISTINCT m.municipality_id, m.name,
               ST_Y(ST_Centroid(m.geometry)) AS lat,
               ST_X(ST_Centroid(m.geometry)) AS lon
        FROM municipalities m
        WHERE m.municipality_id IN (SELECT DISTINCT municipality_id FROM temperature)
           OR m.municipality_id IN (SELECT DISTINCT municipality_id FROM arpa_temperature)
        ORDER BY m.municipality_id
    """
    rows = db_manager.execute_query(query)
    return [{'municipality_id': r[0], 'name': r[1], 'lat': r[2], 'lon': r[3]} for r in rows]


def fetch_elevations(points: list) -> list:
    """
    Interroga la Elevation API a lotti di al massimo
    `MAX_COORDS_PER_REQUEST` coordinate (lat/lon separate da virgola in
    un'unica richiesta per lotto, come documentato per l'endpoint).
    """
    elevations = []
    for i in range(0, len(points), MAX_COORDS_PER_REQUEST):
        chunk = points[i:i + MAX_COORDS_PER_REQUEST]
        params = {
            'latitude': ','.join(str(p['lat']) for p in chunk),
            'longitude': ','.join(str(p['lon']) for p in chunk),
        }
        response = requests.get(ELEVATION_URL, params=params, timeout=30)
        response.raise_for_status()
        elevations.extend(response.json()['elevation'])
    return elevations


def update_elevations(points: list, elevations: list) -> None:
    for point, elevation in zip(points, elevations):
        db_manager.execute_update(
            "UPDATE municipalities SET elevation_m = :elevation, "
            "updated_at = CURRENT_TIMESTAMP WHERE municipality_id = :id",
            {'elevation': int(round(elevation)), 'id': point['municipality_id']},
        )


def main():
    points = get_municipalities_with_data()
    logger.info(f"Recupero elevazione per {len(points)} comuni...")

    elevations = fetch_elevations(points)
    update_elevations(points, elevations)

    logger.info("✓ Elevazione aggiornata:")
    for point, elevation in zip(points, elevations):
        logger.info(f"  {point['name']}: {elevation:.0f} m")


if __name__ == "__main__":
    main()
