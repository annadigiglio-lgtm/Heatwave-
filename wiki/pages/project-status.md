# Stato del progetto (pianificato vs implementato)

**Sorgenti**: confronto diretto tra `docs/ROADMAP.md`/`PROJECT_SUMMARY.md`
(pianificazione) e stato reale delle cartelle/codice.

Questa pagina è quella con la scadenza più breve nella wiki: va aggiornata a
ogni sessione di lavoro rilevante (vedi workflow di ingest in `CLAUDE.md`).

## Settimana 1 — Setup & Data Acquisition

| Attività | Roadmap | Realtà |
|---|---|---|
| Struttura repo | ✅ | ✅ |
| Schema DB (`01_init_database.sql`) | ✅ | ✅ completo: 6 tabelle, 2 viste, 1 funzione, 25+ indici. **Eseguito per la prima volta su un DB reale il 2026-07-04** (Postgres 16 + PostGIS locale) — trovati e risolti 4 bug mai emersi finché nessuno l'aveva davvero eseguito (vedi [ETL](etl-pipeline.md) e [Modello Dati](data-model.md)) |
| Script download (`download_data.py`) | pianificato | ✅ scritto, bug di import **risolto il 2026-07-04** (vedi [Fonti Dati](data-sources.md)); aggiunto anche retry/backoff per rate limit Open-Meteo |
| Download dati 2000-2026 | ⬜ | ✅ **eseguito il 2026-07-04, esteso il 2026-07-15, due volte il 2026-07-17, due volte il 2026-07-18, il 2026-07-19 e il 2026-07-23** — 5.809.330 righe reali, **599 comuni** (8 capoluoghi + 591 extra), dal 2000 **fino a oggi** (non più fermo al 31/12/2025) |
| Dati geografici (ISTAT comuni/province) | ⬜ | ✅ **caricati il 2026-07-04** — 1180 comuni reali in `municipalities` (DB Postgres/PostGIS locale), 8 province con codici ISTAT corretti |
| Python environment / requirements | ⬜ | `.venv` presente, `requirements.txt` presente e dettagliato |

## Settimana 2 — ETL & Analisi

| Attività | Roadmap | Realtà |
|---|---|---|
| `DataCleaner` completo | pianificato | ✅ scritto, **ma non era mai stato eseguibile** fino al 2026-07-04 (`SyntaxError` da newline letterali corrotte + bug che scartava il 99,9% dei dati — vedi [ETL](etl-pipeline.md)). Eseguito su 75.976 righe (8 comuni) e poi su altre 341.892 (36 comuni extra, 2026-07-15), senza modifiche al codice |
| Caricamento `temperature` nel DB | pianificato | ✅ **eseguito il 2026-07-04, esteso il 2026-07-15** — **417.868 righe reali, 44 comuni**, in `temperature`, batch insert (vedi [ETL](etl-pipeline.md)) |
| `identify_heatwaves()` eseguita | pianificato | ✅ eseguita il 2026-07-12 su 8 comuni (51 ondate), **rieseguita il 2026-07-15** su 44 comuni (145 ondate), **due volte il 2026-07-17** su 63 poi 98 comuni, **due volte il 2026-07-18** su 155 poi 177 comuni, **il 2026-07-19** su 234 comuni e **il 2026-07-23** su 599 comuni, sempre dopo `TRUNCATE` (non idempotente) — **2.192 ondate totali**, incluse quelle del 2026 (vedi [Modello Dati](data-model.md)) |
| KPI calcolati | pianificato | ✅ viste materializzate rinfrescate il 2026-07-12 (208 righe, 8 comuni), il 2026-07-15 (1144 righe, 44 comuni), due volte il 2026-07-17, due volte il 2026-07-18, il 2026-07-19 e **il 2026-07-23** — `kpi_annual_by_municipality` ora **16.173 righe** (599 comuni × 27 anni, 2000-2026). Refresh eseguito **senza `CONCURRENTLY`**: la vista non ha un indice univoco (solo btree non-unique), quindi `REFRESH MATERIALIZED VIEW CONCURRENTLY` fallisce con `ObjectNotInPrerequisiteState` — segnalato come possibile miglioria futura (creare un indice univoco su `(municipality_id, year)`), non ancora applicato |
| Query SQL (10+) | pianificato | 3 query scritte in `02_common_queries.sql` |

## Settimana 3 — Visualizzazione & Deployment

| Attività | Roadmap | Realtà |
|---|---|---|
| `src/analysis/` (statistica, spaziale, temporale) | pianificato | ✅ **implementata ed eseguita su dati reali il 2026-07-15** — trend (Mann-Kendall/regressione), statistiche ondate di calore, STL decomposition, Moran's I + clustering K-means (vedi [Analisi Statistica](statistical-analysis.md)) |
| `src/visualization/` | pianificato | ❌ cartella vuota |
| Progetti QGIS | pianificato | ✅ **generati ed eseguiti il 2026-07-15** — 3 progetti `.qgz` (heatmap, hotspot, animazione temporale) via PyQGIS headless, verificati con render PNG (vedi [Mappe GIS](gis-maps.md)); manca solo la mappa "Heatwave Index" |
| Dashboard Streamlit | pianificato | ✅ **implementata il 2026-07-15, contenuto ampliato sostanzialmente lo stesso giorno, pubblicata online il 2026-07-20** — 8 pagine (home con card di navigazione, analisi temporale, analisi spaziale, ondate di calore, contesto territoriale, sintesi della ricerca, download dati, citazioni e fonti), filtri, palette colori coerente, dati reali, verificata via `AppTest`, live su Streamlit Community Cloud: https://heatwave-piemonte.streamlit.app (vedi [Dashboard](dashboard.md)) |
| Test unitari | pianificato (70%+ coverage) | ✅ **implementati il 2026-07-15** — 31 test pytest (`DataCleaner`, `src/analysis/` funzioni pure, `Config`), 86% di copertura su `clean_data.py`; **1 bug reale trovato e corretto** in `detect_outliers()` (vedi [Test Unitari](testing.md)) |
| Documentazione | in gran parte fatta | ✅ README, PROJECT_SUMMARY, docs/* molto estesi (a volte più avanti del codice) |

## Cronologia degli aggiornamenti principali

**Il nucleo pianificato del progetto è completo**: pipeline Extract →
Transform → Load, analisi statistica/spaziale, mappe GIS e dashboard sono
tutte implementate ed eseguite su dati reali. Quello che segue è la
cronologia di come ci si è arrivati.

### 2026-07-04 — pipeline dati end-to-end (il buco più grande, colmato)

Download Open-Meteo reale, database Postgres/PostGIS locale configurato e
raggiungibile (via `.env`), schema inizializzato, 8 province + 1180
comuni reali + 75.976 righe di temperatura (8 comuni capoluogo,
2000-2025) caricati. Questo era il buco più grande del progetto — da qui
in poi il resto ha avuto dati reali su cui lavorare.

> Nota di granularità: `temperature` copriva inizialmente solo gli **8
> comuni capoluogo di provincia** (unica granularità realmente misurata da
> Open-Meteo), non tutti i 1180 comuni — scelta deliberata, vedi
> [ETL](etl-pipeline.md).

### 2026-07-12 — prima esecuzione di `identify_heatwaves()`

51 ondate identificate (2000-2025) e viste materializzate KPI rinfrescate
(208 righe ciascuna). **Tutta la catena dati → schema → KPI/ondate è ora
reale e verificata**: `temperature`, `heatwave_events`,
`kpi_annual_by_municipality`, `kpi_annual_by_province` hanno tutte
contenuto vero su cui costruire analisi/mappe/dashboard.

### 2026-07-15 — analisi, dashboard, mappe GIS, test, rifiniture

Giornata con il maggior numero di traguardi:

- **`src/analysis/`** scritta ed eseguita su dati reali — trend di
  riscaldamento (7/8 comuni con trend significativo, +0.4/+1.0
  °C/decade), statistiche ondate di calore (intensità/durata popolate su
  tutte le 51 ondate), STL decomposition (ampiezza stagionale ~28-32°C),
  Moran's I + clustering climatico (limitati dal campione di sole 8
  unità spaziali — vedi [Analisi Statistica](statistical-analysis.md) per
  dettaglio e caveat). Risultati salvati come CSV in `output/`.
- **Dashboard Streamlit**: scritta ed eseguita (5 pagine, dati reali) —
  vedi [Dashboard](dashboard.md) per i 3 bug trovati eseguendola per la
  prima volta (import `components` non risolto, WKT passato a
  `folium.GeoJson` senza conversione, API deprecata). Verificata senza
  browser con `streamlit.testing.v1.AppTest`, poi avviata live.
- **Mappe GIS**: generati i 3 progetti QGIS pianificati via script PyQGIS
  headless (`qgis_projects/build_maps.py`), verificati con render PNG
  offscreen invece che aprendo QGIS Desktop — vedi [Mappe GIS](gis-maps.md)
  per i 2 bug reali trovati (nomi di campo dopo un join, subquery SQL non
  eseguibile come `table=` in QGIS) e per l'unico aspetto non verificabile
  in automatico (rendering del testo delle etichette, bloccato da un font
  mancante nell'ambiente headless). **Con questo, tutti e 3 i pezzi
  principali di Settimana 3 (analisi, dashboard, mappe) sono implementati
  ed eseguiti su dati reali.**
- **Rifiniture**: `logging.format` in `config.yaml` corretto alla sintassi
  loguru (era sintassi stdlib `%(...)s`, sovrascriveva erroneamente il
  default corretto di `src/utils/logger.py`) — console e file di log ora
  leggibili. `requirements.txt` allineato alle versioni effettivamente
  installate nel `.venv` (drift esistente da inizio progetto — es. pandas
  2.1.4→3.0.3, numpy 1.26→2.4, streamlit 1.29→1.58); verificato `pip
  check`, nessun conflitto.
- **Estensione a 44 comuni**: su richiesta dell'utente ("rendere Moran's
  I/clustering più robusti"), copertura reale estesa da 8 a 44 comuni (36
  extra selezionati con campionamento "farthest-point" per massimizzare
  la copertura spaziale per provincia — vedi [ETL](etl-pipeline.md)).
  Rieseguita l'intera catena a valle: `identify_heatwaves()` (145
  ondate), viste KPI, tutti e 4 i moduli di `src/analysis/`, i 3 progetti
  QGIS, tutte le pagine dashboard. Risultato più significativo: **Moran's
  I passa da non significativo (p=0.732, n=8) a statisticamente
  significativo (I=0.101, p=0.002, n=44)** — vedi
  [Analisi Statistica](statistical-analysis.md). Nel farlo, scoperto e
  risolto un bug di encoding vecchio di 11 giorni (28 comuni su 1180 con
  nomi corrotti nel DB, mai notato prima — vedi [Fonti Dati](data-sources.md)).
- **Ampliamento contenuto dashboard**: su richiesta esplicita dell'utente,
  contenuto delle 3 pagine di analisi ampliato sostanzialmente (dettaglio
  completo in [Dashboard](dashboard.md)): anomalie termiche, confronto
  stagionale, boxplot per quinquennio e confronto con letteratura in
  Analisi Temporale; mappe coropletiche per provincia (via `ST_Union`
  PostGIS), mappa del trend per comune, fasce altitudinali e isola di
  calore urbana in Analisi Spaziale; conteggio cumulato, mappa di
  concentrazione e heatmap "calendario" in Ondate di Calore. Per la
  fascia altitudinale è stato necessario popolare
  `municipalities.elevation_m` (prima sempre `NULL`) — scaricato per
  davvero da Open-Meteo Elevation API per i 44 comuni con dati (scelta
  confermata con l'utente, invece di un placeholder "non disponibile") —
  vedi [Fonti Dati](data-sources.md) e [Modello Dati](data-model.md).
- **Test unitari**: 31 test pytest scritti, vedi [Test Unitari](testing.md).

### 2026-07-16 — popolazione e uso del suolo (covariate per il paper)

Popolazione residente (`demo.istat.it`) e CORINE Land Cover 2018
popolate per tutti i 1180 comuni — vedi [Fonti Dati](data-sources.md) per
il dettaglio completo di entrambe le fonti.

### 2026-07-17 — estensione a 63 comuni, NDVI, modello statistico, 35 comuni extra

Giornata più densa del progetto, quattro traguardi distinti:

**1. Estensione a 63 comuni + dati fino ad oggi**. Su richiesta esplicita
dell'utente ("coprimi i 1180 comuni piemontesi, e aggiorna la data fino ad
oggi"). Obiettivo iniziale enorme (1180 comuni) ridimensionato insieme
all'utente dopo aver spiegato costi/rischi reali (vedi
[Fonti Dati](data-sources.md) per il dettaglio): tentativi falliti a 300 e
poi 56 comuni extra per lo stesso motivo — **Open-Meteo ha un limite
giornaliero di richieste** (non solo "al minuto" come già noto), scoperto
nel modo peggiore (~5h40 di download quasi tutto sprecato il primo
giorno, perso perché lo script salvava solo a fine esecuzione). Corretto
alla radice: salvataggio incrementale (ogni comune scaricato viene subito
scritto su disco) in `download_extra_municipalities.py` e nel nuovo
`update_recent_data.py`, così nessuna interruzione futura fa più perdere
progresso. Risultato netto in due giorni: **44 → 63 comuni** (19
aggiuntivi, stesso campionamento "farthest-point") e **tutti i 63 comuni
ora arrivano fino a oggi** — non i 1180 completi, ma un incremento reale
ottenuto in modo sostenibile invece di un tentativo fallito in blocco.
Vedi [Fonti Dati](data-sources.md) per la scoperta del rate limit,
[ETL](etl-pipeline.md) per il flusso incrementale, e
[Analisi Statistica](statistical-analysis.md) per i risultati ricalcolati
(Moran's I ora 0.132, p=0.001, ancora più significativo che con 44
comuni).

> **2 bug reali trovati e corretti** per via del nuovo dato che arriva
> fino al 2026 (non più fermo al 2025): (1) `frequency_by_year()` in
> `heatwave_stats.py` aveva un `reindex` fisso `range(2000, 2026)` che
> scartava in silenzio le ondate del 2026 (16 ondate nascoste, trovate
> verificando l'output dopo l'estensione) — reso dinamico sul range anni
> realmente presente nei dati; (2) lo slider dell'intervallo anni nella
> dashboard (`components/filters.py`) aveva `YEAR_MIN, YEAR_MAX = 2000,
> 2025` fissi nel codice, che avrebbe reso impossibile selezionare il
> 2026 una volta arrivati i dati più recenti — resi dinamici dalla data
> reale più vecchia/più recente in `temperature`.

**2. NDVI — terza covariata esplicativa** per il paper (dopo popolazione e
CORINE, fatte il giorno prima) — vedi
[Articolo scientifico](paper-scientifico.md). Decisione presa con
l'utente: Copernicus Global Land Service NDVI 300m V3 (prodotto già
calcolato, download manuale) invece di Sentinel-2 vero (10m, via GEE o
CDSE Statistical API). Un'apparente scorciatoia verso un prodotto NDVI
10m reale trovata durante la navigazione del portale (HR-VPP) si è
rivelata un vicolo cieco — tornati al piano originale. Il download reale
via Copernicus Browser ha richiesto diversi tentativi e ha prodotto un
file **globale** da 3.3 GB (nessun ritaglio lato server per questo
prodotto, a differenza di CLC) — gestito senza saturare la RAM leggendo
solo la finestra Piemonte via `rasterio.windows`. Scala/offset/flag della
formula DN→NDVI **verificati sui metadati embedded del file reale**, non
solo dalla documentazione (rivelatasi imprecisa sui codici di flag).
**Risultato**: `municipality_ndvi` popolata per **1180/1180 comuni**.
Media regionale NDVI 0.663, range 0.327-0.867, valori verificati a
campione coerenti coi risultati CORINE. Vedi [Fonti dati](data-sources.md)
e [Modello dati](data-model.md).

**3. Prima iterazione del modello statistico**: non appena
popolazione/CORINE/NDVI sono state tutte disponibili, prima esecuzione di
`src/analysis/spatial_regression.py` — OLS classico (temp ~
elevazione+popolazione+%urbano+NDVI, VIF tutti <5, R²=0.979 dominato
dall'elevazione) seguito dal check concordato con l'utente (Moran's I sui
residui): ancora significativo (I=0.081, p=0.001), quindi costruito anche
un vero modello a errore spaziale via `spreg`/`libpysal`. La regola di
Anselin ha dato un esito non ambiguo (errore spaziale, non lag):
lambda=0.738 (p<0.001). **Risultato più rilevante**: **% urbano diventa
statisticamente significativo col segno atteso solo nel modello
spaziale** (l'OLS classico lo mascherava) — prima conferma quantitativa,
seppur provvisoria (n=63), dell'ipotesi originale del paper su
città/urbanizzazione come fattore esplicativo. NDVI resta significativo
ma con segno controintuitivo (più verde → temperatura più alta), da
approfondire. Decisione concordata con l'utente: **non** aggiungere
subito altre covariate candidate — si rilancia questa stessa pipeline via
via che il campione di comuni con temperatura cresce. Vedi
[Analisi statistica](statistical-analysis.md) per il dettaglio tecnico
completo e [Articolo scientifico](paper-scientifico.md) per l'impatto sul
piano del paper.

**4. 35 comuni extra, scaricati da una seconda macchina, poi importati lo
stesso giorno**: una collaboratrice, senza accesso al database del
titolare, ha ricostruito quali comuni fossero già coperti leggendo le
preview PNG dei progetti QGIS (tracciate in Git a differenza dei dati),
poi scaricato 35 comuni aggiuntivi da Open-Meteo fino al blocco del rate
limit giornaliero — vedi
[Fonti Dati](data-sources.md#download-collaborativo-da-una-seconda-macchina--35-comuni-extra-2026-07-17)
per il metodo (verificabile) e un bug reale trovato e corretto durante
l'esecuzione (confronto `int`/`str` su `istat_code` che causava download
duplicati). Import eseguito lo stesso pomeriggio: pulizia (`DataCleaner`,
0 righe scartate, 666 outlier IQR) + risoluzione `istat_code` →
`municipality_id` via join contro `municipalities` (tutti e 35 trovati) —
passi documentati in
[Pipeline ETL](etl-pipeline.md#import-dei-35-comuni-extra-dalla-seconda-macchina-2026-07-17).
**Risultato: 63 → 98 comuni, 950.110 righe in `temperature`.**

**5. Ricalcolo completo a valle dei 98 comuni**: elevazione ri-scaricata
per tutti i comuni con temperatura (98/98), `TRUNCATE` + `identify_heatwaves()`
(331 ondate, da 190), refresh viste KPI (`kpi_annual_by_municipality`
2.646 righe, `kpi_annual_by_province` 216), tutti e 5 i moduli di
`src/analysis/` rieseguiti (inclusa `spatial_regression.py`) e mappe QGIS
rigenerate — vedi [Analisi Statistica](statistical-analysis.md) per i
risultati completi. **Cambio degno di nota**: a n=98 **% urbano non è più
statisticamente significativo** nel modello a errore spaziale (lo era a
n=63, p=0.011) — registrato onestamente in
[Articolo scientifico](paper-scientifico.md) invece di tenere solo il
risultato precedente. Testo della dashboard corretto di conseguenza (vedi
[Dashboard](dashboard.md)).

### 2026-07-18 — 98 → 177 comuni: seconda collaborazione + download diretto

Stessa collaboratrice della sessione precedente, stessa macchina esterna.
Dopo `git pull` (che ha portato il repo alla versione a 98 comuni e
importato la nuova pagina [Comuni già coperti](comuni-coperti.md), scritta
dal titolare proprio per evitare di dover ripetere la ricostruzione dai
PNG QGIS della volta precedente), campionamento "farthest-point" rieseguito
sui 1082 comuni ancora scoperti usando questa lista come fonte diretta e
affidabile. Download bloccato dal rate limit giornaliero dopo **57 comuni**
riusciti (su "Cannobio", stesso pattern di backoff crescente già visto) —
questa volta **senza il bug di doppioni** della sessione precedente,
verificato riga per riga.

**File stantio scartato prima dell'import**: insieme al file nuovo
(`batch2`) era presente anche una copia di `temperature_data_extra_helper_35comuni.csv`
— stesso identico contenuto del file già importato il giorno prima
(339.325 righe, stessi 35 codici ISTAT). Verificato contro il DB prima di
toccarlo (tutti e 35 già presenti) e scartato senza importarlo: un
secondo import avrebbe duplicato 339mila righe senza che nessun vincolo
DB lo impedisse. La cautela di controllare sempre il contenuto di un file
consegnato contro lo stato reale del DB, invece di fidarsi del nome del
file o della richiesta dell'utente, ha evitato un danno reale.

**Import di `batch2`** (57 comuni): pulizia + risoluzione `istat_code` →
`municipality_id`, stessi passi già collaudati. **98 → 155 comuni.**

**Download diretto di altri 22 comuni**, eseguito subito dopo (non da una
macchina esterna): `download_extra_municipalities.py --count 40`,
bloccato dal rate limit (già in parte consumato dalla collaboratrice
nella stessa giornata) dopo 22 comuni — questa volta con un sintomo
diverso, nessun errore esplicito ma il processo bloccato "silenziosamente"
per oltre 12 minuti senza scrivere nulla di nuovo, interrotto
manualmente dopo aver verificato che i 22 comuni già ottenuti fossero
completi. **155 → 177 comuni, 1.716.094 righe in `temperature`.**

**Bug reale trovato durante il ricalcolo**: `fetch_elevation.py`
interrogava l'Elevation API con tutte le coordinate in un'unica
richiesta — oltre 100 comuni l'API risponde `400`. Fix: richieste a
lotti da 100.

**Ricalcolo completo a valle dei 177 comuni**: elevazione (177/177,
col fix sopra), `TRUNCATE` + `identify_heatwaves()` (**640 ondate**, da
331), refresh viste KPI (`kpi_annual_by_municipality` 4.779 righe), tutti
e 5 i moduli di `src/analysis/`, mappe QGIS rigenerate. **Ulteriore
cambio nei risultati statistici**: a n=177 nel modello a errore spaziale
**anche NDVI smette di essere significativo** (oltre a % urbano, già non
significativo da n=98) — solo l'elevazione resta un predittore robusto
in tutte e tre le versioni (n=63/98/177). Vedi
[Analisi Statistica](statistical-analysis.md) per il dettaglio, testo
della dashboard corretto di conseguenza.

**Consolidamento file** (stesso pattern del giorno prima): `data/raw/`
e `data/processed/` riportati a 4 e 2 file rispettivamente, dopo aver
unito i file del giorno e verificato zero duplicati/sovrapposizioni.
[Comuni già coperti](comuni-coperti.md) aggiornata con l'elenco completo
dei 177 comuni.

Vedi [Fonti Dati](data-sources.md#seconda-sessione-collaborativa--download-diretto--98--177-comuni-2026-07-18)
e [Pipeline ETL](etl-pipeline.md#comuni-extra--57-dalla-collaboratrice--22-scaricati-direttamente-2026-07-18)
per il dettaglio completo.

### 2026-07-18 (pomeriggio) — VALIDAZIONE ARPA PIEMONTE: FASE 1 DEL PAPER RISOLTA

Fase a priorità più alta del piano paper ([Articolo scientifico](paper-scientifico.md)),
bloccata dal 2026-07-16 (URL ARPA in `config.yaml` risponde 404). Trovata
via ricerca web una vera API REST pubblica di ARPA Piemonte
(`utility.arpa.piemonte.it/meteoidro/`, non linkata da nessuna pagina
ufficiale del sito ARPA) — vedi
[Fonti dati](data-sources.md#arpa-piemonte--integrata-e-scaricata-2026-07-18)
per il dettaglio tecnico completo.

Implementato `src/data_acquisition/download_arpa.py`: dei 177 comuni con
temperatura Open-Meteo, **51 hanno una stazione ARPA reale corrispondente**
(sensore di temperatura attivo, `codice_istat_comune` come chiave di join —
inclusi tutti gli 8 capoluoghi). Scaricate **451.502 righe** giornaliere
reali (2000-01-01 → oggi), caricate in una nuova tabella `arpa_temperature`
(`sql/05_arpa_temperature.sql`).

**Risultato della validazione** (`src/analysis/validate_arpa.py`):
correlazione molto alta con Open-Meteo (r medio 0.966 su temp_max) ma un
**bias sistematico negativo di -1.71°C in media**, che peggiora con
l'elevazione del comune (r=-0.348, p=0.012) — le rianalisi come Open-Meteo
mediano una cella di griglia, non un punto, e in terreno alpino complesso
questo smussa le temperature estreme reali. Risultato quantitativo
riportabile nel paper, non solo un limite dichiarato qualitativamente. Vedi
[Analisi statistica](statistical-analysis.md#validazione-contro-arpa-piemonte-2026-07-18)
per il dettaglio completo per comune.

**Approfondimento stesso giorno — bias sui giorni caldi + confronto a
livello di evento**: sui giorni davvero caldi (ARPA temp_max>35°C) la
correlazione crolla a 0.400 (da 0.956 su tutti i giorni). Più diretto:
riapplicando `identify_heatwaves()` ai dati ARPA per i 51 comuni, **ARPA
mostra 322 ondate reali contro le 150 rilevate da Open-Meteo (recall
31.4%, precision 62%)** — Open-Meteo cattura meno di un terzo delle
ondate di calore realmente accadute in questi comuni. Implica che le 640
ondate totali già contate nel progetto su 177 comuni sono probabilmente un
sottoconteggio sostanziale, non un numero prudente — risultato più
rilevante di tutta la validazione, da riportare nel paper come limite
quantificato. Vedi
[Analisi statistica](statistical-analysis.md#confronto-a-livello-di-evento-quante-ondate-di-calore-vere-mancano-2026-07-18).

**Contro-bilanciamento**: il trend di riscaldamento invece regge alla
fonte dati (88.2% di concordanza di segno ARPA/Open-Meteo, nessun caso di
trend opposti entrambi significativi) — il risultato "riscaldamento
diffuso e significativo" del paper non è un artefatto, il conteggio delle
ondate sì. Vedi
[Analisi statistica](statistical-analysis.md#il-trend-di-riscaldamento-regge-sui-dati-di-stazione-reali-2026-07-18).

### 2026-07-18 (tardo pomeriggio) — COPERTURA ARPA ESTESA A 218 COMUNI

Discussione con l'utente su come riorganizzare la dashboard: invece di
una pagina "Validazione Dati" separata, un **selettore per pagina** (tab
temporale, spaziale, ondate di calore) tra tre modalità — "ARPA +
Open-Meteo", "solo ARPA", "solo Open-Meteo". Durante la discussione,
verificato che il matching comuni↔stazioni ARPA era filtrato solo sui 177
comuni con Open-Meteo per un vincolo di contesto (fase di validazione),
non un limite reale dell'API. Esteso a tutti i 1180 comuni: **167 comuni
nuovi** trovati con stazione ARPA attiva e nessun dato Open-Meteo
esistente. Scaricati con successo, **zero errori/blocchi** (l'API ARPA
non ha mostrato segni di rate limit su questo volume, a differenza di
Open-Meteo) — vedi
[Fonti dati](data-sources.md#estensione-a-218-comuni-2026-07-18) per il
dettaglio tecnico completo. **Copertura ARPA ora: 218 comuni, 1.965.138
righe** (era 51 comuni, 451.502 righe).

**Aggiornamento stesso giorno — selettore implementato**: il selettore
Open-Meteo/Solo ARPA/Confronto discusso con l'utente è stato scritto ed
è live in **Analisi Temporale** e **Ondate di Calore** (nuovo componente
`components/data_source.py` + funzioni ARPA live in `queries.py` +
`identify_heatwaves_events()` in `heatwave_definitions.py` — vedi
[Dashboard](dashboard.md#selettore-fonte-dati-open-meteo--arpa--confronto--2026-07-18)
per il dettaglio completo). Verificato con `AppTest` su tutte e 3 le
combinazioni di fonte in entrambe le pagine, nessuna eccezione. La pagina
"Validazione Dati" dedicata **non è stata rimossa** (scelta deliberata,
non un limite tecnico — contenuto che non ha una casa naturale nelle altre
due pagine). Download Dati non ha ricevuto il selettore (CSV export non
dipende dalla fonte).

**Aggiornamento stesso giorno (sera) — esteso anche ad Analisi Spaziale**:
l'utente ha fatto notare che la giustificazione iniziale per escludere
questa pagina era incompleta — solo le mappe uso del suolo/popolazione/
NDVI sono davvero indipendenti dalla fonte, ma mappa coropletica, mappa
del trend, fascia altitudinale, cluster K-means e Moran's I sono tutti
temperatura-dipendenti. Esteso il selettore anche lì (vedi
[Dashboard](dashboard.md#selettore-fonte-dati-open-meteo--arpa--confronto--2026-07-18)
per il dettaglio, incluso il bug bloccante trovato e risolto prima di
scrivere il codice: `elevation_m` mancante per i 167 comuni solo-ARPA).
Server live riavviato su richiesta dell'utente per la verifica visiva
(trovati e terminati 3 processi Streamlit duplicati sulla stessa porta —
bug già noto, vedi sezione dashboard).

**Aggiornamento stesso giorno (sera, seguito) — mappa trend corretta,
pagina "Validazione Dati" eliminata**: l'utente ha chiesto se, in
modalità Confronto, la mappa del trend mostrasse davvero i colori di
entrambe le fonti — non era vero, mostrava solo Open-Meteo. Corretta con
due mappe affiancate (stessa scala colore). Chiesto poi di portare anche
la mappa del **bias** (già esistente solo nella pagina dedicata
"Validazione Dati") dentro Analisi Spaziale — fatto, e a quel punto
l'utente ha messo in dubbio il senso di tenere ancora quella pagina a
parte, dato che gran parte del suo contenuto era ormai duplicato altrove
(recall/precision in Ondate di Calore, confronto trend in Analisi
Temporale). Scelta confermata con l'utente (`AskUserQuestion`): **pagina
eliminata**, tutto il contenuto residuo (scatter bias/elevazione,
istogramma, bias per condizione, tabella completa 51 comuni, tabella
trend comparativa, metodologia) spostato in Analisi Spaziale → tab
Dettaglio tecnico → sezione "Validazione ARPA — dettaglio" (visibile solo
in modalità Confronto). **5 pagine dashboard**, non più 6. Nessun
contenuto perso. Verificato con `AppTest` su tutte e 3 le combinazioni di
fonte, incluso `Home.py`, nessuna eccezione.

### 2026-07-19 — 177 → 234 comuni: terza collaborazione mirata alla mappa Bias ARPA

Sessione partita da un fraintendimento: l'utente aveva chiesto di
scaricare Open-Meteo per completare la mappa Bias Open-Meteo↔ARPA (i
comuni con ARPA ma senza Open-Meteo, 167 su 218), non di aggiornare la
serie esistente né di estendere la copertura spaziale a caso — le due
azioni tentate all'inizio della sessione, corrette non appena l'utente ha
chiarito l'obiettivo (vedi [Comuni già
coperti](comuni-coperti.md#correzione-stessa-giornata)). Il tentativo
diretto (provincia di Torino) si è bloccato dopo 18 comuni; per puro caso
9 di quei 18 avevano anche ARPA e sono comunque serviti.

La collaboratrice (stessa seconda macchina delle sessioni del 07-17 e
07-18) ha scaricato **57 comuni** direttamente dalla lista dei 167 target
(round-robin per provincia), bloccata anch'essa dalla quota a 57/158.
Consegnati e importati (pulizia + join `istat_code` → `municipality_id` +
`insert_temperature_for_municipalities` + ricalcolo a valle completo):
**234 comuni**, 2.268.823 righe in `temperature`. `download_arpa.py`
rilanciato di conseguenza: 108/234 comuni Open-Meteo hanno anche ARPA (i
51 di prima + tutti i 57 nuovi — la lista target si è rivelata corretta al
100%). Restano **101 comuni** dei 167 originali ancora senza Open-Meteo,
per le prossime sessioni dopo il reset quota.

Vedi [Comuni già coperti](comuni-coperti.md#obiettivo-reale-completare-la-mappa-bias-open-meteoarpa)
per la lista completa e [Pipeline ETL](etl-pipeline.md#comuni-extra-mirati-alla-validazione-arpa--158-comuni-target-2026-07-19)
per il dettaglio del download della collaboratrice e dell'import.

**Aggiornamento (stesso giorno, sera)**: `download_arpa.py` e l'intera
pipeline di analisi (`refresh_dashboard.py`) rieseguiti per intero — vedi
[Pipeline ETL](etl-pipeline.md#import-dei-57-comuni-arpa-target-e-ricalcolo-completo-2026-07-19)
per il resoconto completo, incluse due interruzioni ambientali dei
processi in background (non errori applicativi) e la correzione di
un'iniziativa non richiesta (il titolare/IA aveva rilanciato il download
ARPA di propria iniziativa, fermato su segnalazione dell'utente e ripreso
solo dopo conferma). Risultati di validazione aggiornati sul campione a
108 comuni in [Analisi
statistica](statistical-analysis.md#validazione-contro-arpa-piemonte-2026-07-18-estesa-il-2026-07-19):
bias -1.59°C (quasi invariato), ma **recall delle ondate crollato al
16.4%** dal 31.4% originale — domanda aperta, non ancora spiegata.

### 2026-07-20/23 — accumulo senza import, poi giro unico: 234 → 599 comuni

Per 3 giorni (2026-07-20, 21, 22, 23) il titolare/IA e la collaboratrice
hanno continuato a scaricare comuni (sia mirati ARPA fino al
completamento a 167/167, sia estensione generale con criterio spaziale),
**deliberatamente senza importare né ricalcolare ad ogni sessione** — la
pipeline completa richiede ore, ripeterla ogni giorno non aveva senso.
Durante l'accumulo, **due bug reali di processo scoperti**: (1) 2 comuni
(Pragelato, Sestriere) scaricati due volte dalla collaboratrice nella
stessa sessione perché il controllo "già scaricato" guardava solo il DB,
non il file appena prodotto nella stessa sessione; (2) 8 comuni
riscaricati un giorno dopo perché un aggiornamento della wiki era rimasto
**non committato/pushato** — la collaboratrice ha lavorato su uno
snapshot Git vecchio di un giorno. Entrambi risolti deduplicando (righe
verificate identiche prima di scartarle), non hanno causato perdita dati,
solo spreco di quota.

Il 2026-07-23 l'utente ha chiesto il giro unico rimandato: consolidati
tutti i lotti pendenti (347 comuni nuovi + 18 di Torino + 267 righe di
delta) — **3.540.507 righe pulite e importate**, **234 → 599 comuni**
(5.809.330 righe totali). Ricalcolo completo: elevazione 599/599,
`identify_heatwaves()` → **2.192 ondate** (da 770), KPI →
**16.173 righe**. `download_arpa.py` rilanciato: **218/218 comuni ARPA
ora hanno anche Open-Meteo** (copertura ARPA completa, era 108/234).
Pipeline di analisi (`refresh_dashboard.py`) eseguita in **parallelo** al
download ARPA per risparmiare tempo (STL da sola: **4h10min** per 599
comuni) — mappe QGIS rigenerate, file raw/processed consolidati (un
altro bug di merge scoperto e corretto durante il consolidamento, 14
righe temporaneamente perse per una deduplica su colonna svuotata per
errore, recuperate).

**Risultati di validazione ARPA sul campione completo** (218/218,
vedi [Analisi statistica](statistical-analysis.md#validazione-contro-arpa-piemonte-2026-07-18-estesa-il-2026-07-19-copertura-completa-il-2026-07-23)):
bias -1.52°C (stabile su tutti e 3 gli allargamenti), **recall delle
ondate risalito al 25.2%** (da 16.4% a 108 comuni — il valore intermedio
era probabilmente rumoroso su un campione piccolo e non rappresentativo),
ma **la differenza di pendenza del trend ha invertito segno**
(-0.096→+0.148°C/decade) — segnalato esplicitamente come risultato
instabile da non riportare come cifra precisa nel paper, solo come
concordanza qualitativa (92.7% dei comuni concorde in segno, stabile e
in crescita).

**2026-07-24 — sincronizzazione wiki/dashboard sui risultati a 599 comuni**:
`refresh_dashboard.py` (tutti e 5 i moduli di `src/analysis/`) era già
stato rieseguito sul campione a 599 comuni il 23/7 pomeriggio insieme
all'import, ma i risultati non erano ancora stati sintetizzati in
`statistical-analysis.md` né corretti nel testo statico della dashboard —
fatto in questa sessione (richiesta esplicita dell'utente: "controlla
tutte le scritte del frontend e della wiki... riportalo"). Due correzioni
sostanziali rispetto a claim ripetute per più estensioni consecutive
(dettaglio completo in
[Analisi statistica](statistical-analysis.md#aggiornamento-2026-07-24--da-177-a-599-comuni-via-234)):
**Argentera si aggiunge a Briga Alta come secondo comune con
raffreddamento significativo** (Mann-Kendall, confermato anche da STL), e
nel modello a errore spaziale **% urbano torna non significativo**
(p=0.370, era p=0.031 a n=234) mentre **NDVI diventa significativo con
segno negativo** (p=0.012, per la prima volta il segno atteso invece del
solito segno controintuitivo). L'unico predittore rimasto stabile in
tutte e 5 le versioni del modello (n=63/98/177/234/599) resta
l'elevazione. Corretti anche 5 punti di testo statico non aggiornati
automaticamente (fermi a "234 comuni"): `dashboard/pages/08_citazioni_e_fonti.py`,
`dashboard/pages/05_contesto_territoriale.py` (risultati del modello
spaziale), commenti/docstring in `Home.py`/`queries.py`/`data_source.py`,
oltre a `README.md` (due punti) e `wiki/pages/gis-maps.md` (fermo a "177
comuni" nonostante le mappe QGIS fossero già state rigenerate il 23/7).

### 2026-07-28 — verifica servizio Postgres: claim obsoleto corretto

Su richiesta dell'utente ("cosa manca da fare al progetto?" → servizio
Postgres), verificato lo stato reale invece di fidarsi del claim esistente
in "Prossimi passi": `Get-Service postgresql-x64-16` → `Running` /
`Automatic`; processo `pg_ctl.exe` con parent `services.exe` e orario di
avvio coincidente col boot del PC. Il servizio **è già** un vero servizio
Windows auto-avviabile — non serviva alcuna azione. Corretto il punto 3 di
"Prossimi passi" di conseguenza. Non è noto quando questo sia cambiato
rispetto a quanto documentato in precedenza.

## Prossimi passi

Tutti minori/non bloccanti — il nucleo pianificato del progetto è
completo:

1. ~~Aprire i 3 `.qgz` in QGIS Desktop per confermare visivamente le
   etichette~~ — **fatto e confermato dall'utente il 2026-07-15**, incluso
   un fix successivo per le etichette mancanti in `evolution_animation.qgz`
2. ~~Popolare `elevation_m`~~ — **fatto parzialmente il 2026-07-15**, ma
   solo per i comuni con dati di temperatura reali (Open-Meteo Elevation
   API, vedi [Modello Dati](data-model.md)); esteso a 98 comuni il
   2026-07-17 e a 177 il 2026-07-18; resta `NULL` per il resto dei 1180
   comuni
3. ~~Riavviare `postgresql-x64-16` come vero servizio Windows~~ — **verificato
   il 2026-07-28: già a posto**, claim obsoleto. Il servizio risulta
   `Status: Running`, `StartType: Automatic`; `pg_ctl.exe` è avviato da
   `services.exe` (Service Control Manager) e il suo orario di avvio
   coincide esattamente col boot del PC (12g 10h di uptime) — quindi
   riparte da solo dopo un riavvio, contrariamente a quanto scritto in
   precedenza. Non è chiaro quando/come sia stato risolto (probabilmente
   durante un update di PostgreSQL o una configurazione manuale non
   documentata). Connessione al DB confermata (`psql` → PostgreSQL 16.14,
   `heatwave_piemonte` raggiungibile).
4. Ricordarsi di rifare `REFRESH MATERIALIZED VIEW` dopo ogni futuro
   caricamento di `temperature` (vedi [Modello Dati](data-model.md)) —
   incluso dopo l'import dei 35 comuni extra descritti sopra
5. Mappa "Heatwave Index" (composito intensità/frequenza ondate) — unica
   mappa pianificata non ancora costruita (vedi [Mappe GIS](gis-maps.md))
6. ~~Test unitari (`tests/` vuota)~~ — **fatto il 2026-07-15**, 31 test
   pytest, vedi [Test Unitari](testing.md); resta da scrivere una
   documentazione API/tutorial
7. Retry più generico per errori di rete transitori (non solo `429`) in
   `download_data.py` — scoperto durante il download dei comuni extra
   (vedi [Analisi Statistica](statistical-analysis.md))
8. ~~Contenuto delle 3 pagine di analisi della dashboard troppo
   essenziale~~ — **ampliato sostanzialmente il 2026-07-15**, vedi
   [Dashboard](dashboard.md)
9. ~~Valutare il deploy pubblico gratuito della dashboard~~ (Streamlit
   Community Cloud) — discusso il 2026-07-15, rimandato allora per il
   blocco tecnico noto (connessione a Postgres/PostGIS su `localhost`, non
   raggiungibile da un server remoto). **Deciso e implementato il
   2026-07-18**: scartata l'opzione DB in cloud (Supabase/Neon) per i costi
   a queste dimensioni (DB reale arrivato a 756 MB lo stesso giorno, con
   218 stazioni ARPA), scelta l'opzione "nessuna connessione DB dal vivo" —
   `src/data_processing/export_dashboard_data.py` esporta uno snapshot
   Parquet in `data/dashboard_export/` (69 MB, tracciato in Git),
   `dashboard/components/queries.py` riscritta per leggere solo da lì,
   `requirements-dashboard.txt` nuovo per il deploy. Resta manuale
   l'aggiornamento (nessun refresh automatico). **Pubblicata il
   2026-07-20**: dashboard live su Streamlit Community Cloud,
   https://heatwave-piemonte.streamlit.app — deploy senza intoppi
   segnalati dall'utente. Vedi [Dashboard](dashboard.md) per il dettaglio
   completo.
10. ~~Importare i 35 comuni extra scaricati dalla seconda macchina~~ —
    **fatto lo stesso giorno (2026-07-17)**: pulizia + risoluzione
    `municipality_id`, poi rilancio di `identify_heatwaves()`/viste
    KPI/`src/analysis/`/mappe QGIS a valle (vedi cronologia sopra).
11. ~~Importare i 57 comuni extra del 2026-07-18~~ — **fatto lo stesso
    giorno**, insieme a un download diretto di altri 22 comuni (98 → 155
    → 177) e al ricalcolo completo a valle (vedi cronologia sopra).
12. ~~Selettore fonte per pagina in dashboard~~ — **fatto lo stesso giorno
    (2026-07-18)**: componente `render_source_selector()`, integrato in
    Ondate di Calore e Analisi Temporale, dati ARPA estesi a 218 comuni per
    supportarlo. Pagina "Validazione Dati" tenuta com'era (scelta
    deliberata). Vedi [Dashboard](dashboard.md#selettore-fonte-dati-open-meteo--arpa--confronto--2026-07-18).
13. ~~Titolo dashboard da cambiare~~ — **deciso e applicato il 2026-07-19**:
    "Il riscaldamento del Piemonte: un'analisi spazio-temporale dei trend
    termici e delle ondate di calore" (README H1, `config.yaml` →
    `dashboard.title`, hero della Home). "Heatwave Piemonte" resta come
    brand/eyebrow (Home + tutti gli `st.set_page_config(page_title=...)`
    delle altre pagine, invariati). `PROJECT_SUMMARY.md` non toccato
    (documento di pianificazione immutabile per `CLAUDE.md`) — cita ancora
    il vecchio titolo.

## Discrepanze da tenere a mente quando si presenta il progetto

`PROJECT_SUMMARY.md` descrive ancora metriche come "1.7M record", "Status:
Production Ready", "database size 3-5 GB" — sono **target pianificati**,
scritti prima di scrivere il codice, non misurazioni reali. Utile saperlo
per non presentarli come risultati raggiunti in un colloquio o in una demo.

**`README.md` riscritto il 2026-07-22** su richiesta esplicita dell'utente
("non mi sembra aggiornato, sembra fatto con l'IA"): non è più un documento
di pianificazione aspirazionale ma riflette lo stato reale rilevato in
questa pagina (234 comuni Open-Meteo, 218 ARPA, 8 pagine dashboard live su
https://heatwave-piemonte.streamlit.app/). Rimossa la roadmap "3 settimane"
(l'utente ha impiegato più tempo di quello e non voleva quel vincolo
temporale nel README pubblico), aggiunto `LICENSE` (MIT, mancante — il
badge lo dichiarava ma il file non esisteva), corretti i placeholder
(`yourusername`, `Nome Cognome`, email finta) con i dati reali dell'autrice.
Per `CLAUDE.md` `README.md` resta formalmente una "sorgente grezza"
immutabile dal punto di vista del workflow di ingest della wiki (la wiki
non lo riscrive per sincronizzarsi), ma resta comunque un file che
l'utente può chiedere di modificare direttamente come qualunque altro file
del repo — è quanto avvenuto qui.
