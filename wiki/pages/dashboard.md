# Dashboard Streamlit e mappe

**Sorgenti**: `dashboard/`, `.streamlit/config.toml`,
`dashboard/components/queries.py`, `qgis_projects/`.

## Avvio

```bash
streamlit run dashboard/Home.py
```

L'app non apre connessioni al database: legge `data/dashboard_export/`
(Parquet) e `models/`.
Dopo un aggiornamento dei dati: `python -m src.data_processing.refresh_dashboard`.

## Pagine

| File | Contenuto | Stato |
|---|---|---|
| `Home.py` | presentazione, numeri chiave, card di navigazione | ✅ |
| `02_analisi_temporale.py` | trend, anomalie, stagionalità, boxplot per quinquennio, STL | ✅ |
| `03_analisi_spaziale.py` | mappe per provincia e comune, fasce di quota, cluster, Moran's I | ✅ |
| `04_ondate_di_calore.py` | frequenza, intensità, mappa, calendario | ✅ |
| `05_contesto_territoriale.py` | uso del suolo, popolazione, NDVI rispetto alla temperatura | ✅ |
| `06_sintesi_della_ricerca.py` | sintesi divulgativa con citazioni | ✅ |
| `07_download_dati.py` | export CSV | ✅ |
| `08_citazioni_e_fonti.py` | bibliografia e fonti dati | ✅ |
| `09_machine_learning.py` | tab Clustering (silhouette, cluster, mappa, PCA 2D: PC1 85%, PC2 14%), Regressione (metriche 3 modelli × KFold/GroupKFold, importanza feature, predetto vs osservato, mappa residui), Limiti | ✅ senza DB |
| `10_assistente_climatico.py` | chatbot con agenti e RAG | ⬜ T7.1 |
| `11_etica_e_limiti.py` | cosa è / non è, limiti di dati e modelli, privacy del chatbot, AI Act e GDPR | ✅ |

Percorso consigliato per la demo:
problema (Home) → dati (02–05) → ML (09) → assistente (10) → etica (11).

## Componenti condivisi (`dashboard/components/`)

| File | Ruolo |
|---|---|
| `queries.py` | tutte le letture dei dati (Parquet), con `@st.cache_data` |
| `data_source.py` | selettore Open-Meteo / ARPA / Confronto riusato dalle pagine |
| `filters.py` | filtri per anni e provincia dentro ogni pagina |
| `charts.py`, `styling.py`, `constants.py` | tema Plotly, CSS, palette e costanti |
| `maps.py` | conversione WKT → GeoJSON per Folium |
| `heatwave_definitions.py` | definizione alternativa a percentile e rilevamento eventi in Python |

## Mappe QGIS

`qgis_projects/build_maps.py` (PyQGIS, eseguito con l'interprete di QGIS)
genera tre progetti: `temperature_heatmap.qgz` (temperatura media dei 599
comuni), `hotspot_analysis.qgz` (cluster K-Means) e
`evolution_animation.qgz` (animazione 2000 → oggi). I comuni senza dati
restano grigi, così la copertura reale è visibile.

## Verifica senza browser

```python
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("dashboard/pages/09_machine_learning.py").run(timeout=60)
assert not at.exception
```
