# Test

**Sorgenti**: `tests/`, `tests/conftest.py`, `pytest.ini`.

```bash
python -m pytest tests -q
python -m pytest tests --cov=src --cov-report=term-missing
```

Regola: i test non usano rete, Ollama, Gemini né PostgreSQL. Si lavora con
DataFrame sintetici, cartelle temporanee (`tmp_path`), LLM finti (`FakeLLM`)
e mock degli SDK. `tests/conftest.py` disattiva per tutta la suite la cache
su disco delle risposte del chatbot.

## Suite attuale — 237 test (2026-10-24)

| File | Test | Cosa verifica |
|---|---:|---|
| `test_data_cleaning.py` | 15 | `DataCleaner`: duplicati, valori mancanti, range, outlier IQR, flag di qualità, pipeline completa |
| `test_analysis.py` | 12 | funzioni pure: Mann-Kendall, regressione, haversine, pesi spaziali, Moran's I, K-Means (equivalenza con la Pipeline), ondate |
| `test_config.py` | 5 | `Config.get()`, precedenza delle variabili d'ambiente su `config.yaml` |
| `test_machine_learning.py` | 5 | Pipeline K-Means, silhouette, ordine dei cluster, `joblib`, feature mancanti |
| `test_temperature_regression.py` | 9 | merge e densità, NaN esclusi, 3 Pipeline, KFold/GroupKFold, residui, `joblib` |
| `test_pages_smoke.py` | 2 | AppTest della pagina 10 (con `FakeLLM`) e della Home |
| `chatbot/test_llm_client.py` | 44 | Ollama (timeout, server spento, modello mancante), Gemini (ruoli, streaming, quota giornaliera, errori), Anthropic, riserva automatica, `FakeLLM`, `stato_llm` |
| `chatbot/test_tools.py` | 17 | 6 tool, comune inesistente con suggerimenti, anni non validi, output JSON, whitelist |
| `chatbot/test_rag.py` | 21 | chunking, indice numpy salva/carica, retrieval, esclusioni del corpus, controllo sull'indice reale (saltato se manca) |
| `chatbot/test_agent.py` | 83 | router, parser TOOL/PARAMS, ciclo dell'agente, `max_iterations`, rifiuti e injection, memoria, Revisore, streaming, pre-selezione del tool, system prompt comune, avviso di riserva |
| `chatbot/test_cache_risposte.py` | 9 | cache delle risposte: hit/miss, chiave, invalidazione, rifiuti non salvati |
| `chatbot/test_test_set.py` | 10 | formato e coerenza di `test_set.csv` |
| `chatbot/test_benchmark.py` | 5 | criteri del benchmark (numeri, tool alternativi, rifiuti, riepilogo) |

Un bug reale trovato grazie ai test: `detect_outliers` declassava righe
già "non valide" a "sospette" (vedi [ETL](etl-pipeline.md)).

## Benchmark del chatbot (non è un test pytest)

`python -m tests.chatbot.benchmark [--provider ollama|gemini] [--prompt v1 v2]`
interroga il modello reale sulle 28 domande di `tests/chatbot/test_set.csv`
senza cache, calcola criteri oggettivi per categoria e salva i risultati in
`data/benchmark/`, mostrati nella tab Valutazione della pagina 10. Dettagli in
[Chatbot](chatbot.md) e [To-do](todo-agenti.md) (T8.2).

## Non coperto (scelta esplicita)

Download di rete, caricamento in PostgreSQL e STL completa: richiederebbero
servizi esterni o tempi lunghi. Sono verificati eseguendo gli script.
