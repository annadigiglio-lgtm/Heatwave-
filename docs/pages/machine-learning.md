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
| `LinearRegression`, `RandomForestRegressor` | 16-07, 17-02, 17-08 | ✅ |
| `GridSearchCV`, `cross_validate` / KFold / GroupKFold | 16-09, 17-10 | ✅ |
| MAE / RMSE / R², `permutation_importance` | 16-08 | ✅ |
| Rete neurale (`MLPRegressor`) | 18-03, 18-04 | ✅ |
| Deep learning pre-addestrato (embedding `bge-m3`) | 18-04, 21-02 | ✅ client (T3.1), RAG in corso (T4.1) |

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

**Uso nell'app**: la pagina 09 legge le feature da `spatial_analysis.parquet`
(`queries.get_ml_features()`) e applica il modello salvato, senza database.
`src/analysis/spatial_analysis.py::climate_clustering()` è un wrapper sulla
stessa Pipeline (`build_pipeline` + `label_mapping`) e serve per un fit nuovo
su altri dati, per esempio i comuni ARPA.

## 2. Regressione della temperatura (implementata, T2.1)

**Domanda**: quanto le caratteristiche del territorio spiegano la
temperatura media di un comune, e quale modello lo fa meglio?

- **Dati**: 599 comuni, 0 esclusi, solo parquet (`build_dataset()` unisce
  `spatial_analysis`, `municipality_metadata_all`, `land_cover_with_population`, `ndvi_all`).
- **Target**: `temp_mean_avg`. **Feature** (set `territorio`): `elevation_m`,
  `population_density`, `pct_urban`, `pct_forest_seminatural`, `ndvi_mean`;
  variante `territorio_coordinate` con `lat`, `lon`.
- **Modelli**, tutti in `Pipeline(StandardScaler → modello)`: `LinearRegression`,
  `RandomForestRegressor` in `GridSearchCV` (griglia 2×2×2, KFold(3) interno),
  `MLPRegressor(32, 16, early_stopping=True)`.
- **Validazione**: `cross_validate` con KFold(5) e GroupKFold per provincia.

| Modello (set `territorio`) | CV | MAE °C | RMSE °C | R² |
|---|---|---:|---:|---:|
| LinearRegression | KFold | 0,369 | 0,510 | 0,972 |
| LinearRegression | GroupKFold | 0,448 | 0,607 | 0,875 |
| **RandomForest** | KFold | 0,357 | 0,527 | 0,970 |
| **RandomForest** | **GroupKFold** | **0,434** | **0,594** | **0,889** |
| MLP | KFold | 0,500 | 0,764 | 0,926 |
| MLP | GroupKFold | 0,663 | 1,249 | 0,670 |

Con le coordinate tutti migliorano tranne l'MLP; la migliore diventa la
lineare (RMSE 0,402 con GroupKFold), l'MLP crolla (R² 0,15).

- **Modello salvato**: RandomForest (`max_depth=10`, `min_samples_leaf=5`,
  `n_estimators=200`) in `models/temperature_regressor.joblib` + metadati JSON
  con tutte le metriche. Residui fuori campione (`cross_val_predict` +
  GroupKFold) in `data/dashboard_export/temperature_regression_residuals.parquet`:
  media circa 0, deviazione standard 0,65 °C, intervallo da −2,7 a +2,5 °C.
- **Importanza per permutazione** (calo di R²): elevazione 2,035; tutte le
  altre circa 0,004. Coerente con la regressione spaziale, dove l'elevazione
  è l'unico predittore stabile.
- **Lettura per l'orale**:
  - KFold casuale è ottimista; lasciare fuori un'intera provincia è più difficile.
  - Il RandomForest batte la lineare solo di poco: la relazione è quasi lineare
    (gradiente termico verticale).
  - L'MLP non aggiunge nulla ed è instabile: con circa 600 righe tabellari il
    deep learning non è giustificato (lezione 18-04).
- **Riaddestramento**: `python -m src.machine_learning.train_temperature_model`
  (circa 6,5 minuti su questo PC, senza database).
- **Note metodologiche** (nei metadati): la GridSearch interna usa KFold(3)
  e non GroupKFold; l'importanza è calcolata sui dati di addestramento.

## Limiti

- Le feature del clustering sono correlate tra loro e descrivono lo stesso regime termico.
- `k=3` supera `k=2` di circa 0,002 nel silhouette score.
- I modelli descrivono il periodo osservato e non fanno previsioni.
- Open-Meteo è una rianalisi e differisce dalle misure ARPA (vedi [Fonti dati](data-sources.md)).
