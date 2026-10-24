# To-do per agenti

**Sorgenti**: [Pipeline d'esame](roadmap-esame.md), [Chatbot](chatbot.md),
[Machine Learning](machine-learning.md), [Etica e limiti](etica-e-limiti.md).

Lista operativa per eseguire il progetto d'esame con agenti (Claude Code e
subagenti). Ogni task contiene tutto quello che serve per lavorarci da solo.
Stati: ⬜ da fare · 🔄 in corso · ✅ fatto · ⛔ bloccato.

## Regole per ogni agente

1. Prima di iniziare: leggere `CLAUDE.md`, questa pagina e le pagine wiki
   indicate nel task. Verificare che le dipendenze del task siano ✅.
2. Lavorare solo sui file elencati nel task. Se serve toccarne altri,
   dichiararlo nel resoconto.
3. Seguire lo stile del codice esistente: docstring in italiano, type hint,
   `get_logger(__name__)`, configurazione da `config.yaml` con `config.get(...)`.
4. Nessuna chiave nel codice. Nessun test che usa rete, Ollama o PostgreSQL.
5. Chiudere il task solo se il comando di **verifica** passa. Riportare
   l'output reale; se qualcosa fallisce, stato ⛔ con il motivo.
6. A fine task: stato aggiornato qui, una riga in `wiki/log.md`, e le pagine
   wiki toccate dal cambiamento aggiornate. Lo schema della pipeline in
   [roadmap-esame.md](roadmap-esame.md) si rigenera da solo (hook di Claude
   Code) quando questa pagina viene modificata con Edit/Write; se la modifichi
   in altro modo, lancia `python scripts/aggiorna_pipeline.py`.
7. Niente commit o push senza richiesta esplicita dell'utente.

## Ondate di lavoro (cosa si può fare in parallelo)

| Ondata | Task | Parallelo? |
|---|---|---|
| 1 | T0.1 → T0.2 | in sequenza, a mano con l'utente |
| 2 | T1.1, T1.2, T1.3 | sì, 3 agenti |
| 3 | T2.1, T3.1, T9.1 | sì, 3 agenti |
| 4 | T2.2, T4.1, T5.1 | sì, 3 agenti |
| 5 | T4.2, T6.1 | T6.1 dopo T4.1 e T5.1 |
| 6 | T7.1 | 1 agente |
| 7 | T8.1 → T8.2 | in sequenza |
| 8 | T10.1, T11.1 | sì |

---

## F0 — Messa in sicurezza

### T0.1 ✅ Commit del lavoro ML e nuovo repository
- **Fatto il 2026-10-23:** lavoro ML e wiki in due commit su `main`, push su
  https://github.com/annadigiglio-lgtm/Heatwave-.git (remote `origin`; il
  vecchio repository resta come `origine-vecchia`). Si lavora direttamente
  su `main` del nuovo repository, senza branch separato.
- `CLAUDE.md` è escluso da `.gitignore` per scelta dell'utente: le regole per
  gli agenti esistono solo nella copia locale.

### T0.2 ✅ Template delle variabili d'ambiente
- **Dipende da:** —
- **File:** `.env.example` (nuovo)
- **Fare:** stessi nomi di `.env` (DB_*, CDS_*, OSM_USER_AGENT, LOG_LEVEL,
  STREAMLIT_SERVER_PORT) più `ANTHROPIC_API_KEY=` e `OLLAMA_HOST=`, tutti
  con valori segnaposto. Controllare che `.gitignore` escluda `.env` ma non
  `.env.example`.
- **Verifica:** `git check-ignore .env.example` non stampa nulla.

## F1 — Base solida

### T1.1 ✅ Pagina ML senza database
- **Dipende da:** T0.1 · **Wiki:** [Machine Learning](machine-learning.md), [Dashboard](dashboard.md)
- **File:** `dashboard/components/queries.py`, `dashboard/pages/09_machine_learning.py`
- **Fare:** aggiungere a `queries.py` una funzione `get_ml_features()` che
  legge `spatial_analysis.parquet` (contiene già `municipality_name, lon,
  lat, temp_mean_avg, days_gt_30c_avg, days_gt_35c_avg`). Nella pagina 09
  sostituire `load_municipality_features()` (query PostgreSQL) con questa
  funzione.
- **Accettazione:** con PostgreSQL spento la pagina 09 si apre; i cluster
  predetti coincidono con la colonna `climate_cluster` del parquet.
- **Verifica:** `python -m pytest tests -q` e un test AppTest della pagina
  (vedi T10.1) senza eccezioni.
- **Esito (2026-10-23):** `get_ml_features()` in `queries.py`; AppTest senza
  eccezioni con DB irraggiungibile; cluster coincidenti al 100% (599 comuni).

### T1.2 ✅ Un solo K-Means (DRY)
- **Dipende da:** T0.1
- **File:** `src/analysis/spatial_analysis.py`, `tests/test_analysis.py`
- **Fare:** `climate_clustering(df, k)` deve usare `build_pipeline(k)` e il
  riordino delle etichette di `src/machine_learning/climate_clustering.py`
  invece della standardizzazione fatta a mano. Firma e output invariati:
  la usano ancora `queries.get_arpa_spatial_clustering` e `qgis_projects/build_maps.py`.
- **Accettazione:** stesse etichette di prima sui dati di test; nessun
  `KMeans(` fuori da `src/machine_learning/`.
- **Verifica:** `python -m pytest tests -q`; `grep -rn "KMeans(" src dashboard`
  trova solo `src/machine_learning/climate_clustering.py`.
- **Esito (2026-10-23):** `climate_clustering()` delega a `build_pipeline` +
  `label_mapping` (reso pubblico); nuovo test di equivalenza; 100% di
  coincidenza sui 599 comuni.

### T1.3 ✅ Configurazione e dipendenze
- **Dipende da:** T0.1
- **File:** `config.yaml`, `requirements.txt`, `.gitignore`
- **Fare:** aggiungere la sezione `chatbot:` (vedi [Chatbot](chatbot.md)) e
  `ml:` (`random_seed: 42`, `cv_folds: 5`). Aggiungere a `requirements.txt`
  `ollama`, `anthropic` con versioni fissate (pubblicate da almeno due
  settimane). Aggiungere `data/vector_store/` al `.gitignore`.
- **Verifica:** `.venv\Scripts\python -c "import ollama, anthropic"`;
  `python -m pytest tests -q`.
- **Esito (2026-10-23):** sezioni `ml` e `chatbot` in `config.yaml`;
  `ollama==0.6.3`, `anthropic==1.12.1`. ChromaDB 1.5.9 e
  sentence-transformers 6.1.0 si installano, ma **Smart App Control** (attivo
  sul PC) blocca `orjson`, `torch` e `regex`. Decisione dell'utente: RAG con
  embedding Ollama (`bge-m3`) + indice numpy; pacchetti bloccati rimossi.

## F2 — Machine Learning supervisionato

### T2.1 ✅ Regressore della temperatura (Linear, RandomForest, MLP)
- **Dipende da:** T1.3 · **Corso:** lezioni 16 (pipeline, metriche, CV),
  17 (RandomForest, GridSearchCV, Pipeline), 18 (reti neurali), 19 (joblib)
- **File:** `src/machine_learning/temperature_regression.py`,
  `src/machine_learning/train_temperature_model.py`, `tests/test_temperature_regression.py`
- **Dati (solo parquet):** `spatial_analysis` (target `temp_mean_avg`) unito
  per `municipality_name` con `municipality_metadata_all` (`elevation_m`,
  `lat`, `lon`, `province_name`), `land_cover_with_population` (`population`,
  `area_km2` → `population_density`, `pct_urban`, `pct_forest_seminatural`) e
  `ndvi_all` (`ndvi_mean`). Circa 599 righe; le righe con NaN vanno escluse e contate.
- **Fare:**
  - funzione `build_dataset()`, poi tre `Pipeline` con `StandardScaler`:
    `LinearRegression`, `RandomForestRegressor` (`GridSearchCV` su
    `n_estimators`, `max_depth`, `min_samples_leaf`) e `MLPRegressor`
    (`hidden_layer_sizes` (32,16), `early_stopping=True`);
  - due set di feature: senza coordinate (principale) e con `lat`/`lon` (variante);
  - `cross_validate` con KFold(5, shuffle, seed) e `GroupKFold` per
    `province_name`; metriche MAE, RMSE, R² (media ± deviazione standard);
  - scegliere il miglior modello per RMSE con GroupKFold, riaddestrarlo su
    tutto il dataset, salvare `models/temperature_regressor.joblib` e
    `models/temperature_regressor_metadata.json` (feature, n righe, tabella
    metriche di tutti i modelli, parametri migliori, importanza delle
    feature con `permutation_importance`, data, seed);
  - salvare i residui in `data/dashboard_export/temperature_regression_residuals.parquet`.
- **Accettazione:** lo script gira senza database; i metadati contengono le
  metriche di tutti e tre i modelli; i test usano un dataset sintetico piccolo.
- **Verifica:** `python -m src.machine_learning.train_temperature_model`;
  `python -m pytest tests/test_temperature_regression.py -q`.

### T2.2 ✅ Pagina ML: sezioni supervisionato e PCA
- **Dipende da:** T1.1, T2.1 · **Corso:** lezione 18-02 (PCA)
- **File:** `dashboard/pages/09_machine_learning.py`, `src/machine_learning/__init__.py`
- **Fare:** organizzare la pagina in `st.tabs` — "Clustering" (contenuto
  attuale + scatter PCA a 2 componenti colorato per cluster, con varianza
  spiegata), "Regressione" (tabella metriche dei 3 modelli con KFold vs
  GroupKFold, barre di importanza delle feature, scatter predetto vs
  osservato, mappa dei residui), "Limiti". Si leggono solo i file in
  `models/` e `data/dashboard_export/`: nessun training nella pagina.
- **Verifica:** AppTest della pagina senza eccezioni.

### T2.3 ⬜ (Facoltativo) Modello del bias Open-Meteo vs ARPA
- **Dipende da:** T2.1
- **Fare:** stessa struttura di T2.1 con target `temp_max_bias` da
  `arpa_validation.parquet` (218 comuni) e feature territoriali. Mostra
  *dove* Open-Meteo sbaglia di più. Solo se avanza tempo.

## F3 — Client LLM

### T3.1 ✅ `llm_client.py` + FakeLLM
- **Dipende da:** T1.3 · **Corso:** lezione 13 (wrapper universale, sicurezza delle chiavi)
- **File:** `src/chatbot/__init__.py`, `src/chatbot/llm_client.py`, `tests/chatbot/test_llm_client.py`
- **Fare:** come descritto in [Chatbot §1](chatbot.md).
  Funzione `stato_llm() -> (ok: bool, messaggio: str)` per la sidebar.
- **Verifica:** `python -m pytest tests/chatbot/test_llm_client.py -q`
  (mock di `ollama.chat`, nessuna rete).

## F4 — RAG

### T4.1 ✅ Knowledge base e indice vettoriale
- **Dipende da:** T1.3, T3.1, Ollama installato con `ollama pull bge-m3` (solo per
  il build reale, non per i test) · **Corso:** lezione 21-02, 21-03, 21-04; 19 (`cosine_similarity`)
- **File:** `src/chatbot/rag.py`, `src/chatbot/build_knowledge_base.py`,
  `tests/chatbot/test_rag.py`
- **Fare:** [Chatbot §3](chatbot.md).
  Chunking e `IndiceVettoriale` sono testabili senza Ollama: nei test si
  passa una embedding function finta e deterministica e si usa `tmp_path`
  per salvare e ricaricare l'indice.
- **Verifica:** `python -m src.chatbot.build_knowledge_base` stampa il numero
  di chunk per fonte; `python -m pytest tests/chatbot/test_rag.py -q`.

### T4.2 ✅ Schede curate per la knowledge base
- **Dipende da:** T4.1
- **File:** `data/knowledge_base/metodologia.md`, `faq.md`, `glossario.md`, `limiti.md`
- **Fare:** testi brevi e divulgativi, una sezione `##` per argomento,
  presi da [Analisi statistica](statistical-analysis.md), [Glossario](concepts.md),
  [Etica e limiti](etica-e-limiti.md). Niente numeri che non siano già nella wiki.
- **Verifica:** 5 domande di controllo (scritte nel test) restituiscono la
  scheda giusta tra i primi 3 risultati con l'indice reale.

## F5 — Tool dati

### T5.1 ✅ Sei tool controllati
- **Dipende da:** T1.1 · **Corso:** lezione 20-02, 20-03, 20-04 (sicurezza)
- **File:** `src/chatbot/tools.py`, `tests/chatbot/test_tools.py`
- **Fare:** [Chatbot §2](chatbot.md). Lettura dei
  parquet con cache (`functools.lru_cache`, non `st.cache_data`: il modulo
  non deve dipendere da Streamlit). Il percorso della cartella dati è un
  parametro, così i test passano una cartella temporanea con parquet sintetici.
- **Accettazione:** comune inesistente → errore con suggerimenti
  (`difflib.get_close_matches`); anno fuori 2000–2026 → errore; output
  sempre serializzabile in JSON.
- **Verifica:** `python -m pytest tests/chatbot/test_tools.py -q`.
- **Esito (2026-10-23):** 6 tool + `TOOLS`, `TOOL_DESCRIPTIONS`,
  `descrivi_tool_per_prompt()`, `esegui_tool()` (whitelist, parametri
  sconosciuti/mancanti → `{"errore": ...}`); 17 test. Sui dati reali:
  "Biela" → suggerisce Biella; comuni senza Open-Meteo dichiarati; 2026
  trattato come anno parziale (204 giorni). Punto aperto: il trend di
  `trend_analysis.parquet` include il 2026 parziale (vedi nota nel tool).

## F6 — Agente

### T6.1 ✅ Agente multi-ruolo, memoria, prompt
- **Dipende da:** T3.1, T4.1, T5.1 · **Corso:** lezioni 15, 20-03, 21-03, 21-05
- **File:** `src/chatbot/agent.py`, `src/chatbot/memory.py`,
  `src/chatbot/prompts.py`, `tests/chatbot/test_agent.py`
- **Fare:** [Chatbot §4–6](chatbot.md).
- **Accettazione (con FakeLLM):** (a) domanda dati → 2 chiamate tool →
  risposta; (b) domanda di metodo → nessun tool, almeno una fonte; (c) tool
  inesistente → osservazione di errore, nessun crash; (d) 6 richieste di tool
  di fila → stop a `max_iterations`; (e) domanda fuori ambito → rifiuto
  senza chiamare l'LLM; (f) la memoria tronca la storia a `memory_window`.
- **Verifica:** `python -m pytest tests/chatbot/test_agent.py -q`.
- **Stato (2026-10-24):** codice e 55 test pronti (`agent.py`, `prompts.py`,
  `memory.py`). Il primo subagente si è bloccato nella prova reale: il client
  non aveva timeout e ogni ruolo aveva un system prompt diverso (2 minuti di
  lettura a ogni cambio su CPU). Corretto dal coordinatore: timeout di 180 s,
  system prompt unico per tutti i ruoli, `riscalda_modello()`, contesto RAG
  ridotto, risposte massimo 70 parole, `num_predict: 200`.
- **Prova reale (2026-10-24, qwen2.5:7b su CPU, prompt v2):** 6/6 corrette.
  Alessandria (dati) 82 s, Cuneo contro Novara (dati) 181 s, Open-Meteo/ARPA (metodo)
  130 s, Biella (misto) 190 s; previsione e injection rifiutate in 0 s senza LLM.
  Riscaldamento: 6 s con la cache, 88 s dopo una modifica del prompt.

## F7 — Interfaccia

### T7.1 ✅ Pagina "Assistente climatico"
- **Dipende da:** T6.1 · **Corso:** lezioni 13-06…08, 14-05 (streaming), 14-07
- **File:** `dashboard/pages/10_assistente_climatico.py`, `dashboard/Home.py`
- **Fare:** [Chatbot §7](chatbot.md),
  più un link dalla Home (`st.page_link`) con la stessa grafica delle altre card.
- **Verifica:** AppTest con `FakeLLM` iniettato (via `st.session_state` o
  variabile d'ambiente `HEATWAVE_FAKE_LLM=1`) senza eccezioni; prova
  manuale con Ollama acceso sulle 5 domande d'esempio.

## F8 — Valutazione

### T8.1 ✅ Test set
- **Dipende da:** T5.1 · **File:** `tests/chatbot/test_set.csv`
- **Fare:** 20+ righe come in [Chatbot §8](chatbot.md).
  Le risposte attese si ricavano chiamando direttamente i tool.

### T8.2 ⬜ Benchmark prompt v1 vs v2
- **Dipende da:** T6.1, T8.1 · **Corso:** lezione 12
- **File:** `tests/chatbot/benchmark.py`, `output/chatbot_benchmark.csv`,
  tab "Valutazione" in pagina 10
- **Fare:** eseguire con Ollama reale (non è un test pytest); salvare
  metriche per prompt; scrivere nella wiki il prompt vincente e gli errori residui.
- **Regole di confronto (dal lavoro di T8.1):** cercare i `valori_chiave`
  come numeri interi (non sottostringhe: `0`, `1`, `2` darebbero falsi
  positivi) e normalizzare la virgola decimale italiana (`0,45` = `0.45`);
  per D01/D03 (`deve_rifiutare = si` con tool atteso) la chiamata al tool che
  restituisce errore è il comportamento corretto; per C01 sono accettabili
  anche due `get_heatwave_summary` al posto di `compare_locations`.
  Tempo stimato su CPU: 28 domande × 2 prompt × circa 20–40 s.
- **Verifica:** il CSV esiste e la tab lo mostra.

## F9 — Etica

### T9.1 ✅ Pagina "Etica e limiti"
- **Dipende da:** T0.1 · **Corso:** lezione 10
- **File:** `dashboard/pages/11_etica_e_limiti.py`, `dashboard/Home.py`
- **Fare:** trasformare [Etica e limiti](etica-e-limiti.md) in pagina,
  con lo stile di `components/styling.py`; link dalla Home.
- **Verifica:** AppTest senza eccezioni.
- **Esito (2026-10-23):** pagina con sezioni "è / non è", 4 card di limiti
  (conteggi letti da `queries.get_overview_stats()`), tab Dati / ML / Chatbot /
  AI Act e GDPR, avviso del chatbot in evidenza; link dalla Home sotto il
  blocco Machine Learning. AppTest pagina 11 e Home senza eccezioni.
  Da ricontrollare: le formulazioni su AI Act/GDPR vengono dalla lezione 10,
  non dalla wiki di progetto.

## F10 — Qualità

### T10.1 ⬜ Test, lint, README
- **Dipende da:** T7.1, T9.1
- **File:** `tests/test_pages_smoke.py`, `README.md`
- **Attenzione (scoperto in T9.1):** una pagina che contiene `st.page_link`
  verso pagine sorelle fallisce in AppTest se eseguita da sola
  (`KeyError: 'url_pathname'`): testare dalla Home con `at.switch_page(...)`
  oppure evitare `page_link` nelle pagine figlie (03 e 05 li usano).
- **Fare:** smoke test AppTest per le pagine 09, 10, 11 (e Home); `flake8
  src/chatbot src/machine_learning`; README: prerequisiti (Python 3.11+,
  PostgreSQL facoltativo per la demo, Ollama + `ollama pull qwen2.5:7b`),
  avvio in 4 comandi, knowledge base, screenshot in `docs/screenshots/`,
  tabella delle 6 competenze. Togliere dal README il link al deploy
  pubblico se non viene aggiornato.
- **Verifica:** `python -m pytest -q` tutto verde; `flake8` senza errori.

### T10.2 ⬜ (Facoltativo) Pulizia dei documenti storici
- **Fare:** spostare `PROJECT_SUMMARY.md`, `SIMPLIFICATION_SUMMARY.md` e
  `docs/*.md` in `docs/archivio/` con una nota "pianificazione originale,
  non aggiornata". Solo su conferma dell'utente.

## F11 — Consegna

### T11.1 ⬜ Demo e presentazione
- **Dipende da:** T10.1
- **Fare:** screenshot delle pagine 09, 10, 11; video di backup di 2 minuti;
  scaletta slide (problema → architettura → demo → sfide → conclusioni);
  lista di risposte alle domande probabili (perché Ollama/qwen, cosa succede
  se l'LLM non risponde, come il RAG gestisce documenti lunghi, perché non
  serve il deep learning sui dati tabellari).
- **Verifica:** prova generale cronometrata sotto i 10 minuti.
