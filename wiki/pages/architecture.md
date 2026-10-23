# Architettura

**Sorgenti**: struttura del repository, `config.yaml`, `src/`, `dashboard/`,
`sql/`. Le parti marcate *(da fare)* sono descritte in
[Pipeline d'esame](roadmap-esame.md).

## Tre livelli

```text
1. PRODUZIONE DATI (offline, in locale)
   Open-Meteo · ARPA · ISTAT · CORINE · NDVI · popolazione
        │  src/data_acquisition/
        ▼
   pulizia pandas (src/data_processing/clean_data.py)
        │  src/database/load_to_db.py
        ▼
   PostgreSQL + PostGIS  ──►  src/analysis/*  (trend, STL, Moran's I, regressione, ARPA)
        │                     src/machine_learning/* (K-Means, regressore)  ──► models/*.joblib
        ▼
   src/data_processing/refresh_dashboard.py  ──►  data/dashboard_export/*.parquet

2. CONOSCENZA PER IL CHATBOT  (da fare)
   wiki/pages · paper/manoscritto.md · data/knowledge_base/
        │  src/chatbot/build_knowledge_base.py
        ▼
   indice vettoriale numpy  (data/vector_store/, embedding bge-m3 via Ollama)

3. APPLICAZIONE (Streamlit, nessuna connessione al database)
   dashboard/Home.py + pages/02…09   ◄── Parquet + models/
   pages/10_assistente_climatico.py  ◄── src/chatbot/  (da fare)
   pages/11_etica_e_limiti.py        (da fare)
```

**Decisione:** PostgreSQL/PostGIS è lo storage primario e serve a ETL,
analisi e training. L'app legge solo lo snapshot Parquet e i modelli
salvati: così la demo funziona anche con il database spento, ed è la stessa
fonte dati per dashboard e chatbot.

## Chatbot: componenti *(da fare)*

```text
domanda utente
   │
   ▼
memory.py  (finestra scorrevole su st.session_state)
   │
   ▼
agent.py ── Router ──┬── Analista dati ── tools.py ── Parquet / models
                     │
                     └── Ricercatore ──── rag.py ──── indice vettoriale
   │
   ▼
Revisore (controlla numeri e fonti)  ──►  risposta + fonti + traccia tool
   │
llm_client.py  (Ollama locale · Anthropic opzionale)
prompts.py     (system prompt v1 / v2)
```

Dettagli in [Chatbot](chatbot.md).

## Moduli del repository

| Cartella | Ruolo |
|---|---|
| `src/data_acquisition/` | download da API e file (Open-Meteo, ARPA, ISTAT, popolazione, CORINE, NDVI, elevazione) |
| `src/data_processing/` | `clean_data.py` (DataCleaner), `export_dashboard_data.py`, `refresh_dashboard.py` |
| `src/database/` | caricamento in PostgreSQL |
| `src/analysis/` | statistica temporale e spaziale, validazione ARPA |
| `src/machine_learning/` | Pipeline K-Means; regressore *(da fare)* |
| `src/chatbot/` | *(da fare)* client LLM, RAG, tool, agente, memoria, prompt |
| `src/utils/` | `config.py`, `database.py`, `logger.py` |
| `dashboard/` | app Streamlit multipagina, `components/` condivisi |
| `models/` | modelli `joblib` + metadati JSON |
| `data/dashboard_export/` | snapshot Parquet letto dall'app (tracciato in git) |
| `qgis_projects/` | tre progetti QGIS generati con PyQGIS |
| `sql/` | schema PostgreSQL/PostGIS |
| `tests/` | test pytest senza rete né database |

## Principi

- Separare dati, analisi, interfaccia e chiamate al modello.
- L'LLM non esegue mai SQL o codice: chiama solo funzioni Python in whitelist.
- Credenziali solo in `.env`, lette da `src/utils/config.py`.
- Distinguere sempre valori calcolati, risultati ML e testo generato.
- Database o LLM non disponibili → messaggio comprensibile, mai un traceback.
