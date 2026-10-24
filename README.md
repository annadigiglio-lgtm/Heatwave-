# Il riscaldamento del Piemonte

### Un'analisi spazio-temporale dei trend termici e delle ondate di calore

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Dashboard](https://img.shields.io/badge/Dashboard-live-orange)](https://heatwave-piemonte.streamlit.app/)

**Dashboard live: https://heatwave-piemonte.streamlit.app/**

## Descrizione

Heatwave Piemonte è un progetto di Data Engineering, Data Science e GIS che
analizza l'evoluzione delle temperature e delle ondate di calore nei comuni
piemontesi dal 2000 a oggi. Copre l'intera pipeline: acquisizione dati da
fonti pubbliche, pulizia e caricamento in un database geospaziale, analisi
statistica e spaziale, mappe GIS e una dashboard interattiva pubblicata online.

I dati di temperatura (Open-Meteo) sono validati contro le stazioni reali di
ARPA Piemonte, per quantificare quanto ci si può fidare di una rianalisi
climatica rispetto a un'osservazione a terra — un passaggio spesso dato per
scontato in analisi simili.

## Domande di ricerca

- Le giornate con temperature estreme (>30°C, >35°C, >40°C) sono aumentate nel tempo?
- Quali province mostrano i maggiori incrementi di temperatura?
- Esistono pattern geografici e stagionali significativi?
- Quali comuni sono più vulnerabili alle ondate di calore, e perché (elevazione, urbanizzazione, uso del suolo)?

## Cosa contiene il progetto

- **Acquisizione dati**: temperature giornaliere da Open-Meteo (599 comuni,
  2000–oggi, oltre 5,8 milioni di righe), validazione contro 218 stazioni
  reali ARPA Piemonte, popolazione (ISTAT), uso del suolo (Copernicus CORINE
  Land Cover), indice di vegetazione NDVI (Copernicus Global Land Service),
  confini amministrativi dei 1180 comuni piemontesi (ISTAT).
- **Database**: PostgreSQL + PostGIS, schema con tabelle temperature/ondate
  di calore/uso del suolo, viste materializzate per i KPI annuali, funzione
  SQL per l'identificazione delle ondate di calore.
- **Analisi statistica e spaziale**: trend di riscaldamento (Mann-Kendall e
  regressione lineare), decomposizione stagionale (STL), autocorrelazione
  spaziale (indice di Moran), clustering climatico (K-means), modello di
  regressione a errore spaziale (temperatura in funzione di elevazione,
  popolazione, uso del suolo, NDVI).
- **Validazione**: confronto sistematico Open-Meteo vs stazioni ARPA reali
  — correlazione alta (r≈0.97) ma bias sistematico negativo che cresce con
  l'elevazione, e un tasso di rilevamento delle ondate di calore reali
  inferiore a quanto la sola rianalisi suggerirebbe. Risultato riportato
  onestamente come limite del dataset, non nascosto.
- **Mappe GIS**: 3 progetti QGIS (heatmap provinciale, cluster climatici,
  animazione temporale 2000–oggi) generati via PyQGIS.
- **Dashboard Streamlit**: 8 pagine (panoramica, analisi temporale, analisi
  spaziale, ondate di calore, contesto territoriale, sintesi divulgativa dei
  risultati, download dati, citazioni e fonti), con selettore Open-Meteo /
  ARPA / confronto diretto tra le due fonti.
- **Test**: 31 test pytest sulla pipeline di pulizia dati e sulle funzioni di
  analisi, 86% di copertura sul modulo di pulizia.

## Stack tecnologico

- **Python** — pandas, numpy, geopandas, SQLAlchemy
- **Database** — PostgreSQL + PostGIS
- **GIS** — QGIS (via PyQGIS headless), Folium, Shapely
- **Analisi** — scikit-learn, statsmodels, pymannkendall, libpysal/spreg
- **Dashboard** — Streamlit, Plotly
- **Test** — pytest

## Struttura del progetto

```
heatwave-piemonte/
├── src/
│   ├── data_acquisition/   # Open-Meteo, ARPA, popolazione, uso del suolo, NDVI, elevazione
│   ├── data_processing/    # pulizia dati, export snapshot per la dashboard
│   ├── database/           # caricamento nel database
│   ├── analysis/           # trend, ondate di calore, STL, Moran's I, clustering, regressione spaziale, validazione ARPA
│   └── utils/              # configurazione, logging
├── sql/                    # schema DB e query
├── qgis_projects/          # generazione mappe via PyQGIS
├── dashboard/              # applicazione Streamlit (Home.py + pages/)
├── data/                   # dati grezzi, elaborati, esterni, snapshot per il deploy
├── tests/                  # test pytest
├── docs/                   # documentazione (wiki): index.md, pages/, log.md
├── docs/                   # documenti di pianificazione originali (obiettivi iniziali del progetto)
├── config.yaml             # configurazione centrale
└── requirements.txt        # dipendenze Python
```

## Come eseguirlo in locale

Per usare la dashboard non serve installare nulla: è pubblica su
https://heatwave-piemonte.streamlit.app/ e legge uno snapshot dei dati già
calcolato, senza bisogno di un database live.

Per riprodurre l'intera pipeline in locale:

```bash
git clone https://github.com/annadigiglio-lgtm/Heatwave-.git
cd Heatwave-

python -m venv .venv
.venv\Scripts\activate       # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # configura le credenziali del database
psql -U postgres -f sql/01_init_database.sql

python -m src.data_acquisition.download_data
python -m src.database.load_to_db

streamlit run dashboard/Home.py
```

Richiede PostgreSQL 14+ con estensione PostGIS. Gli script aggiuntivi di
acquisizione (ARPA, popolazione, uso del suolo, NDVI, elevazione) sono in
`src/data_acquisition/` e vengono eseguiti separatamente man mano che si
aggiungono covariate all'analisi.

## Test

```bash
pytest tests/ -v
pytest tests/ --cov=src.data_processing --cov=src.analysis --cov=src.utils.config --cov-report=term-missing
```

## Documentazione

La documentazione tecnica (architettura, dati, pipeline ETL, analisi,
Machine Learning, chatbot, test, etica) è in [`docs/`](docs/index.md),
mantenuta come wiki e tenuta sincronizzata con lo stato reale del codice.

## Limiti noti

- Copertura dati di temperatura reale: 599 dei 1180 comuni piemontesi per
  Open-Meteo, 218 per ARPA Piemonte — copertura ARPA completa (tutti i
  comuni con stazione attiva hanno anche dati Open-Meteo).
- Open-Meteo (rianalisi climatica) sottostima sistematicamente le
  temperature massime reali rispetto alle stazioni ARPA, con un bias che
  cresce in territorio alpino — vedi la modalità "Confronto" nella
  dashboard per il dettaglio quantitativo.
- La mappa "Heatwave Index" (indice composito di intensità/frequenza) è
  pianificata ma non ancora realizzata.
- La dashboard pubblica legge uno snapshot statico dei dati: l'aggiornamento
  non è automatico.

## Licenza

Distribuito con licenza MIT — vedi [LICENSE](LICENSE).

## Autore

**Anna Digiglio** — laurea in Scienze Naturali, in formazione ITS Data
Manager for Business Intelligence Software Developer.

- GitHub: [@Anna-digiglio](https://github.com/Anna-digiglio)
- LinkedIn: [anna-digiglio](https://www.linkedin.com/in/anna-digiglio-76a144406/)
- Email: anna.digiglio97@gmail.com

## Fonti dati

Open-Meteo, ARPA Piemonte, ISTAT, Copernicus (CORINE Land Cover, NDVI Global
Land Service) — dettaglio completo con link in
[docs/pages/data-sources.md](docs/pages/data-sources.md) e nella pagina
"Citazioni e Fonti" della dashboard.
