# Pipeline ETL

**Sorgenti**: `src/data_acquisition/`, `src/data_processing/`,
`src/database/load_to_db.py`, `sql/`.

```text
Extract  → src/data_acquisition/*        → data/raw/*.csv
Transform→ src/data_processing/clean_data.py (DataCleaner) → data/processed/*.csv
Load     → src/database/load_to_db.py (DatabaseLoader) → PostgreSQL/PostGIS
Analyze  → src/analysis/* + src/machine_learning/* → output/*.csv, models/*
Serve    → src/data_processing/refresh_dashboard.py → data/dashboard_export/*.parquet
```

## Extract

- `WeatherDataDownloader` (`download_data.py`): chiamate Open-Meteo per
  coordinate, retry con backoff esponenziale sui `429` (rispetta
  `Retry-After`, massimo 5 tentativi), pausa tra le richieste.
- `download_extra_municipalities.py`: scelta dei comuni da aggiungere con
  campionamento "farthest point" per provincia (copertura geografica
  uniforme) e salto dei comuni già scaricati.
- `download_arpa.py`: anagrafica stazioni → associazione ai comuni →
  download giornaliero con paginazione.
- Covariate: `download_population.py`, `process_land_cover.py` (CORINE con
  geopandas), `process_ndvi.py` (raster con rasterstats), `fetch_elevation.py`.

## Transform — `DataCleaner.clean_data()`

1. `load_data` — lettura del CSV.
2. `remove_duplicates` — su (data, località).
3. `handle_missing_values` — interpolazione lineare (massimo 2 giorni) di
   `temp_mean`, precipitazione mancante → 0, righe senza max/min eliminate.
4. `quality_flag = 0` per tutte le righe.
5. `validate_temperature` — fuori da [−50, 60] °C → flag 2;
   `temp_min > temp_max` → flag 1.
6. `detect_outliers` — metodo IQR (1,5×IQR) → flag 1, senza mai declassare
   un flag 2.
7. `convert_dtypes` — `float32`/`category` per risparmiare memoria.
8. `apply_quality_flags` — scarta le righe con flag ≥ 2.
9. `generate_report` — riepilogo nel log.

Due bug trovati e corretti (utili da raccontare come "sfide"):
- una colonna `quality_flag` creata implicitamente con `NaN` faceva
  scartare quasi tutte le righe (`NaN < 2` è falso);
- `detect_outliers` declassava a "sospette" righe già "non valide"
  (trovato grazie a un test di regressione).

## Load — `DatabaseLoader`

`initialize_schema` / `verify_schema`, poi `insert_municipalities`,
`insert_temperature`, `insert_temperature_for_municipalities` e
`insert_arpa_temperature`, con inserimenti a blocchi (`page_size` 5000).
Le viste materializzate KPI e la funzione SQL `identify_heatwaves()` sono
in [Modello dati](data-model.md).

## Analisi ed export — un solo comando

```bash
python -m src.data_processing.refresh_dashboard
```

Esegue in sequenza `trend_analysis`, `heatwave_stats`, `seasonal_analysis`,
`spatial_analysis`, `spatial_regression`, `validate_arpa`,
`export_dashboard_data`. Ogni passo è isolato: se uno fallisce, viene
registrato nel log e gli altri continuano. L'export scrive circa 20 file
Parquet in `data/dashboard_export/`, l'unica fonte dati dell'app.

Per l'esame si aggiungono, dopo l'export, il training dei modelli (T2.1)
e la costruzione della knowledge base (T4.1): vedi
[To-do per agenti](todo-agenti.md).
