# Modello dati

**Sorgenti**: `sql/01_init_database.sql`, `sql/02_common_queries.sql`,
`sql/03_land_cover.sql`, `sql/04_ndvi.sql`, `sql/05_arpa_temperature.sql`,
`data/dashboard_export/`.

## PostgreSQL + PostGIS (storage primario)

| Tabella | Colonne principali | Note |
|---|---|---|
| `provinces` | `province_id`, `name`, `istat_code`, `geometry`, `population` | 8 province, indice GIST sulla geometria |
| `municipalities` | `municipality_id`, `province_id`, `name`, `istat_code`, `geometry`, `elevation_m`, `population` | 1180 comuni |
| `temperature` | `municipality_id`, `province_id`, `date`, `temp_mean`, `temp_max`, `temp_min`, `precipitation`, `data_source`, `quality_flag` | serie giornaliera Open-Meteo, indici su (comune, data) |
| `arpa_temperature` | `municipality_id`, `station_code`, `station_name`, `date`, `temp_mean`, `temp_max`, `temp_min` | misure di stazione ARPA |
| `heatwave_events` | `municipality_id`, `start_date`, `end_date`, `duration_days`, `max_temp`, `mean_temp`, `intensity_index`, `heat_threshold` | 2192 ondate (≥ 3 giorni sopra 35 °C) |
| `municipality_land_cover` | `pct_urban`, `pct_agricultural`, `pct_forest_seminatural`, `pct_wetland`, `pct_water`, `dominant_class` | CORINE 2018 |
| `municipality_ndvi` | `ndvi_mean`, `ndvi_min`, `ndvi_max`, `ndvi_stddev`, `vegetation_class` | Copernicus |
| `kpi`, `metadata` | tabelle di servizio | `kpi` non è popolata da codice Python: i KPI vengono dalle viste |

**Viste materializzate**: `kpi_annual_by_municipality` e
`kpi_annual_by_province` — per anno: giorni osservati, temperatura media,
massima e minima, giorni sopra 30/35/40 °C (`COUNT(*) FILTER (WHERE …)`),
deviazione standard della massima.

**Funzione**: `identify_heatwaves(p_heat_threshold = 35.0, p_min_duration = 3)`
scorre la serie di ogni comune e restituisce le sequenze di almeno
`p_min_duration` giorni con `temp_max` sopra soglia, con
`intensity_index = (max_temp − soglia) × durata`.

**Query pronte** (`sql/02_common_queries.sql`): temperatura e giorni
estremi per provincia e anno; confronto tra i decenni 2000–09, 2010–19 e
2020–26; classifica delle province per incremento.

## KPI del progetto

| KPI | Definizione |
|---|---|
| Temperatura media annua | `AVG(temp_mean)` per anno |
| Giorni sopra 30/35/40 °C | conteggio dei giorni con `temp_max` sopra soglia |
| Trend | °C per decennio (regressione) + significatività (Mann-Kendall) |
| Numero, durata e intensità delle ondate di calore | da `heatwave_events` |
| Bias Open-Meteo − ARPA | media delle differenze giornaliere di `temp_max` |

L'anomalia rispetto al periodo 1961–1990 non è calcolata: i dati partono
dal 2000.

## Snapshot Parquet (`data/dashboard_export/`) — fonte dell'app

| File | Righe | Contenuto |
|---|---:|---|
| `temperature_daily_all` | 5,8 M | serie giornaliera Open-Meteo per comune |
| `arpa_temperature_daily_all` | 2,07 M | serie giornaliera ARPA |
| `kpi_annual` / `kpi_annual_by_province` | 16 173 / 216 | KPI annuali |
| `trend_analysis` | 599 | Mann-Kendall, pendenza Sen, regressione °C/decennio |
| `heatwave_events` / `heatwave_stats_by_municipality` / `heatwave_frequency_by_year` | 2192 / 333 / 26 | ondate di calore |
| `spatial_analysis` | 599 | centroide, feature climatiche, `climate_cluster` |
| `morans_i_summary` | 1 | Moran's I e p-value |
| `seasonal_decomposition_all` | grande | componenti STL |
| `arpa_validation`, `arpa_trend_comparison`, `arpa_hot_day_bias`, `arpa_event_comparison_summary` | 218 / 218 / 3 / 1 | confronto con ARPA |
| `municipality_metadata_all` | 1180 | provincia, quota, lat, lon |
| `land_cover_all`, `land_cover_with_population`, `ndvi_all` | 1180 / 599 / 1180 | covariate territoriali |
| `all_municipality_geometries`, `province_geometries` | 1180 / 8 | geometrie WKT |
| `overview_stats.json` | — | conteggi per la Home |

Sono questi i file che leggeranno anche i tool del chatbot ([Chatbot](chatbot.md)).
