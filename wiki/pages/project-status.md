# Stato del progetto

**Sorgenti**: codice del repository verificato il 2026-10-23.
Sequenza di lavoro in [Pipeline d'esame](roadmap-esame.md), attività in
[To-do per agenti](todo-agenti.md).

## Requisiti d'esame (6 competenze del corso)

| # | Competenza | Stato | Evidenza / cosa manca |
|---|---|---|---|
| 1 | Dati con pandas | ✅ | ETL, `DataCleaner`, snapshot Parquet |
| 2 | Visualizzazione | ✅ | 8 pagine Plotly/Folium, 3 progetti QGIS |
| 3 | ML classificazione/regressione (scikit-learn) | ⚠️ | c'è solo K-Means (non supervisionato) → T2.1 |
| 4 | API LLM | ❌ | nessun codice → T3.1 |
| 5 | Agente con almeno 2 tool | ❌ | → T5.1, T6.1 |
| 6 | RAG | ❌ | → T4.1, T4.2 |
| — | Streamlit funzionante | ✅ | `dashboard/Home.py` + 8 pagine |
| — | README, requirements | ⚠️ | manca `.env.example`, il README cita il deploy pubblico |
| — | Bonus: test automatici | ✅ | 36 test pytest |

## Già pronto

| Area | Evidenza |
|---|---|
| Dati | 5,8 milioni di righe giornaliere Open-Meteo (2000-01-01 → 2026-07-23), 599 comuni su 1180; 2,07 milioni di righe ARPA su 218 comuni |
| Database | PostgreSQL + PostGIS, schema in `sql/` |
| Analisi | trend (Mann-Kendall + regressione), STL, Moran's I, regressione spaziale, validazione ARPA |
| ML | Pipeline StandardScaler + K-Means, silhouette 0,539 (k=3), `joblib`, pagina 09 |
| App | dashboard multipagina che legge lo snapshot Parquet, senza database live |
| Test | 36 test (cleaning, config, analisi, ML) |

## Problemi noti nel codice esistente

- La pagina 09 interroga PostgreSQL mentre il resto dell'app usa il Parquet → T1.1.
- K-Means implementato due volte → T1.2.

## Decisioni confermate

- PostgreSQL/PostGIS è autorizzato dal docente e resta lo storage primario.
- La demo è locale; il deploy pubblico non è richiesto.
- Repository d'esame: https://github.com/annadigiglio-lgtm/Heatwave- (pubblico).
- Le analisi scientifiche (Moran's I, ARPA, STL, QGIS) restano.
- L'app (dashboard e chatbot) legge solo Parquet e modelli salvati.
- LLM locale con Ollama; Anthropic come provider opzionale.
- Agente scritto a mano (schema della lezione 20), niente CrewAI/LangChain.

## Fuori dall'ambito d'esame

- Articolo scientifico (`paper/`): resta nel repository e fa parte della
  knowledge base del RAG, ma non è un deliverable d'esame.
- Ulteriore estensione della copertura dei comuni.
- Mappa composita "Heatwave Index".
- Docker e deploy pubblico.
