# Test

**Sorgenti**: `tests/`, `pytest.ini`.

```bash
python -m pytest tests -q
python -m pytest tests --cov=src --cov-report=term-missing
```

Regola: i test non usano rete, Ollama né PostgreSQL. Si lavora con
DataFrame sintetici, cartelle temporanee (`tmp_path`) e LLM finti (`FakeLLM`).

## Suite attuale — 37 test

| File | Test | Cosa verifica |
|---|---:|---|
| `test_data_cleaning.py` | 15 | `DataCleaner`: duplicati, valori mancanti, range, outlier IQR, flag di qualità, pipeline completa |
| `test_analysis.py` | 12 | funzioni pure: Mann-Kendall, regressione, haversine, pesi spaziali, Moran's I, K-Means, aggregazioni delle ondate |
| `test_config.py` | 5 | `Config.get()`, precedenza delle variabili d'ambiente su `config.yaml` |
| `test_machine_learning.py` | 5 | Pipeline K-Means, silhouette, ordine dei cluster, salvataggio e caricamento `joblib`, feature mancanti |

Un bug reale trovato grazie ai test: `detect_outliers` declassava righe
già "non valide" a "sospette" (vedi [ETL](etl-pipeline.md)).

## Da aggiungere

| File | Task | Contenuto |
|---|---|---|
| `test_temperature_regression.py` | T2.1 | dataset, CV, salvataggio del regressore |
| `tests/chatbot/test_llm_client.py` | T3.1 | mock di `ollama.chat`, errori del provider |
| `tests/chatbot/test_rag.py` | T4.1 | chunking, indicizzazione con client effimero, retrieval |
| `tests/chatbot/test_tools.py` | T5.1 | 6 tool, comune inesistente, anni non validi, output JSON |
| `tests/chatbot/test_agent.py` | T6.1 | ciclo agente con `FakeLLM`, whitelist, `max_iterations`, rifiuti, memoria |
| `test_pages_smoke.py` | T10.1 | AppTest delle pagine 09, 10, 11 e Home |

`tests/chatbot/test_set.csv` e `benchmark.py` (T8.x) **non** sono test
pytest: valutano il chatbot con Ollama reale.

## Non coperto (scelta esplicita)

Download di rete, caricamento in PostgreSQL e STL completa: richiederebbero
servizi esterni o tempi lunghi. Sono verificati eseguendo gli script.
