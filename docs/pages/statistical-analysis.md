# Analisi statistica e spaziale

**Sorgenti**: `src/analysis/*.py`, `output/*.csv`,
`data/dashboard_export/*.parquet`. Risultati dell'ultima esecuzione
completa (`refresh_dashboard.py`, luglio 2026, 599 comuni Open-Meteo e 218 ARPA).

Queste analisi sono **statistica**, non Machine Learning: arricchiscono
l'interpretazione ma non sostituiscono il requisito ML (vedi
[Machine Learning](machine-learning.md)).

## Trend — `trend_analysis.py`

- **Mann-Kendall** (`pymannkendall`): dice *se* esiste un trend monotono,
  senza ipotesi di normalità. **Regressione lineare** (`scipy.stats.linregress`):
  dice *quanto*, in °C per decennio.
- **Risultato**: 556/599 comuni (92,8%) hanno un riscaldamento
  significativo (p < 0,05). Le pendenze vanno da −0,62 a +1,51 °C/decennio
  (massimo a Prarostino). Solo due comuni alpini si raffreddano in modo
  significativo: Briga Alta (−0,62) e Argentera (−0,40).

## Ondate di calore — `heatwave_stats.py`

- Definizione operativa: almeno 3 giorni consecutivi con `temp_max` > 35 °C;
  intensità = (massima − soglia) × durata.
- **Risultato**: 2192 ondate in 333 comuni; i comuni con più ondate sono
  Molino dei Torti e Castellazzo Bormida (17 ciascuno, in provincia di Alessandria).

## Stagionalità — `seasonal_analysis.py`

- **STL** (`statsmodels`, periodo 365, `robust=True`) separa trend,
  stagionalità e residuo della serie giornaliera.
- **Risultato**: componente di trend in aumento in 589/599 comuni (98,3%);
  ampiezza stagionale tra 27,4 e 36,4 °C.

## Autocorrelazione spaziale — `spatial_analysis.py`

- **Moran's I** con pesi inverso-distanza (haversine), normalizzati per
  riga, e test di permutazione (999 permutazioni).
- **Risultato**: I = 0,2115 (atteso sotto casualità −0,0015), p = 0,001:
  i comuni vicini hanno temperature simili più di quanto accadrebbe per caso.
- Lo stesso modulo contiene `climate_clustering()` (K-Means), da unificare
  con la Pipeline ML (T1.2).

## Regressione spaziale — `spatial_regression.py`

- **Fase 1, OLS** (statsmodels) di `temp_mean_avg` su elevazione, densità
  di popolazione, % urbano, NDVI, con VIF per la multicollinearità.
  R² = 0,973, ma Moran's I sui residui = 0,209 (p = 0,001): i residui non
  sono indipendenti, quindi l'OLS non basta per l'inferenza.
- **Fase 2, modello spaziale** (spreg, pesi KNN con k = 5): i test LM
  indicano un modello a **errore spaziale**; λ = 0,932.
- **Risultato stabile**: l'elevazione è l'unico predittore robusto
  (−0,0059 °C/m, cioè circa −0,6 °C ogni 100 m, p < 0,001). % urbano e NDVI
  hanno cambiato significatività e perfino segno tra le esecuzioni con
  campioni diversi (63 → 599 comuni): vanno presentati come risultati non
  ancora stabili.

## Validazione con ARPA — `validate_arpa.py`

| Confronto (temp_max) | Bias | r |
|---|---:|---:|
| Tutti i giorni | −1,47 °C | 0,948 |
| Giorni ARPA > 30 °C | −2,38 °C | 0,618 |
| Giorni ARPA > 35 °C | −2,64 °C | 0,375 |

- Sui giorni più caldi Open-Meteo sottostima di più ed è meno correlato.
- **Ondate di calore**: ARPA ne registra 1185, Open-Meteo 459. Precisione
  63,6% (ondate Open-Meteo confermate da ARPA), recall 25,2% (ondate reali
  catturate da Open-Meteo). Il numero di ondate da Open-Meteo è quindi una
  **stima per difetto**.
- **Trend**: segno concorde tra le due fonti in 202/218 comuni (92,7%).
  Il riscaldamento è confermato anche dalle stazioni.
