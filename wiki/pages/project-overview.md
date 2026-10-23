# Panoramica del progetto

**Sorgenti**: `README.md`, `src/`, `dashboard/`, requisiti del corso.

**Heatwave Piemonte** analizza temperature e ondate di calore nei comuni
piemontesi dal 2000 a oggi e le rende consultabili tramite una dashboard
Streamlit e un assistente AI che risponde sui dati e sui metodi.

È il progetto finale del corso ITS "Data Manager for Business Intelligence
Software Developer" (traccia **E — progetto libero**, approvato dal docente).

## Problema e utenti

- **Problema**: i dati sul caldo estremo sono dispersi tra fonti diverse
  (modelli di rianalisi, stazioni ARPA, dati territoriali) e difficili da
  leggere per chi non è un esperto.
- **Per chi**: studenti, amministrazioni locali, giornalisti e cittadini
  curiosi che vogliono capire come è cambiato il caldo nel loro comune.
- **Valore**: un unico posto con dati puliti, analisi motivate e un
  assistente che spiega i risultati citando le fonti.

## Domande di ricerca

1. Le giornate con temperature estreme sono aumentate nel tempo?
2. Quali comuni e province mostrano i cambiamenti maggiori?
3. Esistono pattern geografici significativi?
4. Quali fattori territoriali spiegano le differenze tra comuni?
5. Si possono raggruppare territori climaticamente simili con il Machine Learning?

## Componenti

| Componente | Tecnologie |
|---|---|
| ETL | Python, pandas, requests, Open-Meteo, ARPA, ISTAT, CORINE, NDVI |
| Storage | PostgreSQL + PostGIS; snapshot Parquet per l'app |
| Analisi | scipy, pymannkendall, statsmodels (STL, OLS), libpysal/spreg |
| Machine Learning | scikit-learn (K-Means, regressori), joblib |
| Assistente AI | Ollama, ChromaDB, sentence-transformers, agente con tool |
| Interfaccia | Streamlit, Plotly, Folium; QGIS per le mappe statiche |
| Qualità | pytest, logging con loguru, configurazione con YAML + `.env` |

Architettura in [Architettura](architecture.md), stato in
[Stato del progetto](project-status.md).
