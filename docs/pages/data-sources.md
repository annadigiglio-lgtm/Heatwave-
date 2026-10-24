# Fonti dati

**Sorgenti**: `src/data_acquisition/`, `config.yaml` (`data_sources`),
`data/dashboard_export/overview_stats.json`, `output/arpa_validation.csv`.

## Fonti usate

| Fonte | Cosa fornisce | Script | Copertura |
|---|---|---|---|
| Open-Meteo (archivio storico) | temperatura media/max/min e precipitazione giornaliere | `download_data.py`, `download_extra_municipalities.py`, `update_recent_data.py` | 599 comuni su 1180, 2000-01-01 → 2026-07-23, 5,8 milioni di righe |
| ARPA Piemonte (API open data) | misure di stazione: temperatura media/max/min | `download_arpa.py` | 218 comuni con stazione attiva, 2,07 milioni di righe |
| ISTAT | confini di comuni e province (2026), popolazione residente | `download_data.py`, `download_population.py` | 1180 comuni, 8 province |
| CORINE Land Cover 2018 | % di suolo urbano, agricolo, forestale… per comune | `process_land_cover.py` | 1180 comuni |
| Copernicus Global Land (NDVI) | indice di vegetazione medio | `process_ndvi.py` | 1180 comuni |
| Open-Meteo Elevation | quota del centroide | `fetch_elevation.py` | comuni con dati |

## Note tecniche utili all'orale

- **Open-Meteo** è una **rianalisi** (modello + osservazioni), non una
  misura diretta. Ha limiti di richieste al minuto e al giorno: i download
  sono stati fatti a lotti, con retry e backoff esponenziale sugli errori
  `429`, salvando i file in modo incrementale.
- **ARPA**: i filtri sulle date dell'API si chiamano `data_min`/`data_max`;
  i parametri con nomi "intuitivi" vengono ignorati senza errore. I comuni
  sono associati alle stazioni tramite codice ISTAT; dove ci sono più
  stazioni si sceglie quella con la quota più vicina a quella del comune.
- I comuni Open-Meteo sono stati scelti per coprire tutte le province e per
  includere tutti i comuni con stazione ARPA (validazione completa 218/218).

## Validazione Open-Meteo contro ARPA (temperatura massima)

| Metrica (media su 218 comuni) | Valore |
|---|---|
| Correlazione di Pearson | 0,968 |
| Bias medio (Open-Meteo − ARPA) | −1,52 °C |
| MAE | 2,50 °C |
| RMSE | 2,98 °C |

Open-Meteo segue bene la variabilità giornaliera ma **sottostima le
massime** di circa 1,5 °C. Il bias varia da +4,35 °C (Sampeyre) a −7,69 °C
(Cossogno) ed è correlato con la quota (r = −0,30, p < 0,001): in montagna
l'errore è maggiore. Il trend di riscaldamento si ritrova anche nei dati
ARPA. Dettagli in [Analisi statistica](statistical-analysis.md).
