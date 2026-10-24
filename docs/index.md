# Documentazione — Heatwave Piemonte (versione d'esame)

Questa cartella `docs/` è la documentazione del progetto, mantenuta come wiki
(si apre anche con Obsidian). Descrive lo stato **reale** del codice: se
qualcosa non coincide, prevalgono codice, `sql/` e `config.yaml`.

Dal 2026-10-24 la wiki ha sostituito i vecchi documenti di pianificazione
(`docs/ARCHITECTURE.md`, `DATABASE.md`, `ETL.md`, `IMPLEMENTATION_GUIDE.md`,
`ROADMAP.md`, `PROJECT_SUMMARY.md`, `SIMPLIFICATION_SUMMARY.md`), che
descrivevano uno stato mai raggiunto e restano solo nella cronologia git.

## Da dove partire

1. [Stato del progetto](pages/project-status.md) — requisiti d'esame: cosa c'è e cosa manca
2. [Pipeline d'esame](pages/roadmap-esame.md) — fasi, dipendenze e cancelli di qualità
3. [To-do per agenti](pages/todo-agenti.md) — task eseguibili con file, criteri e verifica

## Progetto

- [Panoramica](pages/project-overview.md) — problema, utenti, domande di ricerca, tecnologie
- [Architettura](pages/architecture.md) — livelli dati → conoscenza → app, moduli del repository
- [Configurazione](pages/config-reference.md) — `config.yaml` e variabili d'ambiente

## Dati

- [Fonti dati](pages/data-sources.md) — Open-Meteo, ARPA, ISTAT, CORINE, NDVI; validazione ARPA
- [Pipeline ETL](pages/etl-pipeline.md) — extract, transform, load, refresh
- [Modello dati](pages/data-model.md) — tabelle PostGIS, KPI, snapshot Parquet

## Analisi, ML e AI

- [Analisi statistica](pages/statistical-analysis.md) — trend, STL, Moran's I, regressione spaziale, ARPA
- [Machine Learning](pages/machine-learning.md) — K-Means con PCA, regressione supervisionata (Linear, RandomForest, MLP) con KFold e GroupKFold
- [Chatbot](pages/chatbot.md) — agente multi-ruolo con 6 tool, RAG, memoria; Gemini con riserva Ollama, cache, benchmark

## Applicazione e qualità

- [Dashboard e mappe](pages/dashboard.md) — pagine Streamlit, componenti, QGIS
- [Test](pages/testing.md) — suite pytest (dati, analisi, ML, chatbot, pagine) e benchmark del chatbot
- [Etica e limiti](pages/etica-e-limiti.md) — testi per la pagina 11, il README e le slide
- [Glossario](pages/concepts.md) — statistica, ML, LLM, RAG: definizioni per l'orale

## Fuori dalla wiki d'esame

- Piano dell'articolo scientifico: `paper/PIANO-ARTICOLO.md`
- Cronologia tecnica completa: [log.md](log.md) (da non usare come lista di cose da fare)
