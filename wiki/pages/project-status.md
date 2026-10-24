# Stato del progetto

**Sorgenti**: codice del repository verificato il 2026-10-23.
Sequenza di lavoro in [Pipeline d'esame](roadmap-esame.md), attività in
[To-do per agenti](todo-agenti.md).

## Requisiti d'esame (6 competenze del corso)

| # | Competenza | Stato | Evidenza / cosa manca |
|---|---|---|---|
| 1 | Dati con pandas | ✅ | ETL, `DataCleaner`, snapshot Parquet |
| 2 | Visualizzazione | ✅ | 8 pagine Plotly/Folium, 3 progetti QGIS |
| 3 | ML classificazione/regressione (scikit-learn) | ✅ | regressore RandomForest vs Linear vs MLP, GroupKFold R² 0,889 (T2.1) |
| 4 | API LLM | ✅ | `src/chatbot/llm_client.py`: Ollama qwen2.5:7b + bge-m3, Anthropic opzionale (T3.1) |
| 5 | Agente con almeno 2 tool | ✅ | `src/chatbot/agent.py`: router, analista (6 tool), ricercatore (RAG), revisore; prova reale 6/6 (T6.1) |
| 6 | RAG | ✅ | `src/chatbot/rag.py`: embedding bge-m3 + indice numpy, 4 schede curate, cancello 6/6 (T4.1, T4.2) |
| — | Streamlit funzionante | ✅ | `dashboard/Home.py` + 8 pagine |
| — | README, requirements | ⚠️ | `.env.example` e dipendenze del chatbot presenti; il README cita ancora il deploy pubblico |
| — | Bonus: test automatici | ✅ | 37 test pytest |

## Già pronto

| Area | Evidenza |
|---|---|
| Dati | 5,8 milioni di righe giornaliere Open-Meteo (2000-01-01 → 2026-07-23), 599 comuni su 1180; 2,07 milioni di righe ARPA su 218 comuni |
| Database | PostgreSQL + PostGIS, schema in `sql/` |
| Analisi | trend (Mann-Kendall + regressione), STL, Moran's I, regressione spaziale, validazione ARPA |
| ML | Pipeline StandardScaler + K-Means, silhouette 0,539 (k=3), `joblib`, pagina 09 |
| App | dashboard multipagina che legge lo snapshot Parquet, senza database live |
| Test | 37 test (cleaning, config, analisi, ML) |

## Problemi noti nel codice esistente

Nessuno aperto: pagina 09 senza database (T1.1) e K-Means unico (T1.2)
risolti il 2026-10-23.

## Decisioni confermate

- PostgreSQL/PostGIS è autorizzato dal docente e resta lo storage primario.
- La demo è locale; il deploy pubblico non è richiesto.
- Repository d'esame: https://github.com/annadigiglio-lgtm/Heatwave- (pubblico).
- Le analisi scientifiche (Moran's I, ARPA, STL, QGIS) restano.
- L'app (dashboard e chatbot) legge solo Parquet e modelli salvati.
- LLM locale con Ollama; Anthropic come provider opzionale.
- Agente scritto a mano (schema della lezione 20), niente CrewAI/LangChain.
- RAG con embedding Ollama (`bge-m3`) e indice vettoriale numpy al posto di
  ChromaDB: Smart App Control di Windows blocca `orjson`, `torch` e `regex`.

## Prerequisiti ancora da preparare (azione dell'utente)

- Installare Ollama (https://ollama.com) e scaricare i modelli:
  `ollama pull qwen2.5:7b` e `ollama pull bge-m3`. Servono da T4.1 (build
  dell'indice) e da T6.1/T7.1 in poi per le prove reali; i test usano mock.

## Fuori dall'ambito d'esame

- Articolo scientifico (`paper/`): resta nel repository e fa parte della
  knowledge base del RAG, ma non è un deliverable d'esame.
- Ulteriore estensione della copertura dei comuni.
- Mappa composita "Heatwave Index".
- Docker e deploy pubblico.
