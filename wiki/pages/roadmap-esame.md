# Pipeline del progetto d'esame

**Sorgenti**: requisiti del corso (`../../../../wiki/21-RAG-e-Framework-Agenti/07-progetto-finale.md`,
`../../../../wiki/00-Introduzione-Strumenti-AI-e-ML/04-verifica-e-progetto-finale.md`),
stato reale del codice (ottobre 2026), decisioni del docente riportate in
[Stato del progetto](project-status.md).

Questa pagina è la **sequenza di lavoro**: in che ordine si costruisce il
progetto d'esame, cosa dipende da cosa e quando una fase si può dire chiusa.
Il dettaglio operativo di ogni attività (file, istruzioni, verifica) è in
[To-do per agenti](todo-agenti.md); qui ci sono solo fasi, dipendenze e
"cancelli" di qualità.

## Obiettivo d'esame

Un'app Streamlit locale che integra **6 competenze su 6** richieste dal corso:

| # | Competenza | Dove vive nel progetto | Fase |
|---|---|---|---|
| 1 | Dati con pandas | ETL `src/data_processing/`, snapshot Parquet | già fatto |
| 2 | Visualizzazione | dashboard Plotly/Folium, QGIS | già fatto |
| 3 | ML supervisionato con scikit-learn | regressore temperatura (Linear/RandomForest/MLP) | F2 |
| 3b | ML non supervisionato | Pipeline K-Means + PCA (già presente, da consolidare) | F1–F2 |
| 4 | API LLM | `src/chatbot/llm_client.py` (Ollama, Claude opzionale) | F3 |
| 5 | Agente + almeno 2 tool | `src/chatbot/agent.py` + `tools.py` (6 tool) | F5–F6 |
| 6 | RAG | `src/chatbot/rag.py`: embedding Ollama + indice vettoriale numpy | F4 |

Bonus già presenti o previsti: test automatici, documentazione curata.

## Schema della pipeline (stato attuale)

<!-- PIPELINE:START -->
_Generato da `scripts/aggiorna_pipeline.py` il 2026-10-24 09:53: non modificare a mano, si aggiorna da solo quando cambia [To-do per agenti](todo-agenti.md)._

**Avanzamento:** 14/18 task obbligatori (77%) `████████░░`

Legenda: ✅ fatta · 🔄 in corso · ▶️ pronta da avviare · ⬜ in attesa · ⛔ bloccata

```text
✅ F0  Messa in sicurezza
 │
✅ F1  Base solida
 ├──────────────────────┬──────────────────────────┐
✅ F2  ML supervis.   ✅ F3  Client LLM         ✅ F9  Etica e limiti
 │                      ├─────────────┐
 │                   ✅ F4 RAG    ✅ F5 Tool dati
 │                      └──────┬──────┘
 │                          ✅ F6  Agente
 │                             │
 │                          ▶️ F7  Pagina chat
 │                             │
 │                          🔄 F8  Valutazione
 └──────────────┬──────────────┘
             ⬜ F10 Qualità
                │
             ⬜ F11 Consegna e demo
```

| Fase | Stato | Task |
|---|:---:|---|
| F0 Messa in sicurezza | ✅ | T0.1 ✅ · T0.2 ✅ |
| F1 Base solida | ✅ | T1.1 ✅ · T1.2 ✅ · T1.3 ✅ |
| F2 Machine Learning supervisionato (requisito 3) | ✅ | T2.1 ✅ · T2.2 ✅ · T2.3 ⬜ *(facolt.)* |
| F3 Client LLM | ✅ | T3.1 ✅ |
| F9 Etica, privacy e limiti | ✅ | T9.1 ✅ |
| F4 RAG sulla documentazione | ✅ | T4.1 ✅ · T4.2 ✅ |
| F5 Tool dati controllati | ✅ | T5.1 ✅ |
| F6 Agente | ✅ | T6.1 ✅ |
| F7 Pagina Streamlit "Assistente climatico" | ▶️ | T7.1 ⬜ |
| F8 Valutazione del chatbot | 🔄 | T8.1 ✅ · T8.2 ⬜ |
| F10 Qualità | ⬜ | T10.1 ⬜ · T10.2 ⬜ *(facolt.)* |
| F11 Consegna e demo | ⬜ | T11.1 ⬜ |

**Task pronti da avviare** (dipendenze tutte ✅, eseguibili in parallelo):

- T2.3 — (Facoltativo) Modello del bias Open-Meteo vs ARPA
- T7.1 — Pagina "Assistente climatico"
- T8.2 — Benchmark prompt v1 vs v2
- T10.2 — (Facoltativo) Pulizia dei documenti storici
<!-- PIPELINE:END -->

Le fasi sullo stesso livello sono **indipendenti** e possono essere
assegnate ad agenti diversi in parallelo (F2 ∥ F3 ∥ F9, poi F4 ∥ F5).

## Fasi e cancelli di qualità

Una fase è chiusa solo quando **tutti** i criteri del suo cancello sono
veri. Se un criterio non è verificabile, la fase resta aperta.

### F0 — Messa in sicurezza
- Lavoro ML attuale (oggi non tracciato) salvato in un commit.
- Branch `progetto-finale-its` creato.
- `.env.example` presente con i soli nomi delle variabili; `.env` non tracciato.

**Cancello:** `git status` pulito sul branch, `git ls-files .env` vuoto.

### F1 — Base solida
- Dashboard e chatbot leggono **solo** lo snapshot Parquet
  (`data/dashboard_export/`); PostgreSQL resta per ETL, analisi e training.
- La pagina ML non apre più connessioni al database.
- Un'unica implementazione del K-Means (la Pipeline in `src/machine_learning/`).
- `config.yaml` con una sezione `chatbot:` e `ml:`; dipendenze nuove in
  `requirements.txt`.

**Cancello:** `streamlit run dashboard/Home.py` funziona con PostgreSQL
spento; `pytest` verde.

### F2 — Machine Learning supervisionato (requisito 3)
- Regressione di `temp_mean_avg` dalle covariate territoriali con tre
  modelli a confronto in `Pipeline`: `LinearRegression` (baseline),
  `RandomForestRegressor` (con `GridSearchCV`), `MLPRegressor` (rete neurale,
  il ponte verso il deep learning).
- Valutazione con cross-validation (KFold e GroupKFold per provincia),
  metriche MAE, RMSE, R².
- Miglior modello salvato con `joblib` + metadati JSON.
- PCA a 2 componenti per visualizzare i cluster K-Means.
- Sezioni nuove nella pagina 09.

**Cancello:** script di training rieseguibile, metriche nei metadati,
pagina 09 mostra confronto modelli, importanza delle feature e PCA; test
nuovi verdi.

### F3 — Client LLM
- Wrapper unico `chiedi_llm(messaggi)` con provider Ollama (default) e
  Anthropic (opzionale, chiave solo da `.env`).
- Errori di rete/modello assente trasformati in messaggi comprensibili.
- Client finto (`FakeLLM`) per i test.

**Cancello:** test del client con mock verdi, nessuna chiamata di rete nei test.

### F4 — RAG sulla documentazione
- Knowledge base: `wiki/pages/*.md`, `paper/manoscritto.md`,
  `paper/references/README.md`, schede curate in `data/knowledge_base/`.
- Chunking per sezione Markdown (circa 300 parole, sovrapposizione 50).
- Embedding multilingue `bge-m3` calcolati da Ollama; indice vettoriale numpy
  persistente in `data/vector_store/` (ChromaDB è bloccato da Smart App Control).
- Funzione `cerca_documenti(domanda, k)` che restituisce testo + fonte.

**Cancello:** script `build_knowledge_base` rieseguibile; 5 domande di
controllo recuperano il chunk giusto tra i primi 3.

### F5 — Tool dati controllati
- Sei funzioni Python validate che leggono il Parquet (mai SQL dall'LLM).
- Ogni tool restituisce valori + unità + fonte + periodo, in JSON compatto.

**Cancello:** test per ogni tool, inclusi comune inesistente e anni fuori range.

### F6 — Agente
- Ciclo ragiona → tool → osserva (max 5 iterazioni, whitelist).
- Ruoli: Router → Analista dati / Ricercatore (RAG) → Revisore.
- Memoria a finestra scorrevole; system prompt versionati (v1, v2).

**Cancello:** con `FakeLLM` l'agente esegue un percorso a 2 tool e uno RAG;
domanda fuori ambito → rifiuto motivato.

### F7 — Pagina Streamlit "Assistente climatico"
- `dashboard/pages/10_assistente_climatico.py`, collegata dalla Home.
- Chat con `st.chat_message`, pannello "ragionamento" (tool usati, fonti RAG),
  selettore versione prompt, pulsante reset memoria, avviso AI.

**Cancello:** AppTest senza eccezioni; con Ollama spento la pagina mostra
un messaggio chiaro invece di un errore.

### F8 — Valutazione del chatbot
- `tests/chatbot/test_set.csv` con almeno 20 casi (fattuali, confronti,
  metodo, dati assenti, fuori ambito, prompt injection).
- Script di benchmark che confronta prompt v1 e v2 e salva i risultati.
- Sezione "Valutazione" nella pagina 10.

**Cancello:** file dei risultati presente, prompt vincente motivato,
errori residui elencati.

### F9 — Etica, privacy e limiti
- Pagina `dashboard/pages/11_etica_e_limiti.py` con i contenuti di
  [Etica e limiti](etica-e-limiti.md).
- Stessi punti riassunti nel README.

**Cancello:** pagina raggiungibile dalla Home, avviso AI visibile anche
nella pagina del chatbot.

### F10 — Qualità
- `pytest` interamente verde, `flake8` senza errori nei moduli nuovi.
- README con avvio locale passo-passo (DB, Ollama, knowledge base, Streamlit)
  e screenshot.

**Cancello:** una persona che segue solo il README avvia l'app.

### F11 — Consegna e demo
- Screenshot e breve video di backup della demo.
- Slide (10 minuti: problema, architettura, demo, sfide, conclusioni).
- Prova generale cronometrata con Ollama già avviato e modello già scaricato.

**Cancello:** demo completa entro 10 minuti, video di backup pronto.

## Regole che valgono per tutte le fasi

- Nessuna chiave API nel codice; tutto da `.env` via `src/utils/config.py`.
- Nessun test usa rete, Ollama o PostgreSQL: si usano mock e dati sintetici.
- Dopo ogni fase: aggiornare [Stato del progetto](project-status.md),
  [To-do per agenti](todo-agenti.md) e una riga in `wiki/log.md`.
- Durante la demo non si scaricano dati e non si riaddestrano modelli:
  tutto è preparato prima.
