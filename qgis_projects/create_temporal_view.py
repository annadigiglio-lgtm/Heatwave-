"""
create_temporal_view.py - Vista Postgres per la mappa evolution_animation.qgz

Esegue con il venv del progetto (usa src.utils.database), non con il
Python di QGIS:

    python -m qgis_projects.create_temporal_view

Crea `kpi_temporal_view`: una riga per (comune, anno) con la geometria del
comune e la temperatura media annuale, più due colonne data (year_start,
year_end) usate da QGIS per il controllo temporale (animazione 2000-2025).

Una vista reale, non una subquery inline nel progetto QGIS: il provider
Postgres di QGIS tratta le subquery `(SELECT ...) AS alias` passate come
`table=` in QgsDataSourceUri come un identificatore letterale (le mette
tra virgolette per intero), non come SQL da eseguire — vedi
build_maps.py e docs/pages/dashboard.md per il dettaglio del bug.
"""

from sqlalchemy import text

from src.utils.database import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

CREATE_VIEW_SQL = """
CREATE OR REPLACE VIEW kpi_temporal_view AS
SELECT
    k.municipality_id * 100 + (k.year - 2000) AS feature_id,
    m.name,
    m.geometry,
    k.year,
    k.temp_mean_annual,
    k.days_gt_35c,
    make_date(k.year, 1, 1) AS year_start,
    make_date(k.year, 12, 31) AS year_end
FROM kpi_annual_by_municipality k
JOIN municipalities m ON k.municipality_id = m.municipality_id;
"""


def main():
    with db_manager.engine.begin() as conn:
        conn.execute(text(CREATE_VIEW_SQL))
    n_rows = db_manager.execute_query('SELECT COUNT(*) FROM kpi_temporal_view;')[0][0]
    logger.success(f"✓ kpi_temporal_view creata/aggiornata: {n_rows} righe")


if __name__ == '__main__':
    main()
