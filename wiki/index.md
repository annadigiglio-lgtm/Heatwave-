# Indice — Wiki Heatwave Piemonte (versione d'esame)

Wiki operativa per il progetto finale ITS. Descrive lo stato **reale** del
codice: se qualcosa non coincide, prevalgono codice, `sql/` e `config.yaml`.
I documenti in `docs/`, `PROJECT_SUMMARY.md` e `SIMPLIFICATION_SUMMARY.md`
sono la pianificazione originale e non sono aggiornati.

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
- [Machine Learning](pages/machine-learning.md) — K-Means (fatto), regressione supervisionata e PCA (da fare)
- [Chatbot](pages/chatbot.md) — specifica di assistente con agenti, tool e RAG

## Applicazione e qualità

- [Dashboard e mappe](pages/dashboard.md) — pagine Streamlit, componenti, QGIS
- [Test](pages/testing.md) — suite attuale e test da aggiungere
- [Etica e limiti](pages/etica-e-limiti.md) — testi per la pagina 11, il README e le slide
- [Glossario](pages/concepts.md) — statistica, ML, LLM, RAG: definizioni per l'orale

## Fuori dalla wiki d'esame

- Piano dell'articolo scientifico: `paper/PIANO-ARTICOLO.md`
- Cronologia tecnica completa: [log.md](log.md) (da non usare come lista di cose da fare)
