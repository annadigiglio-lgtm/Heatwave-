# Machine Learning

**Sorgenti**: `src/machine_learning/`, `models/`,
`dashboard/pages/09_machine_learning.py`, `tests/test_machine_learning.py`.
Attività aperte: T1.1, T1.2, T2.1, T2.2 in [To-do per agenti](todo-agenti.md).

## Quadro rispetto al corso

| Tecnica | Lezione | Stato |
|---|---|---|
| `Pipeline` + `StandardScaler` | 16-06, 17-12 | ✅ usata |
| `KMeans` + `silhouette_score` | 18-01 | ✅ usata |
| `joblib` (persistenza) | 19-07 | ✅ usata |
| `PCA` | 18-02 | ⬜ T2.2 |
| `LinearRegression`, `RandomForestRegressor` | 16-07, 17-02, 17-08 | ⬜ T2.1 |
| `GridSearchCV`, `cross_validate` / KFold | 16-09, 17-10 | ⬜ T2.1 |
| MAE / RMSE / R² | 16-08 | ⬜ T2.1 |
| Rete neurale (`MLPRegressor`) | 18-03, 18-04 | ⬜ T2.1 |
| Deep learning pre-addestrato (embedding) | 18-04, 21-02 | ⬜ T4.1, nel RAG |

**Perché serve anche un modello supervisionato:** il requisito d'esame parla
di "un modello di classificazione o regressione con scikit-learn". Il
K-Means è non supervisionato e la regressione spaziale esistente usa
statsmodels/spreg, quindi da soli non lo soddisfano in modo esplicito.

## 1. Clustering climatico (implementato)

**Obiettivo**: raggruppare i comuni con regimi termici simili. È
un'analisi esplorativa, non una classificazione climatica ufficiale.

**Feature** (599 comuni Open-Meteo, media 2000–2025): `temp_mean_avg`,
`days_gt_30c_avg`, `days_gt_35c_avg`.

**Pipeline**: `StandardScaler → KMeans(n_init=10, random_state=42)`, con `k`
da 2 a 8 confrontato con il silhouette score.

| k | Silhouette |
|---:|---:|
| 2 | 0,5370 |
| **3** | **0,5389** |
| 4 | 0,5309 |
| 5 | 0,5195 |
| 6 | 0,5021 |
| 7 | 0,4712 |
| 8 | 0,4778 |

| Cluster | Comuni | Temp. media | Giorni >30 °C/anno | Giorni >35 °C/anno |
|---:|---:|---:|---:|---:|
| 0 — alpino, più fresco | 152 | 6,17 °C | 0,26 | 0,00 |
| 1 — intermedio | 249 | 11,90 °C | 12,40 | 0,47 |
| 2 — pianura calda | 198 | 13,16 °C | 32,23 | 2,54 |

Le etichette grezze del K-Means sono arbitrarie: i metadati salvano una
mappa che le riordina per temperatura media (0 = più fresco).

**Artefatti**: `models/climate_kmeans.joblib`,
`models/climate_kmeans_metadata.json`, `output/climate_kmeans_*.csv`.
Riaddestramento (richiede PostgreSQL): `python -m src.machine_learning.train_climate_model`.

**Da sistemare:**
- la pagina 09 legge le feature da PostgreSQL, mentre il resto dell'app usa
  il Parquet (T1.1);
- `src/analysis/spatial_analysis.py::climate_clustering` è una seconda
  implementazione fatta a mano dello stesso K-Means (T1.2).

## 2. Regressione della temperatura (da fare, T2.1)

**Domanda**: quanto le caratteristiche del territorio spiegano la
temperatura media di un comune, e quale modello lo fa meglio?

- **Target**: `temp_mean_avg`.
- **Feature**: `elevation_m`, `population_density`, `pct_urban`,
  `pct_forest_seminatural`, `ndvi_mean`; variante con `lat`, `lon`.
- **Modelli**: `LinearRegression` (baseline, confrontabile con l'OLS di
  statsmodels), `RandomForestRegressor` con `GridSearchCV`, `MLPRegressor`.
- **Validazione**: KFold(5) e GroupKFold per provincia. I comuni vicini si
  assomigliano (Moran's I = 0,21), quindi un KFold casuale tende a essere
  ottimista; la differenza tra le due validazioni è un risultato da mostrare.
- **Interpretazione**: `permutation_importance`; ci si aspetta l'elevazione
  dominante, coerente con la regressione spaziale (unico predittore stabile).

Il deep learning su ~600 righe tabellari non è giustificato: l'`MLPRegressor`
serve a mostrarlo con un confronto onesto (lezione 18-04, "quando usare il
deep learning"). Il deep learning entra davvero nel progetto con i modelli
pre-addestrati del chatbot (embedding del RAG e LLM).

## Limiti

- Le feature del clustering sono correlate tra loro e descrivono lo stesso regime termico.
- `k=3` supera `k=2` di circa 0,002 nel silhouette score.
- I modelli descrivono il periodo osservato e non fanno previsioni.
- Open-Meteo è una rianalisi e differisce dalle misure ARPA (vedi [Fonti dati](data-sources.md)).
