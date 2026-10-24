"""
refresh_dashboard.py - Rilancia le analisi e rigenera lo snapshot della
dashboard, in un solo comando.

Concatena i passi che gia' si lanciavano a mano dopo un aggiornamento dati
(vedi docs/pages/dashboard.md, sezione "Nessuna connessione DB live"):

    1. src/analysis/trend_analysis.py
    2. src/analysis/heatwave_stats.py
    3. src/analysis/seasonal_analysis.py
    4. src/analysis/spatial_analysis.py
    5. src/analysis/spatial_regression.py
    6. src/analysis/validate_arpa.py
    7. src/data_processing/export_dashboard_data.py

Deliberatamente ESCLUSO da questo script: TRUNCATE/identify_heatwaves() e
REFRESH MATERIALIZED VIEW sul database. Sono operazioni che modificano il
DB (la prima e' distruttiva) e finora sono sempre state lanciate a mano,
valutando caso per caso - vanno eseguite PRIMA di questo script, quando i
dati nel DB sono gia' pronti. Questo script legge soltanto.

Ogni passo viene eseguito anche se uno precedente fallisce (es. ARPA vuota
non deve bloccare il refresh delle analisi Open-Meteo) - il riepilogo finale
elenca cosa e' andato a buon fine e cosa no; l'exit code e' diverso da zero
se almeno un passo e' fallito.

Uso:
    python -m src.data_processing.refresh_dashboard
"""

import sys
import time

from src.utils.logger import get_logger

logger = get_logger(__name__)

STEPS = [
    ('trend_analysis', 'src.analysis.trend_analysis'),
    ('heatwave_stats', 'src.analysis.heatwave_stats'),
    ('seasonal_analysis', 'src.analysis.seasonal_analysis'),
    ('spatial_analysis', 'src.analysis.spatial_analysis'),
    ('spatial_regression', 'src.analysis.spatial_regression'),
    ('validate_arpa', 'src.analysis.validate_arpa'),
    ('export_dashboard_data', 'src.data_processing.export_dashboard_data'),
]


def _run_step(label: str, module_name: str) -> bool:
    import importlib

    logger.info(f">>> {label}")
    start = time.monotonic()
    try:
        module = importlib.import_module(module_name)
        module.main()
        logger.info(f"✓ {label} completato in {time.monotonic() - start:.1f}s")
        return True
    except Exception:
        logger.exception(f"✗ {label} fallito dopo {time.monotonic() - start:.1f}s")
        return False


def main() -> int:
    logger.info("=" * 70)
    logger.info("REFRESH DASHBOARD: analisi + export (nessuna scrittura sul DB)")
    logger.info("=" * 70)

    results = {label: _run_step(label, module_name) for label, module_name in STEPS}

    logger.info("=" * 70)
    logger.info("RIEPILOGO")
    for label, ok in results.items():
        logger.info(f"  {'✓' if ok else '✗'} {label}")

    failed = [label for label, ok in results.items() if not ok]
    if failed:
        logger.error(f"Passi falliti: {', '.join(failed)} - vedi log sopra per il dettaglio")
        return 1

    logger.info("Tutti i passi completati - data/dashboard_export/ e' aggiornata")
    logger.info("Prossimo passo (manuale): git add/commit/push per pubblicare l'aggiornamento")
    return 0


if __name__ == '__main__':
    sys.exit(main())
