# Configurazione

**Sorgenti**: `config.yaml`, `src/utils/config.py`, `.env` (non versionato).

`config` è un singleton (`from src.utils.config import config`) con accesso
a punti: `config.get('processing.heatwave_duration_days')`. All'import
chiama `load_dotenv()`, e le variabili d'ambiente `DB_HOST`, `DB_PORT`,
`DB_USER`, `DB_PASSWORD` e `DB_NAME` hanno la precedenza sui valori di
`config.yaml`, che sono solo segnaposto.

| Sezione | Contenuto |
|---|---|
| `database` | connessione PostgreSQL (password solo da `.env`) |
| `data_sources` | URL e opzioni di Open-Meteo, Copernicus, ARPA, ISTAT, OSM |
| `paths` | `raw`, `processed`, `external`, `output`, `logs`, `dashboard_export` (relativi alla root) |
| `processing` | soglie 30/35/40 °C, durata minima dell'ondata (3 giorni), periodo 2000–2026, province |
| `logging` | livello e file (`logs/heatwave_piemonte.log`, loguru) |
| `visualization`, `dashboard` | palette, porta 8501, titolo |
| `ml` | `random_seed`, `cv_folds`, `models_dir` |
| `chatbot` | provider, modello, temperatura, `max_iterations`, memoria, versione del prompt, RAG — vedi [Chatbot](chatbot.md) |

## Variabili d'ambiente

| Variabile | Uso |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | PostgreSQL (solo ETL, analisi, training K-Means) |
| `CDS_URL`, `CDS_KEY` | Copernicus (facoltativo) |
| `OSM_USER_AGENT` | Nominatim |
| `LOG_LEVEL`, `STREAMLIT_SERVER_PORT` | servizio |
| `OLLAMA_HOST` | *(nuova)* indirizzo di Ollama, predefinito `http://localhost:11434` |
| `ANTHROPIC_API_KEY` | *(nuova, facoltativa)* solo con `chatbot.provider: anthropic` |
| `GOOGLE_API_KEY` | chiave gratuita da aistudio.google.com per `chatbot.provider: gemini` (predefinito) |

Il file `.env.example` elenca le variabili con valori segnaposto.
