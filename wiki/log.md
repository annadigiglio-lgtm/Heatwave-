# Log della wiki

Log cronologico append-only. Ogni riga: data, azione, pagine toccate.

- **2026-07-04** — INGEST INIZIALE. Creata la wiki da zero seguendo il pattern
  Karpathy (https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
  applicato al progetto Heatwave Piemonte. Letti come sorgenti grezze:
  `README.md`, `PROJECT_SUMMARY.md`, tutto `docs/*.md`, `config.yaml`,
  `sql/01_init_database.sql`, `sql/02_common_queries.sql`,
  `src/data_acquisition/download_data.py`, `src/data_processing/clean_data.py`,
  `src/database/load_to_db.py`, `src/utils/{config,database}.py`, struttura
  cartelle reale (`find`). Create 10 pagine:
  project-overview, architecture, data-sources, data-model, etl-pipeline,
  config-reference, kpi-catalog, sql-queries, concepts, gis-maps, dashboard,
  project-status. Creato `CLAUDE.md` in root come livello schema. Rilevata
  discrepanza significativa tra documenti di pianificazione (che descrivono
  uno stato molto più avanzato, es. "1.7M record", "Production Ready") e
  codice reale (solo Settimana 1 parziale implementata; `dashboard/`,
  `tests/`, `src/analysis/`, `src/visualization/`, `qgis_projects/` vuote).
  Rilevato bug di import in `download_data.py`
  (`CopernicusERA5Downloader._create_cds_client` annota `-> cdsapi.Client`
  senza importare `cdsapi` a livello di modulo) — documentato in
  `pages/data-sources.md`, non corretto (fuori scope di questo task).

- **2026-07-04** — FIX + DOWNLOAD REALE. Corretto il bug di import in
  `src/data_acquisition/download_data.py:184`
  (`_create_cds_client` ora annota `-> Optional["cdsapi.Client"]`, forward
  reference stringa invece di riferimento diretto valutato a tempo di
  definizione classe). Verificato che il modulo si importa correttamente.
  Eseguito un download reale via Open-Meteo (`--years 2000:2025 --sources
  open_meteo`, escluso 2026 perché l'API storica rifiuta date future):
  primo tentativo riuscito solo per 3/8 province (Torino, Alessandria, Asti)
  a causa di rate limit `429` non gestito dallo script, con il vero errore
  nascosto da un secondo bug scoperto in corso d'opera — `config.yaml`
  (`logging.format`) usa sintassi `%(asctime)s` da stdlib `logging` mentre
  `src/utils/logger.py` usa loguru (sintassi `{time}`), quindi ogni riga di
  log stampava la stringa di formato letterale invece del messaggio reale.
  Aggiunto retry con backoff esponenziale (rispetta `Retry-After`, max 5
  tentativi) in `WeatherDataDownloader.download_historical_data` e sleep
  tra regioni portato da 1s a 3s in `download_all_regions`. Ri-eseguito il
  download: tutte le 8 province scaricate con successo, 75.976 righe totali
  in `data/raw/temperature_data.csv`, nessun valore nullo. Pagine aggiornate:
  `data-sources.md` (bug cdsapi risolto, nuovo bug logging documentato, bug
  rate-limit documentato+risolto, dati reali scaricati), `etl-pipeline.md`
  (sezione Extract aggiornata con retry/backoff e run reale),
  `project-status.md` (righe 1-2 della roadmap segnate fatte, aggiunto punto
  minore sul fix di `logging.format` ancora da fare). Bug di logging
  **non corretto** (fuori scope: non bloccava il download, solo la
  leggibilità dei log) — resta in cima ai "prossimi passi" come voce minore.

- **2026-07-04** — POPOLAMENTO `municipalities` CON DATI ISTAT REALI + SETUP DB.
  Sessione lunga, molti bug reali scoperti perché per la prima volta lo
  schema è stato eseguito su un database Postgres/PostGIS realmente vivo.

  **Dati**: trovato (ricerca web, verificato con HEAD HTTP) l'URL ufficiale
  ISTAT dei confini comunali (`.../confini_amministrativi/generalizzati/2026/
  Limiti01012026_g.zip`, sostituiva una pagina HTML non scaricabile in
  `config.yaml`). Riscritto `IstatGeodataDownloader.download_municipalities`
  in `download_data.py` per scaricare/estrarre lo shapefile, filtrare il
  Piemonte (`COD_REG==1`, 1180 comuni), leggerlo con `encoding='cp1252'`
  (altrimenti nomi accentati corrotti), calcolare `area_km2` nel CRS
  proiettato originale prima di riproiettare in 4326, e salvare
  `data/external/municipalities.csv` + `.geojson`. Scoperto un bug nel seed
  SQL: `provinces.istat_code` di Alessandria era `'001'`, duplicato di
  Torino (corretto in `'006'` in `sql/01_init_database.sql`, verificato
  contro lo shapefile ISTAT). Scoperta anche una curiosità dati: il comune
  istat_code `001168` si chiama letteralmente "None" (va letto con
  `keep_default_na=False` per non perderlo come NaN).

  **Config/secrets**: `.env` non aveva alcun effetto — `config.py` non
  chiamava mai `load_dotenv()` nonostante `python-dotenv` fosse già
  installato, e `get_database_url()` dava comunque precedenza al placeholder
  in `config.yaml` (tracciato in git) sulla variabile d'ambiente. Fixato:
  `load_dotenv()` aggiunto, precedenza invertita (env vars vincono).

  **Database locale**: il Postgres 16+PostGIS locale (già installato per
  questo progetto) aveva una password sconosciuta. Reset password via
  metodo standard "trust temporaneo" in `pg_hba.conf` — nel farlo, un mio
  comando PowerShell (`Set-Content -Encoding utf8`) ha introdotto un BOM
  UTF-8 a inizio file, mai notato subito, che ha fatto fallire silenziosamente
  ogni successivo restart del servizio per diversi tentativi (`FATALE:
  could not load pg_hba.conf`, mascherato da timeout SCM di Windows).
  Diagnosticato leggendo i log Postgres ed Event Viewer; risolto riscrivendo
  il file senza BOM. Il servizio Windows (`postgresql-x64-16`) non si è più
  riavviato correttamente da SCM dopo i tentativi falliti — usato `pg_ctl`
  direttamente (stop/start bypassando il Service Control Manager) come
  workaround; **il servizio Windows resta "Stopped"**, Postgres gira ma non
  come servizio: da sistemare in una sessione futura (probabile bisogno di
  riavviare il servizio da una sessione admin quando comodo).

  **Bug nello schema/loader, mai emersi prima perché mai eseguiti su un DB
  vivo**: (1) `initialize_schema()` usava `exec_driver_sql`, che passa
  sempre un dict di parametri a psycopg2 anche se vuoto, facendo interpretare
  il `%` letterale di `'% of data completeness'` come segnaposto — fix:
  esecuzione via cursore DBAPI grezzo; (2) `metadata.value` era `NOT NULL`
  ma il seed inserisce `NULL` per `last_etl_run` — rimosso il vincolo;
  (3) `municipalities.geometry` era `GEOMETRY(POLYGON,4326)` ma 74/1180
  comuni reali sono `MULTIPOLYGON` (exclavi) — cambiato a `MULTIPOLYGON`,
  insert avvolto in `ST_Multi()`; (4) tutti i `CREATE INDEX` mancavano di
  `IF NOT EXISTS` (a differenza delle `CREATE TABLE`), rompendo la
  ri-esecuzione dello script su un DB parzialmente inizializzato — aggiunto
  a tutte le 24 occorrenze. Rimossa anche la chiamata a
  `insert_sample_province()` da `main()` (inseriva un record fittizio
  "Test Comune Piemonte" nella tabella `provinces` reale).

  **Risultato finale verificato nel DB**: 8 province (codici ISTAT corretti),
  1180 comuni reali, 0 geometrie invalide (`ST_IsValid`).

  Pagine aggiornate: `data-sources.md`, `data-model.md`, `etl-pipeline.md`,
  `config-reference.md`, `project-status.md` (item 3 della roadmap segnato
  fatto, aggiunta voce minore su population/elevation mancanti).

- **2026-07-04** — CARICAMENTO `temperature` (PUNTO 4, ULTIMO BUCO DELLA
  PIPELINE). `src/data_processing/clean_data.py` **non era mai stato
  eseguibile**: da `validate_temperature` in poi il file aveva newline
  letterali (`\n` testuali) invece di righe vere, un `SyntaxError`
  bloccava l'import. Riscritto da capo preservando la logica (il contenuto
  era leggibile, solo "srotolato" su una riga fisica). Prima esecuzione
  reale su `data/raw/temperature_data.csv`: sopravvivevano solo 10 righe su
  75.976 — bug trovato in `apply_quality_flags`: `quality_flag` viene
  valorizzata da `validate_temperature`/`detect_outliers` solo per le righe
  sospette *prima* che la colonna esista, quindi pandas la crea con `NaN`
  per tutte le altre; il filtro `quality_flag < 2` scarta anche quelle
  (`NaN < 2` è `False`). Fix: `df['quality_flag'] = 0` esplicito prima di
  `validate_temperature`. Ri-eseguito: 75.976/75.976 righe mantenute, 10
  flaggate (ondata di freddo febbraio 2012, non errori).

  Scritto `DatabaseLoader.insert_temperature()` in `load_to_db.py` (batch
  insert via `psycopg2.extras.execute_values`). Discussione con l'utente
  sulla granularità: i dati Open-Meteo sono per provincia (1 stazione =
  il capoluogo), ma `temperature.municipality_id` è `NOT NULL` — scelto
  (con l'utente) di associare ogni riga al **comune capoluogo di
  provincia**, lasciando gli altri 1172 comuni senza dati (alternativa
  scartata: rendere `municipality_id` nullable per un "livello
  provinciale"). Trovata un'eccezione nella mappatura nome-capoluogo:
  la provincia "Verbano-Cusio-Ossola" ha come capoluogo il comune di
  "Verbania" (nome diverso dalla provincia, a differenza delle altre 7).

  **Risultato finale verificato nel DB**: 75.976 righe in `temperature`,
  8 comuni capoluogo, range 2000-01-01/2025-12-31, `quality_flag` 0/1
  coerente, nessun record scartato. La pipeline Extract→Transform→Load è
  ora completa ed eseguita end-to-end su dati reali per la prima volta.

  Pagine aggiornate: `etl-pipeline.md` (sezioni Transform e Load, bug
  critici documentati), `project-status.md` (item 4 segnato fatto, righe
  Settimana 2 aggiornate, prossimi passi ridefiniti attorno a
  `identify_heatwaves()`/analisi ora che i dati reali ci sono).

- **2026-07-12** — `identify_heatwaves()` E VISTE KPI SU DATI REALI.
  Prima di eseguire la funzione sui 75.976 record reali, rilettura attenta
  del codice PL/pgSQL in `sql/01_init_database.sql` ha rivelato due bug di
  correttezza mai emersi (la funzione non era mai stata eseguita su dati
  veri): (1) quando la sequenza di giorni caldi si interrompeva per
  **cambio comune** (non solo buco di date), l'`INSERT` usava
  `municipality_id`/`province_id` della riga **nuova** invece che di quella
  a cui l'ondata conclusa apparteneva; (2) **nessun flush finale** — se
  l'ultimo comune elaborato terminava la serie durante un'ondata attiva,
  quell'ultima ondata non veniva mai salvata. Corretti entrambi con
  variabili di tracking dedicate (`v_municipality_id`/`v_province_id`) e un
  controllo esplicito dopo il loop.

  Il fix ha introdotto temporaneamente un terzo bug: le nuove variabili si
  chiamavano quasi come le colonne selezionate, causando
  `ERRORE: riferimento a colonna ambiguo` — risolto aggiungendo un alias di
  tabella esplicito nella query interna (`FROM temperature t`).

  Prima esecuzione "riuscita" (nessun errore) ma con **0 righe inserite**
  in `heatwave_events`, nonostante 406 giorni reali sopra i 35°C nel
  dataset. Causa: la funzione era stata invocata via
  `db_manager.execute_query()`, che usa `engine.connect()` **senza
  `commit()`** — side effect (gli `INSERT` fatti dalla funzione) annullati
  silenziosamente alla chiusura della connessione (comportamento di
  SQLAlchemy 2.0 senza transazione esplicita). Fix: invocata dentro
  `with db_manager.engine.begin() as conn: ...` (commit automatico).
  Verificato con un conteggio indipendente via SQL (window function
  `ROW_NUMBER()` per individuare i gap di date): 51 ondate reali attese, 51
  trovate — coincidenza esatta, inclusa la storica ondata dell'agosto 2003.
  Documentato il gotcha `execute_query`-non-committa in `architecture.md`
  per evitare di ripeterlo con altre funzioni PL/pgSQL in futuro.

  Rinfrescate anche le viste materializzate `kpi_annual_by_municipality` e
  `kpi_annual_by_province` (erano vuote, calcolate quando `temperature` non
  aveva ancora dati): 208 righe ciascuna (8 comuni/province × 26 anni).

  **Risultato finale verificato nel DB**: `heatwave_events` 51 righe,
  `kpi_annual_by_municipality`/`kpi_annual_by_province` 208 righe ciascuna.
  Tutta la catena dati → schema → KPI/ondate è ora reale e verificata.

  Pagine aggiornate: `data-model.md` (sezione `heatwave_events`, viste
  materializzate, bug della funzione documentati), `architecture.md`
  (gotcha `execute_query`/commit), `project-status.md` (Settimana 2
  completata, prossimi passi ridefiniti attorno a analisi/dashboard).

- **2026-07-15** — `src/analysis/` IMPLEMENTATA ED ESEGUITA SU DATI REALI
  (PUNTO 1 DELLA ROADMAP POST-ETL). Prima esecuzione mai fatta di analisi
  statistica/spaziale sui dati reali caricati nelle sessioni precedenti.
  Installate nuove dipendenze non ancora presenti (`pymannkendall`,
  `scikit-learn`, `statsmodels`), aggiunte a `requirements.txt`.

  Scritti ed eseguiti 4 moduli:
  - `trend_analysis.py` — Mann-Kendall + regressione lineare per comune su
    `temp_mean_annual`. Risultato: 7/8 comuni con trend di riscaldamento
    significativo (p<0.05), +0.4/+1.0 °C/decade; Asti borderline (p=0.098).
  - `heatwave_stats.py` — backfill di `heatwave_events.intensity_index`/
    `mean_temp` (lasciati `NULL` da `identify_heatwaves()`, mai calcolati
    finora) + statistiche aggregate per comune/anno. 2003 e 2019 emergono
    come gli anni con più ondate (11 e 9), coerente con le ondate di
    calore europee note di quegli anni.
  - `seasonal_analysis.py` — STL decomposition (statsmodels) sulla serie
    giornaliera per comune. Ampiezza stagionale reale ~28-32°C.
  - `spatial_analysis.py` — Moran's I (implementato a mano, no
    `libpysal`/`esda`, con test di significatività via permutazione) +
    clustering K-means in zone climatiche. Documentato esplicitamente il
    limite: solo 8 unità spaziali disponibili (i comuni capoluogo) è sotto
    la soglia comunemente considerata minima per un'analisi spaziale
    robusta — risultati (I=-0.096, p=0.73; 3 cluster geograficamente
    sensati) presentati come illustrativi, non conclusivi.

  Due bug minori trovati e corretti durante l'esecuzione: (1) `AVG()` di
  PostgreSQL su colonne intere restituisce `NUMERIC`/`Decimal`, in
  conflitto con le colonne `float` nelle operazioni pandas — fix: cast
  `::float` nella query SQL; (2) una bozza iniziale di
  `seasonal_analysis.py` interpolava il nome del comune in un f-string
  SQL (valore comunque fidato, da una query interna, ma pattern da
  evitare) — corretto in query parametrizzata.

  Creata nuova pagina `statistical-analysis.md` con il dettaglio di tutti
  e 4 i moduli, risultati reali e caveat statistici. Aggiornate anche
  `concepts.md` (ogni concetto ora marcato "implementato" con il
  risultato reale), `kpi-catalog.md`, `index.md`, `project-status.md`
  (Settimana 3 aggiornata, prossimi passi ridefiniti attorno a mappe
  GIS/dashboard).

- **2026-07-15** — DASHBOARD STREAMLIT IMPLEMENTATA ED ESEGUITA. Scritta
  la dashboard (`dashboard/app.py` + 4 pagine in `pages/` + componenti
  condivisi in `components/`) sui dati reali già caricati e sui risultati
  di `src/analysis/`. Scostamento deliberato dal piano
  (`PROJECT_SUMMARY.md`): niente `pages/01_home.py` separato — `app.py`
  stesso è la home (convenzione standard Streamlit); niente
  `components/charts.py` — grafici scritti direttamente nelle pagine.

  Scoperti e risolti 3 bug reali alla prima esecuzione:
  1. `ModuleNotFoundError: No module named 'components'` — Streamlit
     esegue gli script con `exec()`, non con l'invocazione standard di
     Python, quindi la cartella dello script non finisce automaticamente
     in `sys.path`. Fix: bootstrap esplicito (`sys.path.insert`) in cima a
     `app.py` e a ogni pagina.
  2. `folium.GeoJson()` non accetta WKT grezzo — tentava di aprirlo come
     percorso file (`OSError: Invalid argument`). Fix:
     `components/maps.py::wkt_to_geojson()` (shapely WKT → dict GeoJSON).
  3. `use_container_width` deprecato nella versione di Streamlit installata
     (1.58.0, già oltre la data di rimozione annunciata) — sostituito con
     `width='stretch'` in tutte le occorrenze.

  **Verifica end-to-end senza browser**: un `curl` sulla porta 8501
  restituiva 200 OK ma non prova nulla (Streamlit è un'app client-rendered,
  il markup HTML iniziale è solo il "guscio" statico). Usato invece
  `streamlit.testing.v1.AppTest`, che esegue davvero lo script in-process:
  tutte e 5 le pagine eseguite senza eccezioni, contenuto reale verificato
  (metriche home: 75.976 righe, 2000-2025, 8/1180 comuni, 51 ondate;
  tabella trend con valori coincidenti con `output/trend_analysis.csv`).
  Infine avviata live (`streamlit run dashboard/app.py --server.headless
  true --server.port 8501`), raggiungibile su `http://localhost:8501`
  (health check `/_stcore/health` → 200).

  Pagine aggiornate: `dashboard.md` (riscritta, struttura reale + bug +
  metodo di verifica via `AppTest`), `project-status.md` (Settimana 3
  completata salvo QGIS, prossimi passi ridefiniti attorno alle mappe GIS
  come ultimo pezzo pianificato mancante), `index.md`.

- **2026-07-15** — MAPPE QGIS GENERATE ED ESEGUITE (ULTIMO PEZZO DI
  SETTIMANA 3). Trovato QGIS 3.44.12 già installato
  (`C:\Program Files\QGIS 3.44.12`), con `python-qgis-ltr.bat` (Python
  bundled con PyQGIS) e `qgis_process-qgis-ltr.bat` disponibili — quindi,
  come per la dashboard, non solo scritti i file ciecamente ma costruiti e
  **verificati con render offscreen** (`QT_QPA_PLATFORM=offscreen` +
  `QgsMapRendererParallelJob` → PNG), invece di limitarsi a consegnare file
  mai aperti.

  Scritto `qgis_projects/build_maps.py` (PyQGIS) per generare i 3 progetti
  pianificati in `PROJECT_SUMMARY.md`: `temperature_heatmap.qgz`,
  `hotspot_analysis.qgz`, `evolution_animation.qgz`. Sfondo comune: tutti i
  1180 comuni in grigio (da `municipalities`), con gli 8 comuni capoluogo
  reali evidenziati a colori sopra — stessa scelta di onestà sulla
  granularità già adottata in dashboard e analisi.

  **Due bug reali trovati e risolti, entrambi con fallimento silenzioso
  (nessun errore Python visibile)**:
  1. Le prime anteprime mostravano solo lo sfondo grigio, nessun comune
     colorato: il renderer referenziava campi come
     `spatial_analysis_temp_mean_avg`, assumendo che
     `QgsVectorLayerJoinInfo` aggiungesse un prefisso — ma con
     `setPrefix('')` i campi joinati mantengono il nome originale
     (`temp_mean_avg`). Trovato ispezionando `layer.fields()` prima/dopo
     il join.
  2. Il layer temporale (mappa 3, basato su una subquery SQL passata come
     `table=` in `QgsDataSourceUri`) risultava sempre invalido, con
     `layer.error()` completamente vuoto — nessun indizio dalle normali
     API Python. Diagnosticato solo collegando un handler al message log
     di QGIS (`QgsApplication.messageLog().messageReceived`), che ha
     rivelato che QGIS mette tra virgolette l'**intera subquery** come se
     fosse un unico nome di tabella, producendo un errore Postgres
     (`la relazione "(SELECT ... non esiste`) mai esposto a Python. Fix:
     creata una vista Postgres reale (`kpi_temporal_view`, script dedicato
     `qgis_projects/create_temporal_view.py`, eseguito col venv del
     progetto) invece della subquery inline — una vista in catalogo si
     comporta come qualunque tabella, senza ambiguità di parsing.

  **Verifica del filtro temporale**: renderizzati due frame (2000 e 2025)
  e confrontati visivamente — differiscono chiaramente (2025 uniformemente
  più rosso/caldo), confermando che il time slider funziona davvero e
  riflette il riscaldamento reale già trovato in `trend_analysis.py`, non
  solo che il layer esiste.

  **Limite scoperto e non risolvibile in questa sessione**: l'ambiente Qt
  offscreen non ha alcun font di sistema registrato
  (`QFontDatabase().families()` vuoto) — le etichette dei comuni appaiono
  come rettangoli tratteggiati nelle anteprime PNG invece che testo.
  Isolato il problema con un test `QPainter` puro (stesso risultato senza
  QGIS coinvolto), quindi non è un bug della configurazione delle
  etichette nel progetto — è un limite del backend di rendering headless.
  Le etichette restano correttamente configurate nel file `.qgz`; vanno
  confermate aprendo i progetti in QGIS Desktop (unico aspetto di questa
  sessione non verificabile in automatico).

  Pagine aggiornate: `gis-maps.md` (riscritta, stato reale + entrambi i
  bug + limite del font documentati), `project-status.md` (Settimana 3
  completa su tutti e 3 i pezzi principali — analisi, dashboard, mappe —
  prossimi passi ridotti a voci minori/rifiniture), `index.md`.

- **2026-07-15** — FIX PAGINA BIANCA IN QGIS DESKTOP. L'utente ha aperto i
  3 `.qgz` in QGIS Desktop e ha segnalato una pagina bianca (il render
  offscreen delle anteprime PNG non aveva rivelato il problema, perché
  imposta l'estensione solo su `QgsMapSettings`, transiente, non su ciò
  che viene effettivamente salvato nel progetto). Causa reale: `QgsProject
  .write()` non salva alcuna estensione di vista (`DefaultViewExtent`) a
  meno di impostarla esplicitamente — verificato ispezionando l'XML dentro
  il `.qgz` (nessun `<mapcanvas>`/`DefaultViewExtent` presente). Fix:
  nuova funzione `set_project_view_extent()` in `build_maps.py`, che
  imposta `project.viewSettings().setDefaultViewExtent(...)`
  sull'estensione combinata dei layer per ciascuno dei 3 progetti, prima
  di salvarli. Rieseguito `build_maps.py`; verificato che l'XML del
  `.qgz` ora contenga `DefaultViewExtent` coi confini reali del Piemonte
  (non più assente); anteprime PNG ri-verificate, invariate/corrette.

  Pagina aggiornata: `gis-maps.md` (nuovo bug documentato nella lista).

- **2026-07-15** — FIX ETICHETTE MANCANTI IN `evolution_animation.qgz`.
  L'utente ha confermato che i nomi dei comuni si vedono correttamente in
  `temperature_heatmap.qgz` e `hotspot_analysis.qgz` (font quindi OK in
  QGIS Desktop reale, il problema visto nelle anteprime era davvero solo
  dell'ambiente offscreen), ma non nel terzo file. Causa: non un bug di
  rendering, semplicemente `add_labels()` non era mai stata chiamata sul
  layer temporale in `build_evolution_animation()` — dimenticanza in fase
  di scrittura, non un difetto di configurazione. Fix: aggiunta la
  chiamata con espressione `"name" || ' (' || round("temp_mean_annual", 1)
  || '°C)'`, così la temperatura in etichetta cambia insieme al colore a
  ogni anno dell'animazione. Rieseguito `build_maps.py`; verificato
  leggendo l'XML del `.qgz` salvato che il nodo `<labeling type="simple">`
  sia ora presente (prima assente).

  Pagina aggiornata: `gis-maps.md`.

- **2026-07-15** — DASHBOARD RESA PIÙ LEGGIBILE PER NON ADDETTI AI LAVORI.
  Richiesta esplicita dell'utente: rendere il sito comprensibile anche a
  chi non conosce il progetto, non solo a chi ha letto la wiki. Aggiunto
  a tutte e 5 le pagine un riquadro introduttivo `st.expander("ℹ️ Come si
  legge questa pagina")` con spiegazioni in linguaggio semplice dei metodi
  usati (Mann-Kendall, regressione lineare, STL, K-means, indice di Moran,
  definizione di ondata di calore), più didascalie (`st.caption`) sotto le
  metriche e i grafici principali che ne riassumono il significato pratico
  invece di lasciare solo il numero/etichetta tecnica. Nella pagina Analisi
  Spaziale, l'indice di Moran ora ha anche un'interpretazione discorsiva
  (`st.success`/`st.info` a seconda della significatività), non solo il
  valore numerico. Nella pagina Download Dati, ogni file ha una
  descrizione di cosa contiene, non solo il nome tecnico. Nessuna modifica
  a query/logica dati — solo testo esplicativo. Verificato con
  `streamlit.testing.v1.AppTest` che tutte e 5 le pagine eseguano ancora
  senza eccezioni dopo le modifiche; server live riavviato su
  `localhost:8501`.

  Pagina aggiornata: `dashboard.md`.

- **2026-07-15** — DUE RIFINITURE MINORI: FIX LOGGING + ALLINEAMENTO
  REQUIREMENTS. Su richiesta dell'utente, risolte le due voci più rapide
  rimaste nella lista dei prossimi passi:
  1. `logging.format` in `config.yaml` corretto dalla sintassi stdlib
     `%(asctime)s...` (mai compatibile con loguru, bug noto da inizio
     wiki il 2026-07-04) alla sintassi loguru corretta — lo stesso valore
     già usato come default di fallback in `src/utils/logger.py`. Log di
     console e file finalmente leggibili; verificato con un test diretto.
  2. `requirements.txt` riallineato alle versioni realmente installate nel
     `.venv` (drift esistente sin dall'inizio del progetto: pandas
     2.1.4→3.0.3, numpy 1.26→2.4, scipy, sqlalchemy, geopandas, shapely,
     pyproj, requests, cdsapi, netCDF4, xarray, matplotlib, plotly,
     seaborn, folium, streamlit 1.29→1.58, streamlit-folium, pyyaml,
     python-dotenv, tqdm, loguru, pytest, pytest-cov, black, flake8, mypy,
     pylint — praticamente ogni pacchetto). Verificato `pip check`: nessun
     conflitto nell'ambiente attuale.

  Pagine aggiornate: `data-sources.md` (bug logging segnato risolto),
  `dashboard.md` (nota sul drift dei requirements aggiornata),
  `project-status.md` (entrambe le voci rimosse dalla lista prossimi
  passi, aggiunta nota sul fix).

- **2026-07-15** — ESTENSIONE A 44 COMUNI (RENDERE MORAN'S I/CLUSTERING
  ROBUSTI). Richiesta esplicita dell'utente: il campione di 8 comuni per
  le analisi spaziali era troppo piccolo (sotto la soglia comune di 20-30
  unità). Concordato con l'utente (via domande di scoping): estendere solo
  le temperature (non i metadati demografici, rimandati), con ~30-40
  comuni extra.

  **Selezione**: nuovo script `src/data_acquisition/download_extra_municipalities.py`
  — campionamento "farthest-point" per provincia (sceglie comuni che
  massimizzano la distanza minima dai punti già presenti, per coprire zone
  diverse invece di ammassarsi), 36 comuni extra allocati proporzionalmente
  alla dimensione di ciascuna provincia (9 Torino, 7 Cuneo, 6 Alessandria,
  4 Asti, 3 Novara, 3 Vercelli, 2 Biella, 2 Verbano-Cusio-Ossola).

  **Download**: refactoring di `WeatherDataDownloader.download_historical_data()`
  in `download_data.py` — estratta la logica di retry/backoff in un nuovo
  metodo `download_for_coordinates(name, lat, lon)` che accetta coordinate
  arbitrarie, non solo gli 8 capoluoghi hardcoded. 31/36 comuni scaricati al
  primo giro; 5 falliti per `ConnectionResetError`/TLS reset (non un `429`,
  quindi non coperto dal retry esistente) — ri-scaricati con una seconda
  passata mirata. Risultato: 36/36, 341.892 righe.

  **Bug di encoding storico scoperto per caso**: durante il download, 2 nomi
  (Rorà, Cavaglià) sono usciti corrotti. Indagine ha rivelato che il fix di
  encoding del 2026-07-04 (`encoding='cp1252'` per leggere lo shapefile
  ISTAT) era **sbagliato fin dall'inizio** — verificato a livello di byte
  (`nome.encode('utf-8')`) che produceva una doppia codifica UTF-8 per
  ogni nome accentato, e che la verifica originaria (stampa a terminale)
  era stata ingannata da un mojibake che sembrava corretto per coincidenza.
  Il file `.dbf` ISTAT è in realtà UTF-8, non cp1252. Corretti: lo script
  (`encoding='utf-8'`), i 28 comuni su 1180 già corrotti nel DB (100% di
  quelli con caratteri accentati, `UPDATE` via `istat_code` come chiave
  stabile), e `data/external/municipalities.csv` (rigenerato).

  **Pulizia**: `DataCleaner` riusato senza modifiche (raggruppa per
  colonna `province`, che qui contiene il nome del comune — funziona
  perché ogni nome è univoco tra i 36 selezionati). 341.892/341.892 righe
  mantenute, 670 outlier statistici (prevalentemente comuni alpini).

  **Caricamento**: nuovo metodo `insert_temperature_for_municipalities()`
  in `load_to_db.py` (variante che usa `municipality_id` già noto, non
  serve risolvere il capoluogo per nome). Temperature totali: 417.868
  righe, 44 comuni.

  **Ricalcolo a valle**: `identify_heatwaves()` non è idempotente —
  `TRUNCATE TABLE heatwave_events` prima di rieseguirla (sicuro, dato
  interamente derivato) per evitare di duplicare le 51 ondate già trovate.
  Risultato: 145 ondate su 44 comuni. Viste materializzate rinfrescate
  (`kpi_annual_by_municipality` ora 1144 righe). Rieseguiti tutti e 4 i
  moduli di `src/analysis/` (nessuna modifica di codice necessaria, tranne
  aggiornare testo/commenti hardcoded su "8 comuni" in `spatial_analysis.py`).

  **Risultato più significativo**: Moran's I passa da **-0.096 (p=0.732,
  non significativo, n=8)** a **0.101 (p=0.002, statisticamente
  significativo, n=44)** — i comuni geograficamente vicini hanno
  temperature realmente più simili di quanto atteso per caso. Il
  clustering K-means è ora visivamente nitido: cluster alpino (3.8°C,
  margini montani nord/sud-ovest), cluster di pianura calda (12.9°C,
  centro-est), cluster intermedio (11.1°C) — confermato anche visivamente
  nella mappa QGIS rigenerata.

  **Rigenerato tutto a valle**: i 3 progetti QGIS (`build_maps.py`,
  verificati con render PNG — pattern geografico dei cluster ora molto più
  leggibile con 44 punti invece di 8) e tutte e 5 le pagine dashboard
  (testi con "8 comuni" aggiornati a "44 comuni" in `app.py`,
  `03_analisi_spaziale.py`, `04_ondate_di_calore.py`,
  `components/queries.py`; il messaggio di Moran's I ora mostra
  `st.success` invece di `st.info`, dato che il risultato è diventato
  significativo). Verificato con `AppTest`, server live riavviato.

  Bug minore incontrato e corretto: `UnicodeEncodeError` ripetuto su
  console Windows per i caratteri "✓"/"✗" nei log (cp1252 non li supporta)
  — fix in `src/utils/logger.py` con `sys.stdout.reconfigure(encoding=
  'utf-8')`.

  Pagine aggiornate: `data-sources.md`, `etl-pipeline.md`, `data-model.md`,
  `statistical-analysis.md` (riscrittura sostanziale della sezione Moran's
  I/clustering), `gis-maps.md`, `dashboard.md`, `project-status.md`.

- **2026-07-15** — TEST UNITARI (`tests/`). Su richiesta esplicita
  dell'utente, creata la prima suite di test del progetto (`tests/` era
  vuota da inizio wiki). Creati `tests/__init__.py`, `pytest.ini`
  (`testpaths = tests`), e 3 file di test: `test_data_cleaning.py` (15
  test su `DataCleaner`, `src/data_processing/clean_data.py`),
  `test_analysis.py` (11 test sulle funzioni pure di `src/analysis/*.py`:
  Mann-Kendall, regressione lineare, haversine, pesi spaziali, indice di
  Moran, clustering K-means, aggregazioni ondate di calore), `test_config.py`
  (5 test su `Config.get()`/`get_database_url()`, incluso un test di
  regressione sulla precedenza env-vars/yaml già risolta il 2026-07-04).
  Scelta deliberata: solo unit test puri, nessuno tocca DB o rete (dati
  sintetici costruiti a mano) — l'intera suite gira in ~5 secondi.

  **Bug reale trovato dalla suite alla prima esecuzione** (non un test
  scritto per confermare un comportamento noto, ma uno che ha effettivamente
  fallito): `test_bad_rows_are_dropped_good_rows_survive`, un dataset
  sintetico con una riga fuori range fisico (`temp_max=999`), falliva
  perché quella riga sopravviveva alla pipeline invece di essere scartata.
  Causa: in `DataCleaner.detect_outliers()`
  (`src/data_processing/clean_data.py`), che gira *dopo*
  `validate_temperature()` (la quale aveva già segnato la riga
  `quality_flag=2`, bad), l'assegnazione del flag IQR (`quality_flag=1`,
  suspect) era incondizionata — **declassava** a 1 anche righe già a 2,
  che poi sopravvivevano ad `apply_quality_flags()` (scarta solo `>= 2`).
  Fix: `df.loc[is_outlier & (df['quality_flag'] < 2), 'quality_flag'] = 1`
  (declassa solo se il flag attuale è ancora `< 2`). Verificato che il bug
  non ha mai avuto impatto sui dati reali già caricati (0 righe fuori range
  fisico sia in `temperature_data.csv` che in `temperature_data_extra.csv`,
  quindi la precondizione del bug — riga contemporaneamente bad e outlier
  IQR — non si è mai verificata finora), ma resta un bug di correttezza
  reale ora corretto e coperto da test di regressione.

  Ri-eseguita l'intera suite dopo il fix: 31/31 test passati. Eseguita
  anche con `--cov=src.data_processing --cov=src.analysis
  --cov=src.utils.config --cov-report=term-missing`: 86% di copertura su
  `clean_data.py`, 57% complessivo sui moduli inclusi nel report (atteso,
  dato che le funzioni che leggono da DB/rete non sono testate per scelta).

  Creata nuova pagina `testing.md` (cosa è coperto, il bug trovato/corretto
  in dettaglio, limiti espliciti — nessun test per `load_to_db.py`,
  `download_data.py`, `seasonal_analysis.py`, `src/visualization/`).
  Aggiornate `etl-pipeline.md` (sezione Transform, nota su ordine
  validate/detect_outliers e bug corretto), `index.md` (nuova sezione
  "Qualità del codice"), `project-status.md` (riga "Test unitari" in
  Settimana 3 segnata fatta con dettaglio, punto 6 dei prossimi passi
  segnato fatto).

- **2026-07-15** — AMPLIAMENTO CONTENUTO DELLE 3 PAGINE DI ANALISI DELLA
  DASHBOARD + FILTRI GLOBALI. Su richiesta esplicita e dettagliata
  dell'utente (specifica puntuale per ciascuna pagina + requisiti
  trasversali di UI/UX), ampliato sostanzialmente il contenuto di
  `02_analisi_temporale.py`, `03_analisi_spaziale.py`,
  `04_ondate_di_calore.py`, oltre a `app.py` (home) e a due nuovi moduli
  condivisi.

  **Nuovi componenti condivisi**:
  - `components/constants.py` — palette coerente (scala sequenziale
    `RdYlBu_r` per temperature assolute, divergente `RdBu_r` centrata sullo
    zero per trend/anomalie, da non confondere tra loro), soglie fasce
    altitudinali (300/700 m), set dei capoluoghi, valori di riferimento
    nazionale/globale (IPCC AR6, ISPRA — dichiarati come letteratura, non
    calcolati dal progetto).
  - `components/filters.py` — sidebar comune (intervallo anni + provincia),
    persistita tra le pagine via `st.session_state` (Streamlit esegue ogni
    pagina come script indipendente, i widget non sono condivisi
    automaticamente).
  - `components/heatwave_definitions.py` — `identify_heatwaves_percentile()`,
    definizione alternativa di ondata di calore a soglia percentile
    (relativa al singolo comune), usata solo a scopo di confronto
    metodologico (vedi decisione sotto).

  **Decisione di scoping 1 — elevazione reale**: la richiesta di un
  confronto per fascia altitudinale (pianura/collina/montagna) richiedeva
  `municipalities.elevation_m`, mai popolato (sempre `NULL`, voce aperta in
  `project-status.md` da settimane). Chiesto esplicitamente all'utente se
  scaricare il dato reale o mostrare un placeholder "non disponibile" —
  scelto il dato reale. Scritto `src/data_acquisition/fetch_elevation.py`:
  centroide di ciascun comune via PostGIS (`ST_Centroid`), interrogata la
  Open-Meteo Elevation API (stessa piattaforma delle temperature, nessuna
  chiave, endpoint diverso: `api.open-meteo.com/v1/elevation`) in
  un'unica richiesta batch per i 44 comuni con dati, risultati scritti in
  `municipalities.elevation_m`. Eseguito realmente: da Torino (256 m) a
  Formazza (2250 m), coerente con la geografia nota del Piemonte.

  **Decisione di scoping 2 — definizione di ondata di calore**: la
  richiesta chiedeva di "implementare una funzione per identificare le
  ondate di calore" con soglia percentile. Il progetto ha già una
  definizione canonica (`identify_heatwaves()` nel DB, soglia fissa
  35°C/3gg) usata ovunque nel resto del sito (145 ondate in home,
  statistiche per comune, mappe QGIS) — sostituirla avrebbe reso
  incoerenti tutti quei numeri. Scelta: la soglia percentile è
  implementata come funzione pura, usata **solo** nel tab "Dettaglio
  tecnico" della pagina Ondate di Calore come confronto illustrativo per
  il comune selezionato, senza toccare il database.

  **Estensione a `heatwave_stats.py`**: `frequency_by_year()` ora include
  anche `avg_duration_days`/`avg_intensity` per anno (prima solo il
  conteggio), necessario per il grafico a barre a doppio asse richiesto
  nella pagina Ondate di Calore. Rieseguito, CSV rigenerato.

  **Contenuto aggiunto per pagina** (dettaglio completo in
  `wiki/pages/dashboard.md`): Analisi Temporale — anomalie con baseline
  configurabile, confronto stagionale (4 stagioni meteorologiche), boxplot
  per quinquennio, widget di confronto con letteratura, tab
  Panoramica/Dettaglio tecnico; Analisi Spaziale — mappa coropletica per
  provincia (confine reale via `ST_Union` PostGIS su tutti i 1180 comuni),
  mappa del trend per comune (colormap divergente), fasce altitudinali,
  isola di calore urbana (Torino vs comuni rurali della sua provincia),
  tab Panoramica/Dettaglio tecnico (cluster K-means e Moran's I spostati
  qui); Ondate di Calore — conteggio cumulato, mappa di concentrazione
  geografica, heatmap "calendario" (anno × giorno dell'anno), confronto
  soglia percentile; Home — 3 card di navigazione (`st.page_link`) al
  posto dei link testuali, sidebar filtri applicata anche a mappa e
  tabella trend esistenti.

  **Verifica**: tutte le pagine compilate (`py_compile`) e verificate con
  `streamlit.testing.v1.AppTest`, incluse esecuzioni con stati non
  di default (provincia Torino esclusa dal filtro → ramo isola di calore
  "dati insufficienti"; intervallo di un solo anno → ramo pendenza "n/d";
  comune di montagna con soglia percentile diversa) — nessuna eccezione in
  nessun caso. Server live riavviato e verificato (`/_stcore/health` → 200).

  Pagine aggiornate: `dashboard.md` (riscrittura sostanziale), `data-model.md`
  (`elevation_m` popolato per i 44 comuni), `data-sources.md` (nuovo
  endpoint Open-Meteo Elevation API), `statistical-analysis.md`
  (`frequency_by_year()` estesa), `project-status.md`.

- **2026-07-15** — RINOMINATA LA PAGINA PRINCIPALE `app.py` → `Home.py`.
  Richiesta esplicita dell'utente: "dobbiamo trovare un altro nome per la
  pagina principale, non si può chiamare app". Rinominato con `git mv`
  (storia Git preservata) `dashboard/app.py` → `dashboard/Home.py`, che è
  anche la convenzione più diffusa nelle app Streamlit multipage (più
  descrittivo di un generico "app"). Aggiornati i riferimenti nel
  docstring del file stesso e in `dashboard/components/__init__.py`.

  **Non toccati** `README.md`/`PROJECT_SUMMARY.md`/`docs/*.md`: per
  `CLAUDE.md` sono sorgenti di pianificazione immutabili, quindi citano
  ancora `streamlit run dashboard/app.py` — ora stale, comando corretto
  `streamlit run dashboard/Home.py`. Le voci storiche di questo stesso log
  che citano `app.py` (2026-07-15, sessioni precedenti) non sono state
  riscritte: erano corrette nel momento in cui sono state scritte (il file
  si chiamava davvero così), coerente con la natura append-only di questo
  log.

  Verificato con `streamlit.testing.v1.AppTest` sul nuovo path (nessuna
  eccezione), server live riavviato su `dashboard/Home.py`
  (`/_stcore/health` → 200).

  Pagina aggiornata: `dashboard.md` (percorsi, nota sulla rinomina,
  chiarimento sulla staleness dei documenti di pianificazione).

- **2026-07-15** — PULIZIA PROCESSI STREAMLIT RESIDUI. Dopo il rename
  `app.py` → `Home.py`, l'utente segnalava di vedere ancora in browser
  `FileNotFoundError: dashboard\app.py` nonostante il server fosse stato
  riavviato. Diagnosticato con `Get-CimInstance Win32_Process | Where
  CommandLine -match streamlit` (mostra la command line completa per PID):
  **4 processi Streamlit** erano rimasti vivi sulla porta 8501 da sessioni
  di verifica precedenti, due dei quali puntavano ancora al vecchio
  `app.py` — un tentativo di stop precedente ne aveva chiuso solo uno.
  Windows permetteva a più processi di restare "in ascolto" sulla stessa
  porta contemporaneamente (visibile con più righe `LISTENING` in
  `netstat`), quindi il browser si collegava a caso a uno dei quattro.
  Risolto terminando tutti i PID trovati e avviandone uno solo pulito,
  verificato con `Get-NetTCPConnection -LocalPort 8501` (un solo
  `OwningProcess`).

  Pagina aggiornata: `dashboard.md` (nuovo bug documentato nella lista).

- **2026-07-15** — ETICHETTE MANN-KENDALL LEGGIBILI + TEMA/RIFINITURE
  ESTETICHE. Due richieste in sequenza dell'utente sulla stessa area:
  prima "perché no trend?" (la stringa grezza `'no trend'` di
  `pymannkendall` si legge come "clima stabile", mentre significa "il test
  non trova abbastanza evidenza di un trend con 26 anni di dati" — un
  limite del test, non un fatto sul clima), poi "estetica bruttissima,
  non si vede nemmeno per intero 'nessun trend chiaro', viene tagliato".

  **Etichette leggibili**: aggiunta `format_mk_trend()` +
  `MK_TREND_LABELS` in `components/constants.py`
  (`increasing`→"📈 In aumento", `decreasing`→"📉 In diminuzione",
  `no trend`→"🔍 Nessun trend chiaro"), applicata ovunque appare
  `mk_trend`: metrica in alto e tab Dettaglio tecnico di
  `02_analisi_temporale.py`, tabella comparativa in `Home.py`. Bug in
  corso d'opera: dimenticato l'import di `format_mk_trend` in `Home.py`
  (`NameError` alla prima esecuzione, segnalato dall'IDE) — l'utente ha
  chiesto di fermarsi per capire cosa stessi facendo (interruzione
  legittima, non un errore da correggere silenziosamente); spiegato lo
  stato e, con l'ok esplicito a continuare, sistemato l'import mancante.

  **Causa reale del testo tagliato**: non un limite delle etichette
  scelte, ma CSS di `st.metric` (`white-space: nowrap` + `text-overflow:
  ellipsis` sul valore, pensato per numeri corti) che troncava qualunque
  valore testuale più lungo della colonna — capitava anche a nomi di
  comune come "Verbano-Cusio-Ossola" nelle metriche della pagina Analisi
  Spaziale, non solo alle nuove etichette. Fix mirato in nuovo
  `components/styling.py::inject_custom_css()`: `white-space: normal` sul
  selettore `[data-testid="stMetricValue"]`, così il testo va a capo
  invece di sparire. Il selettore è stato **verificato esistere davvero**
  in Streamlit 1.58.0 (grep nei bundle JS installati in
  `.venv/Lib/site-packages/streamlit/static/`), non indovinato dalla
  documentazione generica.

  **Tema**: creato `.streamlit/config.toml` (nuovo, prima assente) con un
  tema Streamlit nativo invece di CSS sparso — palette coerente (blu
  `#2563eb` primario), supporto chiaro/scuro, angoli arrotondati
  (`baseRadius`), bordo sui widget, `chartCategoricalColors` allineata a
  `components/constants.py`. Tutte le chiavi usate sono state verificate
  una per una contro `.venv/Lib/site-packages/streamlit/config.py`
  dell'installazione reale (alcune, come `baseRadius`/`showWidgetBorder`/
  `chartCategoricalColors`/`[theme.dark]`, sono relativamente recenti e
  non garantite in versioni più vecchie di Streamlit). Deliberatamente
  **non** cercati selettori CSS per le card della home
  (`st.container(border=True)`): Streamlit le renderizza con classi
  generate dinamicamente (`st-emotion-cache-*`), non un `data-testid`
  stabile — il loro stile arriva comunque dal tema (`baseRadius`/
  `borderColor`), senza bisogno di CSS fragile.

  **Verifica**: `py_compile` + `AppTest` su tutte le pagine (nessuna
  eccezione); server riavviato per far effetto (i cambi a
  `config.toml` richiedono un riavvio completo, non li applica l'hot
  reload di Streamlit) e verificato un solo processo in ascolto sulla
  porta 8501.

  Pagina aggiornata: `dashboard.md` (nuove sezioni "Etichette leggibili
  per l'esito di Mann-Kendall" e "Tema e rifiniture estetiche", struttura
  cartelle aggiornata con `styling.py` e `.streamlit/config.toml`).

- **2026-07-15** — BASELINE DELLE ANOMALIE: DA CONFIGURABILE A FISSA +
  TESTO ESPLICATIVO. L'utente ha chiesto a cosa servissero i due
  `number_input` "Inizio baseline"/"Fine baseline" nella pagina Analisi
  Temporale; dopo la spiegazione, ha fatto notare che lasciarla
  configurabile non ha senso per lo scopo della pagina (capire il
  fenomeno, non esplorare scenari) e ha chiesto un parere esplicito prima
  di procedere. Confermato d'accordo con l'osservazione: rimossi i due
  widget in `02_analisi_temporale.py`, baseline ora fissa al primo
  decennio disponibile per il comune selezionato (non varia più per
  scelta dell'utente, resta scelta di continuità coi commenti nel codice
  già presenti). Sostituita la breve didascalia con un paragrafo esplicito
  che copre, nell'ordine: cos'è un'anomalia, come si calcola, perché
  quella baseline e non un'altra (dato che 1961-1990/1991-2020 — i
  riferimenti convenzionali in climatologia — non sono disponibili, dato
  che la serie parte dal 2000), come leggere le barre rosse/blu.
  Aggiornata anche la nota di metodologia nel tab Dettaglio tecnico dello
  stesso file (non più "modificabile a mano").

  Verificato con `py_compile` + `AppTest` (nessuna eccezione); il server
  live ha ricaricato la modifica da solo (a differenza del tema, un
  cambio a un file `.py` non richiede riavvio).

  Pagina aggiornata: `dashboard.md` (nuova sezione "Baseline delle
  anomalie: da configurabile a fissa").

- **2026-07-15** — TORINO COME COMUNE DI DEFAULT + FIX `NameError` DA
  MODIFICA MANUALE. Due interventi rapidi in sequenza sulla pagina Analisi
  Temporale. (1) L'utente ha chiesto che alla prima apertura della pagina
  il comune preselezionato fosse Torino invece del primo in ordine
  alfabetico (Acceglio): aggiunto `index=names.index('Torino')` (con
  fallback a `0` se assente dal filtro provincia attivo) allo `st.selectbox`
  — verificato con `AppTest` che `sb.value == 'Torino'`. (2) L'utente ha
  poi modificato di sua iniziativa il testo esplicativo della baseline
  (espandendolo, in modo migliore), ma introducendo per errore tre nomi di
  variabili mai definiti nel file (`anno_inizio_baseline`,
  `anno_fine_baseline`, `anno_corrente` — copiati probabilmente da una
  bozza con nomi diversi da quelli usati nel codice reale,
  `baseline_years_available`/`baseline_end`/`last_year`), causando un
  `NameError` che impediva l'esecuzione dell'intera pagina. Diagnosticato
  in un secondo con `AppTest` (traceback completo con numero di riga
  esatto), corretto sostituendo i tre nomi con quelli reali senza toccare
  il testo. Verificato che l'intera pagina esegua di nuovo senza eccezioni.

- **2026-07-15** — OPZIONE AGGREGATA "PIEMONTE" NELLA PAGINA ANALISI
  TEMPORALE. Richiesta esplicita dell'utente: poter calcolare l'intero
  Piemonte (non solo un comune alla volta) sulla base dei dati già
  disponibili. Aggiunta una voce in cima al selettore "Comune":
  `🌍 Piemonte — media di N comuni filtrati` (N riflette il filtro
  provincia della sidebar, non è fisso a 44) — selezionandola, ogni
  grafico/metrica della pagina si ricalcola sulla **media aritmetica non
  pesata** dei comuni filtrati invece che su un singolo comune, con un
  `st.info` che chiarisce esplicitamente non essere una stima ufficiale
  della temperatura regionale (mancano pesi per area/popolazione e la
  copertura è solo 44/1180 comuni).

  **Nuove query** in `components/queries.py`: `get_daily_temperature_aggregate()`
  (media giornaliera via `AVG()` SQL su `temperature`, filtrata per lista
  di comuni con `IN` a parametro espandibile — `bindparam(..., expanding=True)`,
  necessario perché SQLAlchemy non accetta di default una lista Python come
  singolo parametro `:names` in una clausola `IN`) e
  `get_seasonal_decomposition_aggregate()` (STL calcolata al volo con la
  stessa funzione pura `decompose()` di `src/analysis/seasonal_analysis.py`,
  dato che non esiste un CSV precalcolato per un aggregato che non
  corrisponde a un singolo comune).

  **Trend canonico per l'aggregato**: `trend_analysis.csv` ha una riga per
  comune, non per un aggregato arbitrario — per l'opzione Piemonte,
  Mann-Kendall e regressione sull'intero periodo sono ricalcolati al volo
  importando direttamente `mann_kendall_trend()`/`linear_trend()` da
  `src/analysis/trend_analysis.py` (stesse funzioni pure usate per
  generare il CSV), non reimplementati da capo — garantisce identica
  metodologia tra CSV precalcolato e calcolo al volo. Introdotto un dict
  `trend_info`/flag `has_trend_info` che unifica l'accesso ai risultati
  (proveniente da una riga di CSV o da un calcolo fresco) in tutto il
  resto della pagina, senza duplicare la logica delle metriche/tab.

  **Verifica**: `AppTest` sia con selezione di default (Torino) sia con
  l'aggregato Piemonte selezionato (nessuna eccezione in entrambi i casi),
  ripetuto anche con il filtro provincia sidebar ristretto a una sola
  provincia (Cuneo, 8 comuni) per controllare che l'aggregato si adatti
  correttamente al sottoinsieme filtrato (trend Mann-Kendall "in aumento",
  p=0.0011, pendenza periodo selezionato +0.50°C/decade — risultato
  plausibile, non verificato però contro un calcolo indipendente esterno).

  Pagina aggiornata: `dashboard.md` (nuova sezione "Opzione aggregata
  'Piemonte'" dentro la descrizione della pagina Analisi Temporale).

- **2026-07-15** — OPZIONE "PIEMONTE" SPOSTATA IN UNA CHECKBOX SEPARATA.
  L'utente ha chiesto una casella a parte per selezionare l'intero
  Piemonte, invece che una voce in cima allo stesso menu a tendina dei
  comuni. Rimossa la voce `🌍 Piemonte — media di N comuni filtrati` dalle
  opzioni di `st.selectbox`; aggiunta una `st.checkbox("🌍 Intero
  Piemonte")` in una colonna a fianco, che quando attiva disabilita (non
  nasconde) lo `st.selectbox` del comune — scelta per rendere visibile
  che le due scelte sono mutuamente esclusive, senza far scomparire un
  controllo che l'utente potrebbe cercare. `is_aggregate` ora viene
  direttamente dalla checkbox invece che da un confronto testuale con
  un'etichetta placeholder nella lista. Aggiustato un riferimento residuo
  alla vecchia costante `AGGREGATE_LABEL` (rimossa) in favore di
  `subject_label`. Verificato con `AppTest`: selectbox abilitato/Torino
  selezionato di default, disabilitato e pagina ricalcolata sull'aggregato
  quando la checkbox viene attivata, nessuna eccezione in nessuno dei due
  stati.

  Pagina aggiornata: `dashboard.md` (sezione "Opzione aggregata
  'Piemonte'" corretta per riflettere la checkbox invece della voce nel
  menu a tendina).

- **2026-07-15** — FILTRI: DA SIDEBAR GLOBALE A WIDGET INLINE PER PAGINA.
  L'utente ha segnalato che i filtri nella sidebar sembravano inutili
  ("non so cosa possiamo aggiungere a lato") e ha chiesto di rimuoverli,
  mettendoli solo nelle sezioni dove servono davvero. Rimossa
  `render_sidebar_filters()` da `components/filters.py` e da ogni pagina;
  sostituita con due funzioni pensate per essere richiamate inline, con
  una `key` univoca per pagina (non serve più gestire `st.session_state` a
  mano: senza uno stato condiviso tra pagine, Streamlit persiste da solo
  il valore di un widget tramite `key` per tutta la sessione):
  `render_year_range_filter(key)` e `render_province_filter(key)`.

  **Decisioni pagina per pagina** (non un'applicazione meccanica a tutte):
  - `Home.py`: nessun filtro — rimossi `provinces`/`year_start`/`year_end`
    e i due `.isin(provinces)` che filtravano mappa e tabella trend;
    mostra sempre tutti i 44 comuni (una pagina di overview non trae
    beneficio da un filtro).
  - `02_analisi_temporale.py`: tenuto solo l'intervallo anni (l'unico
    usato davvero: regressione, anomalie, stagioni, boxplot), spostato
    sotto la riga comune/checkbox Piemonte, con didascalia che chiarisce
    cosa filtra e cosa no (Mann-Kendall/STL restano sull'intero periodo).
    Rimosso il filtro provincia: serviva solo a restringere la lista dei
    44 comuni nel menu a tendina, beneficio marginale — la lista ora è
    sempre completa (`get_municipality_names_with_data()`).
  - `03_analisi_spaziale.py` e `04_ondate_di_calore.py`: tenuti entrambi i
    filtri (anni e provincia), spostati inline in due colonne in cima alla
    pagina — qui hanno un uso reale e diretto (mappe coropletiche, fasce
    altitudinali, isola di calore, mappa di concentrazione ondate,
    frequenza/intensità per periodo).
  - `05_download_dati.py`: invariata, nessun filtro (i CSV scaricabili
    sono completi, un filtro non avrebbe effetto).

  Verificato con `AppTest` su tutte le pagine (nessuna eccezione), incluso
  con stati non di default (provincia ristretta a "Torino" e intervallo
  anni ridotto a un solo anno su Analisi Spaziale/Ondate di Calore).
  Server live verificato ancora in salute dopo le modifiche.

  Pagina aggiornata: `dashboard.md` (sezione "Filtri: da sidebar globale a
  inline per pagina" riscritta, struttura cartelle e descrizioni delle
  singole pagine aggiornate per rimuovere i riferimenti alla sidebar).

- **2026-07-16** — LEGENDA A FASCE PER LE MAPPE DI ANALISI SPAZIALE.
  Richiesta esplicita dell'utente: per ogni colore delle mappe, indicare
  range numerico e gravità. Le due mappe (temperatura media per provincia,
  velocità di riscaldamento per comune) usavano `branca.colormap.LinearColormap`
  senza alcuna legenda visibile — l'utente doveva indovinare cosa
  rappresentasse una sfumatura di colore. Aggiunta
  `components/maps.py::render_gradient_legend()`: non la legenda
  automatica di branca (`colormap.add_to(m)`, un gradiente continuo con
  solo min/max etichettati), ma una legenda testuale a 5 fasce discrete —
  per ciascuna, uno swatch con il colore realmente restituito dalla
  colormap al centro della fascia, il range numerico e un'etichetta di
  gravità esplicita:
  - Mappa temperatura: "Più fresco" → "Più caldo" (°C).
  - Mappa trend: "Raffreddamento" → "Riscaldamento rapido" (°C/decade,
    centrata sullo zero come la mappa).

  Le etichette non sono generiche: riusano esattamente la stessa istanza
  di colormap già creata per colorare la mappa (`cmap_temp`/`cmap_trend`),
  quindi il colore dello swatch in legenda è garantito identico a quello
  visto sulla mappa, non un'approssimazione a parte.

  Verificato con `py_compile` + `AppTest` (nessuna eccezione); server live
  riavviato per applicare le modifiche.

  Pagina aggiornata: `dashboard.md` (descrizione Analisi Spaziale, nuova
  frase sulla legenda a fasce).

- **2026-07-16** — MAPPA HOME COLORATA PER TREND (NON PIÙ TUTTA ROSSA).
  L'utente ha notato che la mappa della home aveva tutte le aree dello
  stesso colore e ha chiesto se non fosse meglio dividerle per gravità
  come le altre mappe. La mappa in effetti coloriva tutti i 44 comuni con
  lo stesso rosso fisso (`style_function` con colore costante) — serviva
  solo a localizzarli, senza trasmettere alcuna informazione. Ricolorata
  per `lr_slope_per_decade` (lo stesso `trend_analysis.csv` già letto per
  la tabella accanto, spostato prima dello split in colonne così entrambe
  le colonne possono usarlo), con la stessa colormap divergente centrata
  sullo zero e la stessa legenda a 5 fasce
  (`components/maps.py::render_gradient_legend()`) già introdotta poco
  prima per la mappa trend di Analisi Spaziale — stessa rappresentazione
  per lo stesso tipo di dato in due pagine diverse, invece di due
  convenzioni visive diverse per lo stesso concetto.

  Sottotitolo/didascalia della sezione aggiornati di conseguenza
  ("Comuni con dati di temperatura reali" → "Velocità di riscaldamento per
  comune"). Mantenuto un ramo di fallback (mappa tutta rossa col messaggio
  "esegui trend_analysis.py") nel caso improbabile in cui
  `trend_analysis.csv` non esista ancora.

  Verificato con `py_compile` + `AppTest` (nessuna eccezione); server live
  riavviato per applicare le modifiche.

  Pagina aggiornata: `dashboard.md` (sezione Home, nuovo paragrafo sulla
  mappa colorata per trend).

- **2026-07-16** — LEGENDA ANCHE SULLA MAPPA DI ONDATE DI CALORE. Richiesta
  ambigua dell'utente ("metti una legenda anche sotto le tabelle nella
  pagina ondate di calore") — la pagina ha 2 tabelle testuali senza colori
  (Statistiche per comune, Elenco ondate) e una mappa colorata (Dove si
  concentrano geograficamente le ondate) senza legenda. Chiesto
  esplicitamente all'utente quale delle due intendesse: confermato che
  serviva la legenda colori sulla mappa, non un'interpretazione delle
  tabelle testuali.

  Estesa `components/maps.py::render_gradient_legend()` con un parametro
  `integer: bool = False`: la mappa di concentrazione colora per un
  **conteggio** di ondate (`n_heatwaves_filtro`), non una grandezza
  continua come temperatura/trend — senza questo, la legenda avrebbe
  mostrato range come "3.4 – 6.8 ondate", non sensati per un numero
  intero. Aggiunta la legenda sotto la mappa in `04_ondate_di_calore.py`,
  5 fasce "Poche" → "Molto alto".

  Verificato con `py_compile` + `AppTest` su tutte e 3 le pagine che usano
  `render_gradient_legend()` (Home, Analisi Spaziale, Ondate di Calore) per
  assicurarsi che il nuovo parametro non rompesse le chiamate esistenti;
  server live riavviato.

  Pagina aggiornata: `dashboard.md` (descrizione Ondate di Calore, nota
  sulla legenda a fasce intere).

- **2026-07-16** — LEGENDA COLORI ANCHE SUL GRAFICO A BARRE "INTENSITÀ
  MEDIA PER ANNO". Richiesta esplicita dell'utente. A differenza delle
  mappe (Folium, colorate con `branca.colormap.LinearColormap`), questo è
  un grafico Plotly (`px.bar` con `color_continuous_scale`) — la sua
  colorscale era già disabilitata (`coloraxis_showscale=False`, scelta
  della sessione precedente per evitare una colorbar verticale ingombrante
  su un grafico dove il colore è già ridondante con l'altezza delle
  barre). `render_gradient_legend()` si aspetta una colormap "callable"
  (branca), non compatibile direttamente con una colorscale Plotly —
  invece di introdurre una seconda colormap branca che avrebbe rischiato
  di non corrispondere esattamente ai colori disegnati da Plotly, usato
  `plotly.colors.sample_colorscale()` per campionare **la stessa identica
  colorscale** (`TEMPERATURE_COLORSCALE`) del grafico, garantendo che lo
  swatch in legenda sia sempre coerente con la barra reale. Aggiunto anche
  `range_color=(0, vmax_intensity)` esplicito al grafico, per evitare che
  Plotly scegliesse un range colore leggermente diverso da quello usato
  per calcolare la legenda. Etichette di gravità: "Bassa" → "Estrema".

  Verificato con `py_compile` + `AppTest` (nessuna eccezione); server live
  riavviato.

  Pagina aggiornata: `dashboard.md` (descrizione Ondate di Calore, nota
  sulla legenda del grafico intensità).

- **2026-07-16** — FILTRO PROVINCIA: DEFAULT VUOTO INVECE DI TUTTO
  PRESELEZIONATO. L'utente ha segnalato (chiamandolo "la legenda", ma
  descrivendo in realtà il multiselect provincia di Analisi Spaziale/Ondate
  di Calore) che il riquadro filtro non era "facilmente capibile": all'
  apertura della pagina mostrava già 8 tag preselezionati (tutte le
  province), un riquadro pieno e poco immediato da leggere al primo
  sguardo. Richiesta esplicita: di default deve prendere tutti i comuni
  con dati, con la possibilità di restringere scegliendo dal menu (mai
  digitando a mano).

  Causa: `render_province_filter()` in `components/filters.py` aveva
  `default=all_provinces` — precompilava il box con tutti gli 8 tag.
  Fix: `default=[]` (box vuoto all'apertura) +
  `placeholder="Tutte le province con dati"` per comunicare comunque cosa
  succede di default senza riempire il box di tag. Il comportamento
  sostanziale **non cambia**: la funzione già ritornava
  `provinces or all_provinces`, quindi "nessuna selezione" equivaleva già
  a "tutti i 44 comuni" — il fix è puramente di leggibilità
  dell'interfaccia, non di logica di filtro. La selezione resta comunque
  solo per click dal menu a tendina, mai testo libero.

  Verificato con `AppTest` su entrambe le pagine: box vuoto di default,
  nessuna eccezione. Server live riavviato.

  Pagina aggiornata: `dashboard.md` (sezione "Filtri", nota sul default
  vuoto del multiselect provincia).

- **2026-07-16** — SPOSTATA LA SPIEGAZIONE "COS'È UN'ONDATA DI CALORE" +
  BILANCIATE LE 3 CARD DELLA HOME. Due richieste dell'utente in un solo
  messaggio.

  (1) Rimosso da `Home.py` il riquadro `st.expander("ℹ️ Cos'è un'ondata di
  calore?")`: la home è overview, non il posto giusto per una spiegazione
  di metodologia specifica di una sola sotto-analisi. Integrato il
  contenuto nel riquadro "ℹ️ Come si legge questa pagina" già esistente in
  `04_ondate_di_calore.py`, aggiungendo la sfumatura presente solo nella
  versione della home e mancante in quella della pagina Ondate ("una
  scelta semplificata: i climatologi usano spesso soglie che variano da
  località a località, non un valore fisso"), invece di perderla.

  (2) La card "🔥 Ondate di Calore" tra le 3 di navigazione risultava più
  bassa delle altre due: Streamlit non equalizza automaticamente l'altezza
  di `st.container(border=True)` tra colonne, ogni card si dimensiona sul
  proprio contenuto — la sua didascalia era semplicemente più corta (~113
  caratteri contro i ~124-136 delle altre due), quindi andava a capo su
  meno righe. Fix: allungata la didascalia per portarla a un numero di
  righe comparabile alle altre due, aggiungendo dettaglio reale già
  presente in pagina (frequenza, durata, concentrazione geografica) invece
  di riempitivo senza contenuto.

  Verificato con `py_compile` + `AppTest` su `Home.py` e
  `04_ondate_di_calore.py` (nessuna eccezione); server live riavviato.

  Pagina aggiornata: `dashboard.md` (sezione Home, rimosso riferimento
  all'expander spostato, aggiunta nota sullo spostamento).

- **2026-07-16** — CARD HOME: ALTEZZA FISSA INVECE DI TESTO "A OCCHIO".
  Il fix precedente (allungare la didascalia della card "Ondate di
  Calore" per farla combaciare con le altre due) ha overcorretto: la
  card è diventata più grande delle altre due. Individuata la causa
  strutturale: `st.container(border=True)` senza un'altezza esplicita si
  dimensiona sul proprio contenuto, quindi far combaciare l'altezza di 3
  card tarando manualmente la lunghezza del testo è intrinsecamente
  fragile (dipende da dove il testo va a capo, che a sua volta dipende
  dalla larghezza reale della colonna a schermo, non dal numero di
  caratteri). Fix strutturale: `st.container(border=True, height=160)` su
  tutte e 3 le card (`CARD_HEIGHT` come costante condivisa) — Streamlit
  supporta un'altezza fissa in pixel per `st.container()` dalla versione
  installata (1.58.0). Ripristinata la didascalia originale, più concisa,
  della card Ondate di Calore: con l'altezza ora fissa non serve più
  allungarla artificialmente per farla combaciare.

  Verificato con `py_compile` + `AppTest` (nessuna eccezione, il parametro
  `height` è supportato); server live riavviato.

  Pagina aggiornata: `dashboard.md` (nota nella sezione Home sostituita:
  non più "didascalie allungate per bilanciare", ma "altezza fissa
  esplicita").

- **2026-07-16** — CARD HOME: ALTEZZA AUMENTATA (160 → 220px, poi → 280px).
  L'utente ha segnalato che con `height=160` il testo delle card veniva
  tagliato. Aumentato `CARD_HEIGHT` a 220px; l'utente ha poi chiesto di
  aumentarlo ancora perché anche il link "Vai alla pagina" non si vedeva
  per intero — portato a 280px, abbastanza per titolo + didascalia su più
  righe + link sempre visibili. Mantenuto il vantaggio del fix precedente
  (le 3 card restano sempre della stessa altezza, indipendentemente dalla
  lunghezza del testo). Verificato con `AppTest` a ogni passaggio (nessuna
  eccezione); server live riavviato.

- **2026-07-16** — TESTO ESPLICATIVO ESTESO NEL TAB "DETTAGLIO TECNICO" DI
  ANALISI TEMPORALE. Richiesta esplicita dell'utente: le 4 metriche
  (Mann-Kendall, MK p-value, Sen's slope, Regressione °C/decade) e la
  scomposizione STL avevano solo didascalie molto brevi — "non capisco
  cosa c'è scritto, è poco chiara". Chiesto di spiegarle in linguaggio
  umano e discorsivo, senza riferimenti alle funzioni del codice.

  Scritto un blocco esplicativo per ciascuna delle 4 metriche statistiche:
  Mann-Kendall descritto come confronto di ogni possibile coppia di anni
  (quante volte il più recente è più caldo del più vecchio vs il
  contrario), MK p-value come "probabilità che il risultato sia solo
  caso, se non ci fosse alcun trend reale", Sen's slope come mediana delle
  pendenze tra tutte le coppie di punti (perché la mediana invece della
  media: resistenza a un singolo anno anomalo), Regressione °C/decade come
  la classica retta di tendenza (più sensibile agli estremi ma standard
  nei report climatici) — chiusura con una frase che lega i 4 numeri tra
  loro (Mann-Kendall+p-value dicono se fidarsi, Sen's slope+regressione
  dicono quanto è ripido).

  Per la STL: aggiunta una premessa sul *perché* si scompone una serie
  giornaliera (il segnale di riscaldamento è lento e nascosto sotto
  oscillazioni stagionali/giornaliere molto più grandi), poi una
  spiegazione per ciascuno dei 3 grafici (trend, stagionalità, residuo) su
  cosa mostra e cosa guardare, non solo una definizione di una riga come
  prima.

  Riscritta anche la sezione "Metodologia" da elenco puntato terso a
  domande e risposte esplicite (perché due pendenze diverse tra tab
  Panoramica e Dettaglio tecnico, perché le stagioni sono meteorologiche e
  non astronomiche, perché la baseline delle anomalie è fissa, cosa sono i
  riferimenti nazionale/globale) — stessa informazione della versione
  precedente, ma nella forma di domanda che l'utente si farebbe
  realmente guardando la pagina, invece di un bullet secco.

  Verificato con `py_compile` + `AppTest`, sia sul comune di default
  (Torino) sia con l'aggregato "Piemonte" attivo (nessuna eccezione in
  entrambi i casi); server live riavviato.

  Pagina aggiornata: `dashboard.md` (descrizione Analisi Temporale, nuovo
  paragrafo sul testo esplicativo esteso).

- **2026-07-16** — TESTO ESPLICATIVO ESTESO NEL TAB "DETTAGLIO TECNICO" DI
  ANALISI SPAZIALE. Stessa richiesta esplicita già fatta per Analisi
  Temporale, applicata qui a K-means e indice di Moran: "non capisco cosa
  c'è scritto, è poco chiara", con la richiesta aggiuntiva di spiegare
  bene i cluster climatici, suddividere i 3 gruppi trovati e spiegare
  perché sono stati divisi così.

  **K-means**: spiegato passo per passo l'algoritmo (si fissa in anticipo
  il numero di gruppi desiderato — qui k=3, scelta pratica per avere zone
  descrivibili a parole, **non** derivata da un metodo tipo elbow/silhouette
  — poi si assegna ogni comune al centro più vicino guardando temperatura
  media e giorni sopra 30°C/35°C **standardizzati**, si ricalcolano i
  centri sulla media dei comuni assegnati, si ripete finché i gruppi non
  cambiano più) e perché servono i valori standardizzati (senza,
  "giorni sopra 30°C" con range 0-60+ peserebbe molto più della
  temperatura media che varia di pochi gradi). Chiarito esplicitamente che
  l'algoritmo **non guarda la posizione geografica dei comuni** — se i
  gruppi risultano compatti sulla mappa (zone alpine, di pianura, ecc.) è
  un risultato dell'analisi, non un'ipotesi di partenza incorporata
  nell'algoritmo.

  **Suddivisione dinamica dei 3 cluster** (non hardcoded): la richiesta
  era di "suddividere i tre cluster e spiegare perché sono stati divisi in
  questo modo" — invece di scrivere testo fisso tipo "Cluster 0 = zona
  alpina" (fragile: se si ri-esegue `spatial_analysis.py`, K-means può
  assegnare id diversi agli stessi gruppi, o persino trovare un'altra
  soluzione), il codice ora **ordina i 3 gruppi trovati dal più fresco al
  più caldo** in base alla temperatura media effettiva e genera la
  descrizione (temperatura media, giorni sopra 30°C, elenco comuni,
  etichetta "il più fresco"/"un profilo intermedio"/"il più caldo") al
  volo dai dati correnti — resta corretta anche se l'analisi viene
  ri-eseguita e l'assegnazione numerica dei cluster cambia.

  **Indice di Moran**: aggiunta la distinzione esplicita dai cluster
  K-means (Moran guarda la geografia — comuni vicini con temperature
  simili — K-means no, raggruppa solo per somiglianza climatica), spiegato
  il calcolo (peso inversamente proporzionale alla distanza tra i centri
  comunali, combinato con quanto ciascun comune si discosta dalla
  temperatura media generale) e perché il p-value viene da una
  permutazione (si mescolano le temperature a caso tra i comuni migliaia
  di volte, tenendo ferma la geografia, e si confronta il valore osservato
  con quelli ottenuti a caso) invece che da una formula diretta.

  **Metodologia** riscritta in domande e risposte (perché proprio 3 fasce
  altitudinali con quelle soglie, perché il confronto isola di calore è
  solo illustrativo, perché la mappa del trend non si aggiorna col filtro
  anni), stesso trattamento già applicato ad Analisi Temporale.

  Verificato con `py_compile` + `AppTest` (nessuna eccezione); server live
  riavviato.

  Pagina aggiornata: `dashboard.md` (descrizione Analisi Spaziale, nuovo
  paragrafo sul testo esplicativo esteso e sulla suddivisione dinamica dei
  cluster).

- **2026-07-16** — ETICHETTE CLUSTER RINUMERATE ALLA FONTE (0=FRESCO,
  1=INTERMEDIO, 2=CALDO). L'utente ha notato che l'assegnazione dei 3
  cluster non seguiva "una logica di ordinamento" e ha chiesto di
  imporre esplicitamente: cluster 0 il più fresco, 1 intermedio, 2 il più
  caldo. Causa: sklearn's `KMeans.fit_predict()` assegna le etichette
  grezze (0, 1, 2) in un ordine **arbitrario**, deciso dall'inizializzazione
  interna dell'algoritmo, senza alcun legame con quanto è caldo o freddo
  il gruppo — la sessione precedente aveva già ordinato dinamicamente la
  *descrizione testuale* per temperatura nella dashboard, ma il dato
  grezzo sottostante (`climate_cluster` in `spatial_analysis.csv`, i
  colori sulla mappa, il numero mostrato nei tooltip) restava nell'ordine
  arbitrario originale.

  Fix alla fonte, non solo nel testo: `climate_clustering()` in
  `src/analysis/spatial_analysis.py` ora calcola la temperatura media di
  ciascuna etichetta grezza, le ordina in modo crescente, e costruisce una
  mappa {etichetta grezza → rank} per rinumerare i risultati prima di
  restituirli — cluster 0 diventa sempre il più fresco, l'ultimo sempre il
  più caldo, indipendentemente da come sklearn li aveva numerati
  internamente.

  **Rieseguito** `python -m src.analysis.spatial_analysis`: risultato
  verificato — cluster 0 = Acceglio/Aisone/Alagna Valsesia/Bardonecchia/
  Ceresole Reale/Formazza/Macugnaga/Rorà (3.8°C, alpino), cluster 1 = 17
  comuni pedemontani/collinari (11.1°C), cluster 2 = 19 comuni di pianura
  (12.9°C) — stessa identica composizione di gruppi di prima (l'algoritmo
  non è cambiato, solo la numerazione), confermato anche dal test unitario
  `test_separates_two_clearly_distinct_groups` (ancora verde).

  **Colori aggiornati di conseguenza**: `CLUSTER_COLORS` in
  `dashboard/components/constants.py` passa da {0: blu, 1: rosso, 2: verde}
  (arbitrario) a {0: blu, 1: arancio, 2: rosso} (stessa logica blu→rosso
  della colormap di temperatura usata nel resto del sito, ora coerente
  anche qui: cluster freddo = blu, cluster caldo = rosso). Stesso
  aggiornamento fatto nella mappa QGIS `hotspot_analysis.qgz`
  (`qgis_projects/build_maps.py`), **rigenerata** con
  `python-qgis-ltr.bat build_maps.py` per riflettere sia il nuovo
  `spatial_analysis.csv` sia i nuovi colori.

  Verificato con `pytest` (cluster test ancora verde), `py_compile` +
  `AppTest` sulla pagina Analisi Spaziale (nessuna eccezione); server live
  riavviato.

  Pagine aggiornate: `statistical-analysis.md` (etichette cluster
  rinumerate, composizione con id 0/1/2 espliciti), `gis-maps.md` (nota su
  `hotspot_analysis.qgz` rigenerata), `dashboard.md` (nuovo paragrafo sul
  fix alla fonte).

- **2026-07-16** — TESTO ESPLICATIVO ESTESO NEL TAB "DETTAGLIO TECNICO" DI
  ONDATE DI CALORE (stesso pattern di Analisi Temporale e Analisi
  Spaziale). Richiesta esplicita dell'utente di applicare lo stesso
  trattamento fatto per le altre due pagine anche qui.

  **Confronto con la definizione a soglia percentile**: aggiunta una
  premessa sul *perché* esiste un'alternativa alla soglia fissa (35°C
  tratta tutti i comuni allo stesso modo, penalizzando i comuni di
  montagna che quasi non la raggiungono mai anche in estati eccezionali
  per i loro standard locali), poi una spiegazione concreta di cosa sia un
  percentile e come si calcola (ordinare tutte le temperature massime
  storiche di un comune dal 2000 a oggi; il 90° percentile è il valore
  sotto il quale sta il 90% dei giorni — un numero diverso per ogni
  comune, non fisso come 35°C).

  **Metodologia** riscritta in domande e risposte, stesso trattamento
  delle altre due pagine: perché il resto del sito usa comunque la soglia
  fissa (un solo criterio semplice e uguale per tutti, i numeri percentile
  qui sono solo un confronto illustrativo e non sostituiscono mai quelli
  ufficiali mostrati altrove), perché la durata minima resta 3 giorni
  anche con la soglia percentile (per confrontare le due definizioni a
  parità di condizioni), cosa aggrega esattamente la heatmap "calendario"
  (per ogni combinazione anno/giorno-dell'anno, quanti comuni avevano
  un'ondata attiva quel giorno preciso).

  Verificato con `py_compile` + `AppTest` (nessuna eccezione); server live
  riavviato.

  Pagina aggiornata: `dashboard.md` (descrizione Ondate di Calore, nuovo
  paragrafo sul testo esplicativo esteso — chiude il giro di tutte e 3 le
  pagine di analisi con lo stesso trattamento).

- **2026-07-16** — PIANO ARTICOLO SCIENTIFICO: NUOVA PAGINA + RICOGNIZIONE
  FONTI ESTERNE MANCANTI. L'utente ha deciso di trasformare il progetto in
  un articolo scientifico (descrittivo + esplicativo sulle cause
  città/industria/riscaldamento delle differenze di temperatura), target
  una rivista/conferenza peer-reviewed vera, non solo portfolio. Creata
  `wiki/pages/paper-scientifico.md` (nuova pagina di pianificazione, non di
  codice esistente) con le 5 fasi concordate (validazione ARPA, estensione
  campione comuni, acquisizione uso del suolo/popolazione, modellazione
  spaziale, percorso di pubblicazione) e la letteratura raccolta via
  ricerca web (Garzena et al. 2019 su UHI Torino, Perkins & Alexander 2013
  su definizione ondate di calore, studio SUHI/impervious surface città
  italiane, ecc.). Aggiornato `index.md`.

  **Ricognizione di fattibilità delle fonti esterne mancanti** (uso del
  suolo, popolazione, validazione stazioni): nessuna delle tre è un
  semplice "attiva e scarica".
  - `ArpaPiemonteDownloader` esiste già nel codice ma **l'URL in
    `config.yaml` (`arpa_piemonte.url`) risponde 404** (verificato con
    richiesta HTTP diretta) — stesso tipo di bug placeholder mai eseguito
    già trovato per l'URL ISTAT dei confini comunali il 2026-07-04. I dati
    veri stanno dietro un'interfaccia a mappa o una richiesta manuale, non
    un endpoint diretto.
  - CORINE Land Cover (Copernicus) ha un'API di download reale ma richiede
    un account CLMS con credenziali, come già il caso di
    `CopernicusERA5Downloader`/`CDS_KEY`.
  - Popolazione ISTAT (`dati.istat.it`, dataset SDMX `DCIS_POPORESBIL1`)
    non richiede account, ma l'endpoint/query esatti restano da verificare.

  Nessun codice scritto in questa sessione per queste fonti (solo
  ricognizione); documentato in `paper-scientifico.md` per evitare di
  ripartire da zero nella prossima sessione. Non toccato
  `download_extra_municipalities.py`/DB: l'utente sta eseguendo in parallelo
  l'estensione della copertura temperature da 44 a 300 comuni.

  Pagine aggiornate: `paper-scientifico.md` (nuova), `index.md`.

  **Scheletro del manoscritto**: su richiesta dell'utente, creato
  `paper/manoscritto.md` (nuova cartella, fuori da `wiki/` — è il contenuto
  del paper stesso, non meta-pianificazione). Struttura completa
  Abstract/Introduzione/Dati e Metodi/Risultati/Discussione/Conclusioni/
  Bibliografia/Appendice di tracciabilità, con marcatori **[FATTO]**/
  **[DA FARE]** su ogni sottosezione. Le sezioni **[FATTO]** riportano i
  numeri reali già verificati (38/44 comuni con trend significativo,
  145 ondate, Moran's I=0.101 p=0.002, cluster 3.8/11.1/12.9°C, ampiezza
  STL 27-34°C) con riferimento diretto ai CSV in `output/` (tabella di
  tracciabilità in Appendice A). Le sezioni **[DA FARE]** (uso del
  suolo/popolazione, validazione ARPA, modello a errore spaziale)
  restano vuote/segnaposto finché il lavoro sottostante non è concluso —
  deliberato, per non scrivere conclusioni prima di avere i dati.
  Aggiornata `paper-scientifico.md` con un rimando al nuovo file.

  **Approfondimento popolazione ISTAT (stessa sessione, su richiesta
  esplicita dell'utente di lavorare in parallelo al download dei 300
  comuni)**: investigata l'API SDMX `esploradati.istat.it/SDMXWS` per il
  dataset `DCIS_POPORESBIL1` (popolazione residente-bilancio). Confermato
  via richieste HTTP dirette: (1) i codici territorio nel codelist
  `CL_ITTER107` coincidono esattamente con `municipalities.istat_code` già
  in DB (`001272` = Torino, verificato leggendo il codelist completo, 9MB);
  (2) esiste un dataflow specifico per il Piemonte
  (`22_315_DF_DCIS_POPORESBIL1_3`, identificato tra ~450 dataflow cercando
  l'annotazione `FILTER__ITC1`), distinto dal dataflow padre `22_315`.
  **Nessuna query dati ha però restituito osservazioni reali**: sia sul
  flow padre che su quello Piemonte-specifico, con diverse combinazioni di
  `DATA_TYPE` (`JAN`, `DEC_CP_P`, wildcard) e anche con `REF_AREA`
  completamente jolly, la risposta è sempre `NoRecordsFound` o serie con
  tutte le osservazioni `null` — sembra un dataset con struttura/DSD
  popolata ma dati non esposti (o non ancora migrati) su questo endpoint
  REST specifico. Non risolto in questa sessione: il passo successivo
  probabile è l'export CSV manuale della query legacy `.Stat`
  (`dati.istat.it/Index.aspx?QueryId=19101`), sistema diverso dal nuovo
  SDMX REST, mai tentato. File temporanei di indagine (codelist 9MB, lista
  dataflow 13.5MB) salvati solo nello scratchpad di sessione, non nel
  repository.

- **2026-07-16** — POPOLAZIONE ISTAT: TROVATA LA FONTE GIUSTA E CARICATA
  PER TUTTI I 1180 COMUNI. Continuazione della stessa indagine, stessa
  sessione: tentato l'export della query legacy `dati.istat.it` (QueryId
  19101) come prossimo passo previsto — il portale e' dismesso (redirect
  con certificato scaduto verso un avviso di decommissioning). Trovato
  invece `demo.istat.it`, sistema attivo e separato ("Popolazione
  residente per eta' e sesso"), con un file ZIP per provincia
  (`https://demo.istat.it/data/posas/POSAS_{anno}_it_{codice}_{nome}.zip`,
  nessun account), CSV con una riga per comune/eta'/sesso (eta'=999 e' il
  totale per comune). Verificato scaricando ed ispezionando a mano il file
  di Torino prima di scrivere codice: i codici comune coincidono
  esattamente con `istat_code` gia' in DB.

  Scritto `src/data_acquisition/download_population.py`. Bug trovato in
  fase di test manuale (prima di lanciare lo script sulle 8 province): la
  colonna eta' viene letta da pandas come stringa, non intero — un filtro
  numerico (`== 999`) restituiva sempre 0 righe; corretto confrontando con
  la stringa `'999'`. Eseguito sulle 8 province reali: **1180/1180 comuni
  aggiornati** (`municipalities.population`), coincidenza esatta per
  provincia con l'allocazione gia' usata in
  `download_extra_municipalities.py` (312 Torino, 247 Cuneo, 187
  Alessandria, 117 Asti, 87 Novara, 82 Vercelli, 74 Biella, 74
  Verbano-Cusio-Ossola). Valori verificati a campione via query SQL
  diretta: Torino 855.654 ab. (densita' 6580 ab/km2, usando `area_km2` gia'
  presente), Alessandria 93.409, Cuneo 55.747, Bardonecchia 2.853 (densita'
  21.6 ab/km2), Formazza 410 (densita' 3.1 ab/km2) — gradiente
  pianura/alpino coerente col clustering climatico gia' trovato.

  Aggiornato anche `paper/manoscritto.md` (§2.4 passata da "DA FARE" a
  "PARZIALMENTE FATTO" per la parte popolazione).

  Pagine aggiornate: `data-sources.md` (nuova sezione), `data-model.md`
  (`population` non piu' `NULL`), `paper-scientifico.md`.

- **2026-07-16** — CORINE LAND COVER: TERZA COVARIATA ESPLICATIVA FATTA,
  PER TUTTI I 1180 COMUNI. Su richiesta esplicita dell'utente ("spiegami
  come procedere con Copernicus"), spiegato il percorso CLMS (account EU
  Login gratuito, poi "Download by area" invece dell'API con token JWT —
  quest'ultima scartata di comune accordo perche' CORINE si aggiorna ogni
  ~6 anni, non serve automazione). L'utente ha creato l'account e provato a
  scaricare da solo.

  **Primo tentativo dell'utente**: cartella `U2018_CLC2018_V2020_20u1_doc/`
  aggiunta al progetto — ispezionata e risultata **solo documentazione**
  (42 file: PDF, metadata XML, legenda), nessuna geometria. Salvato
  `data/external/clc_legend.csv` (tabella codici CLC -> classi, utile per
  dopo), poi cancellata la cartella su richiesta dell'utente.

  **Secondo tentativo, quello giusto**: file `U2018_CLC2018_V2020_20u1.gpkg`
  (136 MB) aggiunto alla root del progetto. Ispezionato prima di scrivere
  codice (`pyogrio.read_info`): EPSG:3035 (proiezione equal-area di CLC),
  52.794 poligoni, campo `Code_18` = codice CLC a 3 cifre, dimensione ed
  estensione coerenti con un ritaglio sul Piemonte (non tutta Europa).

  Creata `sql/03_land_cover.sql` — nuova tabella `municipality_land_cover`
  (satellite 1:1 con `municipalities`, non nuove colonne li' per non
  appesantirla): % urbano/agricolo/forestale-seminaturale/zone umide/acqua
  + classe dominante, per comune.

  Scritto `src/data_acquisition/process_land_cover.py`: overlay geopandas
  tra le geometrie comunali (riproiettate in EPSG:3035 per coerenza con
  CLC) e i poligoni CLC, categorie aggregate al primo carattere del codice
  a 3 cifre (1=urbano...5=acqua; i codici speciali 990/995/999 in "other",
  vedi `clc_legend.csv`). Testato prima su 3 comuni campione
  (Torino/Alessandria/Formazza, ~8 secondi) prima di lanciare sui 1180
  reali — risultati gia' plausibili nel test (Torino 75% urbano, Formazza
  0% urbano/dominante forestale). Overlay completo sui 1180 comuni:
  **~16 secondi**, nessun problema di performance.

  **Risultato reale, 1180/1180 comuni**: distribuzione classe dominante
  690 agricultural, 466 forest_seminatural, 12 urban, 12 water. Valori
  verificati a campione: Torino 75.45% urbano (dominante urbano); Verbania
  40.70% acqua (dominante acqua — sul Lago Maggiore, coerente con
  l'ampiezza stagionale minima gia' trovata in
  [Analisi statistica](statistical-analysis.md)); Vercelli 75.94% agricolo,
  Alessandria 84.18%, Cuneo 82.37%, Asti 67.59% (tutte dominante
  agricolo, coerente con la vocazione risicola/cerealicola della pianura
  piemontese); Bardonecchia 95.46% e Formazza 94.64% forest_seminatural
  (dominante forestale, comuni alpini).

  Aggiornato `paper/manoscritto.md` (§2.4 uso del suolo passata a
  **[FATTO]**; nota esplicita sul disallineamento temporale CLC2018 vs
  temperature 2000-2025/popolazione 2026, da dichiarare come limite non da
  nascondere). Con questo, tutti e tre gli ingredienti del modello
  esplicativo di §3.5 (elevazione, popolazione, uso del suolo) sono ora
  disponibili per i comuni con temperatura — il modello statistico vero e
  proprio (§2.4/§3.5) resta pero' ancora da costruire.

  Pagine aggiornate: `data-model.md` (nuova tabella
  `municipality_land_cover`), `data-sources.md` (nuova sezione, inclusi i
  due tentativi), `paper-scientifico.md`.

- **2026-07-16** — SCOMPOSIZIONE DI "URBANO" IN SOTTO-CLASSI (RESIDENZIALE
  VS INDUSTRIALE). Su richiesta esplicita dell'utente, che ha scelto questa
  opzione tra tre proposte (le altre: aggiungere subito i dati a dashboard,
  o fermarsi ad aspettare) perche' quasi gratis (dato gia' scaricato) e
  perche' risponde direttamente all'ipotesi originale del paper su
  citta'/industria come cause delle differenze di temperatura — un unico
  `pct_urban` aggregato non distingueva residenziale da industriale.

  Aggiunte 5 colonne a `municipality_land_cover` (`sql/03_land_cover.sql`,
  via `ALTER TABLE ADD COLUMN IF NOT EXISTS`): `pct_residential` (codici
  CLC 111/112), `pct_industrial_commercial` (121), `pct_transport`
  (122-124), `pct_urban_green` (141-142), `pct_extraction_construction`
  (131-133) — sommano a `pct_urban`. Esteso
  `src/data_acquisition/process_land_cover.py` per calcolarle riusando lo
  stesso overlay geopandas gia' fatto (nessun overlay aggiuntivo, solo un
  secondo `groupby` sulle sole righe con `level1=='urban'`).

  **Bug trovato e corretto rieseguendo lo script**: prima esecuzione,
  0 righe con errori evidenti ma valori `NaN` silenziosi per
  `pct_industrial_commercial` (e le altre sotto-classi) in tutti i comuni
  con **zero** intersezione urbana (nessuna riga in `overlay` con
  `level1=='urban'` per quel comune) — scoperto ordinando per
  `pct_industrial_commercial DESC` e vedendo `NaN` in cima invece che 0.
  Causa: `DataFrame.div(Series, axis=0)` allinea gli indici e produce
  `NaN` per le righe assenti da un lato; il successivo
  `.reindex(fill_value=0.0)` **non** sostituisce questi `NaN` (riempie solo
  le righe del tutto assenti dall'indice, non quelle gia' presenti ma
  `NaN`) — serviva un `.fillna(0.0)` esplicito dopo la divisione, aggiunto
  sia per le sotto-classi urbane sia per le categorie di Livello 1 (stesso
  rischio in linea di principio, anche se non si era manifestato).
  Rieseguito: 0 righe `NULL`/`NaN` su 1180.

  **Risultato reale**: Grugliasco 34.20% industriale/commerciale (64.24%
  urbano totale), Beinasco 33.40% (67.26% totale), Settimo Torinese 26.07%
  — le vere zone a vocazione industriale della cintura torinese (non
  Torino stessa, che ha piu' residenziale: 45.47% vs 20.56% industriale),
  coerente con la geografia industriale nota dell'area metropolitana.

  Pagine aggiornate: `data-model.md` (nuove colonne + bug documentato),
  `paper/manoscritto.md` (§2.4, nuovo punto sulle sotto-classi urbane).

- **2026-07-16** — TO-DO AGGIUNTI ALLA WIKI (dashboard + altri dati
  esplicativi), su richiesta esplicita dell'utente. Non implementati in
  questa sessione, solo tracciati in
  [Articolo scientifico](paper-scientifico.md) sotto "Idee da esplorare":
  (1) aggiungere popolazione/uso del suolo alla dashboard (mappa classe
  dominante o % urbana, mappa densita' di popolazione, sostituire il
  confronto isola di calore "solo illustrativo" con uno basato su dati
  reali); (2) altre covariate candidate in ordine di sforzo crescente:
  NDVI da satellite, pendenza/esposizione da un DEM, distanza dal Po/dai
  laghi, densita' stradale/edificato da OpenStreetMap (downloader gia'
  presente nel codice, mai attivato).

- **2026-07-16** — DASHBOARD: USO DEL SUOLO E POPOLAZIONE IN ANALISI
  SPAZIALE, SOSTITUITO IL CONFRONTO ISOLA DI CALORE ILLUSTRATIVO. Su
  richiesta esplicita dell'utente ("procedi con Aggiungere popolazione/uso
  del suolo alla dashboard"), primo dei due to-do tracciati poco prima.

  Aggiunte a `components/constants.py`: `LAND_COVER_COLORS`/
  `LAND_COVER_LABELS`, colori vicini alla palette ufficiale CORINE (presi
  da `data/external/clc_legend.csv`, non inventati) per le 5 categorie di
  Livello 1. Aggiunte a `components/queries.py`: `get_land_cover_all()` e
  `get_all_municipality_geometries_wkt()` (tutti i 1180 comuni, non solo i
  44 con temperatura - uso del suolo/popolazione coprono l'intero
  territorio) e `get_land_cover_with_population()` (solo i comuni con
  temperatura, per lo scatter).

  In `03_analisi_spaziale.py`, dopo la sezione fasce altitudinali:
  - **Mappa uso del suolo dominante** (1180 comuni).
  - **Mappa densita' di popolazione** (1180 comuni, scala logaritmica -
    altrimenti Torino schiaccia la scala).
  - **Scatter temperatura vs uso del suolo/popolazione** (solo i comuni con
    temperatura): sostituisce il vecchio confronto "Torino vs comuni
    rurali della provincia" (dichiarato "solo illustrativo"). Selettore
    `st.radio` tra % urbano/% industriale-commerciale/densita' di
    popolazione; colore = fascia altitudinale, per poter valutare a occhio
    se l'effetto regge a parita' di quota; metrica di correlazione di
    Pearson con caveat esplicito ("non controllata per quota", il modello
    vero resta pianificato in `paper/manoscritto.md` §3.5).

  **Bug trovato e corretto con `AppTest` prima di qualunque verifica
  manuale**: `geo_all.merge(land_cover_all, on='municipality_name')` -
  entrambe le tabelle hanno una colonna `province_name`, non parte della
  chiave di join, quindi pandas la rinominava in `province_name_x`/
  `province_name_y` invece di lasciarla con il nome atteso - `KeyError:
  'province_name'` al primo `AppTest.run()`. Fix: colonna duplicata esclusa
  da un lato del merge prima di unire.

  **Verificato con `AppTest`**: run di default (nessuna eccezione), radio
  su `pop_density` (scala log sull'asse x) e su
  `pct_industrial_commercial` (nessuna eccezione in entrambi i casi),
  filtro provincia ristretto a una sola provincia piccola (Biella, nessuna
  eccezione). Valori reali sensati: correlazione Pearson +0.30 (%urbano vs
  temperatura, tutti i comuni nel filtro di default) - plausibile, non
  sospetta data la confusione nota con la quota.

  Pagine aggiornate: `dashboard.md` (nuova sezione + bug documentato),
  `paper-scientifico.md` (to-do 1 segnato fatto).

- **2026-07-17** — ESTENSIONE A 63 COMUNI + DATI FINO AD OGGI (obiettivo
  iniziale: tutti i 1180 comuni). Richiesta esplicita dell'utente:
  "coprimi i 1180 comuni piemontesi, e aggiorna la data fino ad oggi".
  Sessione lunga e accidentata, con un vero e proprio processo di
  scoperta empirica del rate limit di Open-Meteo. Cronologia:

  1. **Stima iniziale ottimista**: spiegato all'utente il costo reale di
     1180 comuni (~11M righe, ma soprattutto ore di download per il rate
     limit già noto). Consigliata una via di mezzo (200-300 comuni),
     accettata. Chiesto anche un parere su leggibilità delle mappe con
     300 punti: convertita la mappa del trend in Analisi Spaziale da
     marker a cerchio a poligoni colorati (stesso trattamento delle altre
     3 mappe), eliminando il rischio di sovrapposizione visiva.
  2. **Tentativo 1 (256 comuni extra, obiettivo 300 totali)**: lanciato in
     background. Dopo **~5h40** di download continuo (monitorato a
     intervalli), solo 37/256 comuni riusciti, 123 falliti
     definitivamente. Interrotto — e siccome
     `download_extra_municipalities.py::download_all()` collezionava
     tutto in una lista Python scrivendo il CSV **solo a fine
     esecuzione**, l'interruzione ha fatto perdere **tutto** il progresso
     (nessun file scritto). Lezione durissima ma chiara.
  3. **Tentativo 2 (56 comuni, obiettivo ridotto a 100)**: bloccato
     **immediatamente**, anche su una singola richiesta di test isolata
     (429). Il corpo della risposta ha rivelato la causa: `"Daily API
     request limit exceeded. Please try again tomorrow."` — un limite
     **giornaliero**, non solo "al minuto" come già documentato. La
     finestra di 5h40 sprecata aveva già esaurito la quota di giornata.
  4. **Fix strutturale** (prima di riprovare, non dopo): salvataggio
     **incrementale** in `download_extra_municipalities.py` (ogni comune
     scaricato subito appeso al CSV, `mode='a'`) — così un'interruzione
     futura non fa più perdere lavoro.
  5. **Discussione sulle alternative**: l'utente ha chiesto se non ci
     fossero altri modi per scaricare i dati (manualmente, altre fonti).
     Risposta onesta: Copernicus CDS ha un'interfaccia web per download
     manuali (bypassa Open-Meteo, ma richiede account, è un dataset
     diverso — ERA5 a griglia, non per stazione — e la pipeline di
     parsing NetCDF non è mai stata testata); ARPA Piemonte copre solo le
     poche stazioni reali, non abbastanza comuni. Nessuna alternativa
     chiaramente migliore dell'aspettare; l'utente ha scelto di aspettare
     e riprovare il giorno dopo con lotti più piccoli.
  6. **Giorno successivo (2026-07-17)**: quota resettata (verificato con
     un test leggero). Reso `download_extra_municipalities.py`
     **parametrico** (`--count`, allocazione per provincia calcolata dal
     vivo con `compute_target_per_province()` invece di pesi fissi nel
     codice) su richiesta dell'utente di provare lotti da 10 per volta
     per scoprire la soglia esatta. Un lotto di 50 ha **rivelato
     empiricamente**: si blocca sempre intorno a **19-20 richieste
     "pesanti"** (26 anni di storico ciascuna) — dal 20° comune in poi,
     ogni tentativo falliva dopo 5 retry. Fermato subito (zero perdita,
     grazie al fix del punto 4): **19 comuni aggiuntivi** salvati con
     successo (44 → 63 comuni). Chiesto conferma all'utente se procedere
     subito con la pipeline sui 63 disponibili o aspettare altri giorni
     per arrivare a 94: scelto di procedere subito.
  7. **Delta a oggi per tutti i 63 comuni**: scritto nuovo script
     `src/data_acquisition/update_recent_data.py` (stesso fix di
     salvataggio incrementale fin dall'inizio, lezione già imparata).
     Scoperta interessante: le richieste piccole (~198 giorni ciascuna,
     invece di 26 anni) **non hanno mai incontrato il rate limit** —
     tutti e 63 i comuni aggiornati con successo in un solo lotto, zero
     errori. La quota sembra legata al volume di dati per richiesta, non
     a un conteggio piatto (osservazione empirica, non verificata contro
     documentazione ufficiale).
  8. **Caricamento nel DB**: filtrato il CSV pulito ai soli
     `municipality_id` non ancora presenti prima di caricarlo (nessun
     vincolo di unicità `(municipality_id, date)` in `temperature`: un
     caricamento ingenuo dell'intero file avrebbe duplicato i 36 comuni
     già presenti dalla sessione precedente). Elevazione ricalcolata per
     tutti i 63 comuni (query batch singola, economica).
  9. **Ricalcolo di tutta la catena a valle**: `TRUNCATE` +
     `identify_heatwaves()` (190 ondate, +16 rispetto a prima grazie al
     2026), refresh viste materializzate (1701 righe), tutti e 4 i moduli
     `src/analysis/` (STL ~30 minuti data la mole, eseguita in
     background), mappe QGIS rigenerate.
  10. **2 bug reali trovati grazie al dato 2026** (mai emersi prima
      perché la serie storica non aveva mai superato il 2025): (a)
      `frequency_by_year()` in `heatwave_stats.py` aveva un
      `reindex(range(2000, 2026))` fisso che scartava in silenzio le 16
      ondate del 2026 dal grafico della dashboard — nessun errore, solo
      dati mancanti; scoperto confrontando il conteggio diretto da
      `heatwave_events` con l'output della funzione. Fix: range dinamico
      dal min/max anno realmente presente. (b) Stesso identico tipo di
      bug in `dashboard/components/filters.py`
      (`YEAR_MIN, YEAR_MAX = 2000, 2025` fissi) — avrebbe reso
      impossibile selezionare il 2026 nello slider. Fix: dinamico da
      `get_overview_stats()`.
  11. **Aggiornamento testi dashboard**: `Home.py` reso completamente
      dinamico (nessun numero di comuni/anno più hardcoded, tutto da
      `get_overview_stats()`), stesso trattamento parziale sulle altre
      pagine per gli help text/caption più visibili; le narrazioni
      storiche di log/dashboard.md che descrivono sessioni precedenti
      **non sono state riscritte** (coerente con la natura append-only
      della documentazione).

  **Risultato finale**: 44 → **63 comuni** (8 capoluoghi + 55 extra),
  **610.785 righe**, dal 2000 **fino a oggi** — non i 1180 comuni
  richiesti inizialmente, ma un incremento reale, verificato, e ottenuto
  senza perdite nonostante due tentativi fintiti falliti. Moran's I
  migliora ulteriormente (0.132, p=0.001). Trend: 54/63 comuni
  significativi; scoperto un caso controcorrente (Briga Alta, unico
  raffreddamento significativo, -0.63°C/decade) segnalato onestamente
  invece che ignorato.

  Verificato con `py_compile` + `AppTest` su tutte le pagine dopo ogni
  round di modifiche (nessuna eccezione); server live riavviato con i
  dati aggiornati.

  Pagine aggiornate: `data-sources.md` (racconto completo della scoperta
  del rate limit, 2 nuovi script documentati), `etl-pipeline.md`
  (sezione estensione + bug), `data-model.md` (conteggi righe/comuni/anni
  aggiornati), `statistical-analysis.md` (nuova sezione risultati
  ricalcolati + bug), `gis-maps.md` (mappe rigenerate), `dashboard.md`
  (nota di aggiornamento + bug), `project-status.md` (nuova sezione
  cronologica con tutti i dettagli).

- **2026-07-17** — NDVI (VERDE DA SATELLITE): PREDISPOSIZIONE TABELLA +
  SCRIPT, DOWNLOAD ANCORA DA FARE. Su richiesta dell'utente, avviata la
  terza covariata esplicativa per il paper scientifico (dopo popolazione e
  CORINE Land Cover, entrambe fatte il 2026-07-16) — vedi
  [Articolo scientifico](paper-scientifico.md), "Idee da esplorare".

  **Decisione di scoping presa con l'utente** (stessa logica costi/
  benefici gia' applicata a CORINE): tre opzioni presentate — Sentinel-2
  vero via Google Earth Engine (10m, richiede account GEE), Sentinel-2 vero
  via Copernicus Data Space Ecosystem Statistical API (10m, OAuth,
  rischio di friction gia' visto con le altre API Copernicus/ISTAT del
  progetto), o Copernicus Global Land Service NDVI 300m V3 (prodotto gia'
  calcolato, download manuale, nessun account nuovo oltre a quello CDSE per
  il solo download). Scelta: **CGLS NDVI 300m V3**, stesso pattern
  low-effort che ha funzionato per CORINE.

  **Ricerca tecnica** (via web, per evitare di indovinare la formula come
  gia' successo in passato con bug di encoding/scaling): il prodotto e' un
  GeoTIFF a 8 bit, EPSG:4326 (nessuna riproiezione necessaria, a
  differenza di CLC/EPSG:3035). DN 0-250 -> NDVI reale via
  `NDVI = DN * 0.004 - 0.08`; DN 251-255 sono flag dedicati (251=missing,
  252=cloud, 253=snow/ice, 254=sea, 255=background) — confermato da PDF
  ufficiale Copernicus (parzialmente, il rendering testuale del PDF era
  degradato) e da documentazione Sentinel Hub/CDSE leggibile. **Non ancora
  verificato empiricamente su un file scaricato per il Piemonte** — stesso
  tipo di rischio gia' incontrato con CLC (i due tentativi prima del file
  giusto), da tenere d'occhio alla prima esecuzione reale.

  Anche il *dove* si scarica e' cambiato rispetto a CLC: l'accesso ai dati
  NDVI globali e' migrato dal portale CLC (`land.copernicus.eu`, tool
  "Download by area" gia' usato per CORINE) al Copernicus Data Space
  Ecosystem (`dataspace.copernicus.eu`, Copernicus Browser) — richiede un
  account gratuito separato da quello EU Login usato per CLC. Il percorso
  esatto di ritaglio sul Piemonte non e' ancora stato verificato
  praticamente (va documentato dopo il primo download reale, come gia'
  fatto per CORINE con i suoi due tentativi).

  **Predisposto in questa sessione** (codice, non ancora eseguito su dati
  reali): `sql/04_ndvi.sql` (tabella `municipality_ndvi`, satellite 1:1
  con `municipalities` come `municipality_land_cover`), `src/data_acquisition/process_ndvi.py`
  (zonal stats via `rasterstats` invece dell'overlay vettoriale di CLC,
  dato che qui la sorgente e' un raster; `all_touched=True` per i comuni
  piccoli rispetto ai 300m di pixel), `rasterio`/`rasterstats` aggiunti a
  `requirements.txt` (non ancora installati/verificati nel venv).

  **Eseguito realmente in questa sessione** (non solo scritto): `rasterio`/
  `rasterstats` installati nel `.venv` (verificato `pip install`, nessun
  conflitto), `python -m src.data_acquisition.process_ndvi --help` eseguito
  con successo (import puliti, argparse funzionante), e
  `sql/04_ndvi.sql` **applicato per davvero** al database locale (via
  cursore DBAPI grezzo, stesso pattern gia' documentato per
  `initialize_schema()` — `exec_driver_sql` con dict di parametri vuoto
  fallisce su script multi-statement) — tabella `municipality_ndvi`
  verificata esistente con lo schema atteso via
  `information_schema.columns`.

  **Non fatto in questa sessione** (a quel punto): il download manuale del
  GeoTIFF, compito dell'utente da fare interagendo col Copernicus Browser.

  Pagine aggiornate (primo giro): `data-sources.md` (nuova sezione "NDVI
  (Copernicus Global Land Service)"), `data-model.md` (nuova tabella
  `municipality_ndvi`), `paper-scientifico.md` (voce "NDVI" in "Idee da
  esplorare" segnata "in corso"), `project-status.md`.

- **2026-07-17** (stessa giornata) — NDVI: DOWNLOAD REALE E COMPLETAMENTO,
  DOPO UN VICOLO CIECO E DIVERSE DIFFICOLTA' DI PORTALE. Sessione di
  supporto interattivo all'utente (screenshot del Copernicus Browser
  condivisi passo passo) per completare quanto predisposto nella sessione
  precedente.

  **Vicolo cieco — HR-VPP**: durante la navigazione del Browser, un
  filtro "PROJECTION & RESOLUTION" con opzioni UTM 10m/20m/60m e LAEA
  10m/20m/60m/100m (insieme a un campo testuale "Dataset identifier=NDVI")
  sembrava puntare a un secondo prodotto CLMS realmente a 10m (HR-VPP,
  Sentinel-2 vero, tile-based) — un'apparente occasione di ottenere una
  risoluzione migliore del piano originale "gratis". Confermato via
  ricerca web che HR-VPP esiste davvero (10m, dal 2016), ma **non e'
  raggiungibile da questo catalogo di ricerca**: navigando l'albero delle
  sotto-categorie ("Vegetation Indices" → solo le 5 varianti Global
  300m/1km gia' pianificate; "Vegetation Phenology and Productivity
  Parameters" → solo prodotti di fenologia LSP, non NDVI), e verificato
  con una ricerca reale che restituiva sempre "0 prodotti trovati" con
  quei filtri (la lista "Available data" mostrata dall'errore elencava
  solo le varianti Global 300m/1km) — le opzioni UTM/LAEA nel pannello
  erano opzioni generiche del sotto-sistema di filtro, non backed da
  prodotti realmente indicizzati qui. Tornati al piano originale (CGLS
  300m V3), confermato disponibile nella stessa lista.

  **Difficolta' reali del portale** (documentate perche' si ripeteranno
  in eventuali download futuri di altri prodotti CLMS): (1) il selettore
  "Time Range" non rispondeva al click sul testo placeholder
  "YYYY-MM-DD" — sbloccato cliccando esattamente sul primo carattere per
  attivare il segmento, poi digitando le cifre da tastiera (`20260601`),
  non un calendario a popup come ci si aspetterebbe; (2) senza un
  intervallo di date impostato la ricerca restituiva sempre "0 prodotti"
  nonostante il prodotto fosse disponibile, presumibilmente per un
  default implicito su "oggi" (periodo non ancora elaborato per un
  composito 10-giornaliero) — serviva un intervallo esplicito nel
  passato (giugno 2026).

  **Il file scaricato e' globale**: a differenza di CLC (tool "Download
  by area" dedicato su `land.copernicus.eu`, ritaglio lato server), CDSE
  non offre un ritaglio per quest'area — il file (Cloud Optimized GeoTIFF,
  zip) e' un'unica griglia mondiale da **~3.3 GB**, con 4 raster distinti
  dentro (NDVI, NOBS, QFLAG, UNC). Estratto dallo zip solo il file NDVI
  (~1.29 GB, via `zipfile` mirato su un solo membro, non l'intero
  archivio) in `data/external/ndvi/`.

  **Verifica empirica di scala/offset/flag** (invece di fidarsi solo
  della documentazione, che per questo prodotto si e' rivelata
  imprecisa): ispezionato il file reale con `rasterio` — CRS EPSG:4326
  confermato, dtype `uint8`, nodata `255`, griglia 120960×47040 pixel
  (~333m di lato reale, coerente con l'identificatore interno
  `ndvi300_v3_333m` nonostante il nome commerciale "300m"). `scales`/
  `offsets` embedded nel file confermano `0.004`/`-0.08` (la formula
  trovata via ricerca web era giusta), ma i **valori di flag trovati
  online erano sbagliati**: i tag reali (`flag_meanings`/`flag_values`)
  riportano `{252, 253, 254, 255} = {Unknown, Snow, Water, Missing}`, non
  `{251=missing, 252=cloud, 253=snow, 254=sea, 255=background}` come
  suggerito da fonti generiche — nessun DN 251 definito, nessuna
  categoria "cloud" esplicita. Il campo `valid_range=[0,250]` del file
  conferma comunque la soglia gia' usata nello script (nessun impatto
  sulla logica di mascheramento, solo sui commenti/docstring, corretti).

  **Fix allo script prima dell'esecuzione**: `compute_ndvi()` in
  `process_ndvi.py` leggeva l'intero raster in memoria
  (`src.read(1)`) — per un file globale a 333m questo significa un
  array da decine di GB, non eseguibile su una macchina normale. Riscritto
  per leggere solo una **finestra** (`rasterio.windows.from_bounds`)
  corrispondente al bounding box dei comuni piemontesi + margine di
  sicurezza (`boundless=True, fill_value=255` per gestire in sicurezza
  eventuale sconfinamento del margine oltre i bordi del raster globale) —
  lettura in ~3 secondi indipendentemente dalla dimensione del file.
  Anche un piccolo fix cosmetico: `nodata=None` passato a `rasterstats`
  per contare tutti i pixel intersecati produceva un `NodataWarning`
  interno (default silenzioso a `-999`) — sostituito con `nodata=-1`
  esplicito (fuori dal range 0-255 del dato, stesso comportamento, nessun
  warning).

  **Esecuzione reale** (composito 2026-07-01/2026-07-10): **1180/1180
  comuni popolati**, nessun errore. Valori verificati a campione:
  Vercelli 0.62 NDVI medio ("dense", coerente con le risaie gia' trovate
  al 67-84% agricolo da CORINE); Torino 0.40 ("moderate", citta' ma con
  parchi/collina/Po nel perimetro comunale); Bardonecchia/Formazza
  0.44-0.49 con deviazione standard alta (0.26-0.28) e minimo vicino al
  limite teorico -0.08 — gradiente bosco di fondovalle/roccia nuda in
  quota, `pct_valid_pixels` 98-99% (non 100%, segno che il mascheramento
  neve/nuvole in quota funziona davvero). Distribuzione sui 1180 comuni:
  643 dense, 461 very_dense, 76 moderate, 0 sparse/no_vegetation —
  plausibile per luglio (piena stagione vegetativa).

  Pagine aggiornate (secondo giro): `data-sources.md` (sezione NDVI
  riscritta con il racconto completo — vicolo cieco HR-VPP, difficolta'
  di portale, verifica empirica, risultati reali), `data-model.md`
  (`municipality_ndvi` segnata popolata con valori reali),
  `paper-scientifico.md` (voce NDVI segnata "fatto"), `project-status.md`.

- **2026-07-17** — INGEST. Restyling identità visiva "calore" della
  dashboard Streamlit, su richiesta esplicita dell'utente ("frontend troppo
  minimalista e piatto, sembra un PDF"). Processo: analisi della struttura
  reale (`dashboard/`), mockup HTML statico (Artifact) per validare la
  direzione visiva prima di toccare il codice — un giro di feedback
  dell'utente ("sfondo troppo nero") ha spostato la base da quasi-nero a
  grigio ardesia prima dell'implementazione. Palette derivata dai colori
  già usati nei grafici (non introdotta ex novo). Toccati: `constants.py`
  (nuovi token `THEME_*`/`FONT_*`/`MAP_TILES`), `styling.py` (tipografia
  Fraunces/Manrope/JetBrains Mono, hero, card di navigazione via
  `st.container(key=...)`, striscia "numeri chiave"), nuovo `charts.py`
  (sfondo trasparente per Plotly, deliberatamente senza toccare i colori
  del testo per non rompere l'adattamento automatico chiaro/scuro di
  `st.plotly_chart(theme="streamlit")`), `Home.py` (hero/card/stats),
  tile Folium passate da chiare a scure (`CartoDB dark_matter`) in tutte
  le 7 mappe di `Home.py`/`03_analisi_spaziale.py`/`04_ondate_di_calore.py`.
  Corretto un claim non più valido nella wiki: una nota del 2026-07-15
  diceva che le card non erano stilizzabili via CSS per mancanza di un
  selettore stabile — falso, `st.container(key=...)` (già disponibile
  nella versione installata) espone la classe stabile `st-key-<key>`.
  Verificato con `py_compile` + `AppTest` su tutte e 5 le pagine (nessuna
  eccezione, database reale) e un avvio/arresto di server live; verifica
  visiva in browser reale non eseguita in questa sessione (nessun tool di
  automazione browser disponibile) — dichiarato esplicitamente come tale,
  non spacciato per completo.

  Pagine aggiornate: `dashboard.md` (nuova sezione "Restyling identità
  visiva", struttura cartelle aggiornata, claim obsoleto corretto),
  `index.md` (riga di sintesi dashboard).

- **2026-07-17** — LINT/FIX urgente. L'utente ha riaperto la dashboard dopo
  il restyling sopra e ha segnalato tre problemi: sfondo ancora nero (non
  il grigio ardesia atteso), **codice HTML grezzo visibile a schermo**,
  mappe scure giudicate "brutte, troppi casini". Diagnosi:
  - **Bug reale**: `render_hero()` e `_stat_tile_html()` in `styling.py`
    costruivano l'HTML con f-string multi-riga indentate secondo lo stile
    del codice Python (8 spazi). CommonMark (il parser usato da
    `st.markdown`, anche con `unsafe_allow_html=True`) tratta una riga
    indentata di 4+ spazi come **blocco di codice letterale**, non come
    HTML da renderizzare — da qui il codice visibile a schermo. Di
    conseguenza hero/card/stats non diventavano mai HTML vero: lo sfondo
    "nero" visto dall'utente era semplicemente il tema scuro nativo di
    Streamlit (`#0e1117` da `.streamlit/config.toml`), non il token
    `THEME_INK` che non veniva mai applicato. Fix: entrambe le funzioni
    riscritte come singola riga (nessun `\n`/indentazione nell'HTML
    prodotto), stesso pattern già usato (e funzionante) in
    `render_nav_card_header()`. Verificato con `AppTest` che nessuno dei
    7 blocchi markdown della Home inizi più con whitespace/newline.
  - **Regressione non approvata**: le tile Folium scure
    (`CartoDB dark_matter`) non erano mai state validate su un mockup reale
    (quello approvato mostrava una mappa come illustrazione SVG statica,
    non un vero tile Folium) — le etichette/strade del tile scuro
    competevano visivamente con i poligoni colorati sovrapposti.
    **`MAP_TILES` riportato a `"CartoDB positron"`** su richiesta esplicita
    dell'utente, con commento nel codice per non riprovare senza
    rivalidazione.
  - Causa separata già risolta in questa stessa giornata (vedi voce
    precedente più `dashboard.md`): un processo Streamlit rimasto vivo da
    *prima* delle modifiche aveva ancora in cache la vecchia
    `components/constants.py` (`ImportError: MAP_TILES`) — non lo stesso
    bug, ma ha reso la diagnosi iniziale più confusa. Terminato l'intero
    albero di processi e riavviato pulito.

  Pagine aggiornate: `dashboard.md` (correzione nella sezione "Restyling
  identità visiva").

- **2026-07-17** — FIX. Dopo il fix del bug HTML sopra, l'utente ha
  confermato le card corrette ma segnalato che **lo sfondo resta piatto e
  nero**, con un accenno di blu isolato "a lato". Causa root, distinta dal
  bug precedente: `.streamlit/config.toml` → `[theme.dark]` usava ancora
  `backgroundColor = "#0e1117"` / `secondaryBackgroundColor = "#161a23"`,
  i valori quasi-neri della sessione 2026-07-15, **mai aggiornati** quando
  sono stati introdotti i token `THEME_INK`/`THEME_SURFACE` (grigio
  ardesia) in `constants.py` più sopra in questa stessa giornata. L'utente
  usa il tema **scuro** di Streamlit (il default dichiarato in
  `[theme]` è `base = "light"`, ma l'esperienza riportata — sfondo nero,
  non bianco — implica che l'abbia selezionato manualmente dal menu
  Streamlit): quindi vedeva lo sfondo nativo quasi-nero ovunque, con hero e
  card (di poco più chiari) che vi galleggiavano sopra senza fondersi —
  letto come "sfondo sempre nero" nonostante il restyling. Fix: allineati
  `[theme.dark]` e `[theme.dark.sidebar]` ai token `THEME_INK` (`#1c2130`),
  `THEME_SURFACE` (`#262c3d`), `THEME_TEXT` (`#f1f3f8`) e `primaryColor`
  portato a `THEME_COLD` (`#3498db`, invece del blu `#60a5fa` scollegato
  dalla palette) — così lo sfondo nativo di **tutte e 5 le pagine** (non
  solo gli elementi custom della Home) coincide con l'identità "calore".
  Verificato con `AppTest` (nessuna eccezione) e riavvio completo del
  server (i cambi a `config.toml` non si applicano con l'hot-reload,
  richiedono restart — nota già presente in `dashboard.md` dalla sessione
  2026-07-15). Tema chiaro (`[theme]`) non toccato: il problema segnalato
  riguardava solo il tema scuro.

  Pagine aggiornate: nessuna ancora — sezione dedicata da aggiungere a
  `dashboard.md` se l'utente conferma che il fix risolve.

  **Seguito, stesso giorno**: l'utente ha confermato lo sfondo corretto ma
  chiesto un colore diverso per la sidebar (prima identica al contenuto
  principale). Aggiunto `THEME_INK_SIDEBAR = "#161a26"` (leggermente più
  scuro di `THEME_INK`) in `constants.py`, applicato a
  `[theme.dark.sidebar].backgroundColor` in `config.toml`. Restart completo
  del server (richiesto per i cambi a `config.toml`).

- **2026-07-17** — PRIMA ITERAZIONE DEL MODELLO STATISTICO ESPLICATIVO
  (nuovo script `src/analysis/spatial_regression.py`). Su richiesta
  dell'utente, non appena popolazione/CORINE/NDVI sono state tutte
  disponibili (vedi sessione NDVI sopra), avviata la fase 4 del piano del
  paper scientifico — con una decisione di sequenziamento discussa prima
  di scrivere codice: l'utente proponeva di raccogliere prima anche le
  altre covariate candidate (pendenza/esposizione da DEM, distanza
  dall'acqua, densità stradale OSM); consigliato invece di fare un primo
  giro di modellazione con quanto già disponibile e usare l'indice di
  Moran sui residui come segnale **data-driven** per decidere cosa
  aggiungere davvero, invece di raccogliere dati alla cieca — l'utente ha
  concordato, aggiungendo che il campione di comuni con temperatura
  crescerà comunque gradualmente nel tempo.

  **Fase 1 — OLS classico**: `load_regression_data()` unisce
  `kpi_annual_by_municipality` (temp. media 2000-oggi) con elevazione e
  densità di popolazione (`municipalities`), `pct_urban`
  (`municipality_land_cover`), `ndvi_mean` (`municipality_ndvi`) per i 63
  comuni con temperatura. VIF tutti <5 (nessuna multicollinearità grave).
  Risultato: R²=0.979, **dominato quasi interamente dall'elevazione**
  (-0.56°C/100m, p<0.001, fisicamente coerente col gradiente
  altimetrico). Popolazione (p=0.698) e % urbano (p=0.897) **non
  significativi** — in contrasto con l'ipotesi originale del paper
  (città/industria come fattore esplicativo). NDVI significativo
  (p=0.028) ma con **segno controintuitivo** (più verde → più caldo),
  sospetto iniziale: confondimento con l'elevazione (pianura agricola =
  molto verde a luglio + bassa quota calda).

  **Check di adeguatezza concordato**: Moran's I sui residui OLS (riuso
  di `build_inverse_distance_weights()`/`morans_i_permutation_test()` già
  scritte in `spatial_analysis.py`, pesi inverso-distanza) — **ancora
  significativo** (I=0.081, p=0.001): l'OLS classico non è adeguato per
  l'inferenza su questi dati, serve un vero modello a errore/lag
  spaziale, come previsto dal piano.

  **Fase 2 — modello spaziale vero**: a differenza di Moran's I (scritto
  a mano nel progetto per evitare dipendenze extra), qui la stima a
  massima verosimiglianza è abbastanza delicata da preferire una libreria
  testata — installate `libpysal==4.15.0`/`spreg==1.9.0` (verificata la
  compatibilità con Python 3.14.5 del progetto, nessun problema).
  Verificata l'API reale di `spreg` con un test sintetico prima di
  scrivere il codice definitivo (attributi `lm_lag`/`lm_error`/
  `rlm_lag`/`rlm_error`/`z_stat`/`betas`/`rho`/`lam`/`pr2` su
  `spreg.OLS`/`ML_Lag`/`ML_Error` — non tutti scontati, es. `OLS` non ha
  `z_stat` ma `t_stat`). Scritte `build_knn_weights()` (KNN k=5,
  row-standardized — scelta diversa dall'inverso-distanza della Fase 1:
  KNN evita nodi isolati/pesi degeneri, standard per `spreg`),
  `run_lm_diagnostics()` (`spreg.OLS` con `spat_diag=True`),
  `select_spatial_model()` (regola di decisione di Anselin: usa le
  versioni robuste dei test LM quando entrambe le versioni semplici sono
  significative), `fit_spatial_model()` (`spreg.ML_Lag`/`ML_Error`).

  **Risultato Fase 2**: caso non ambiguo — LM-lag p=0.351 (non
  significativo), LM-error p=0.0001 (fortemente significativo, **robusto**
  anche a p=0.0002) → **modello a errore spaziale**. Lambda=0.738
  (p<0.001, forte dipendenza spaziale nell'errore confermata). Con questo
  modello: elevazione resta dominante (p<0.001); **% urbano diventa
  significativo (p=0.011) con il segno atteso** (positivo: più urbano →
  più caldo) — la correzione spaziale **cambia una conclusione
  sostanziale**, non solo la validità statistica: l'OLS classico
  mascherava un effetto urbano reale. Popolazione resta non significativa
  (p=0.116). NDVI resta significativo (p=0.0037) con lo **stesso segno
  controintuitivo** anche dopo la correzione spaziale — quindi non è
  (solo) un artefatto di autocorrelazione, resta da approfondire nel
  paper.

  **Limite dichiarato esplicitamente**: la scelta del modello spaziale
  dipende dalla definizione della matrice pesi (KNN k=5 per `spreg`,
  inverso-distanza per il check Fase 1) — limite noto della spatial
  econometrics con campioni piccoli (n=63), da rivalutare quando il
  campione crescerà. Coerente con la decisione presa con l'utente di non
  aggiungere subito le altre covariate candidate, ma rilanciare questa
  stessa pipeline via via che arrivano nuovi comuni.

  Output: `output/spatial_regression.csv`,
  `output/spatial_regression_summary.txt` (OLS+VIF+Moran's I residui),
  `output/spatial_regression_spatial_model.txt` (diagnostica LM + modello
  spaziale finale).

  Pagine aggiornate: `statistical-analysis.md` (nuova sezione
  `spatial_regression.py`), `paper-scientifico.md` (punto 4 del piano
  aggiornato con risultato reale, prossimi passi rivisti), `project-status.md`,
  `index.md`.

- **2026-07-17** — NDVI PORTATO IN DASHBOARD. Su richiesta esplicita
  dell'utente ("aggiungiamo nel frontend i dati aggiunti?"), portata la
  covariata NDVI (popolata la stessa giornata, vedi sessione dedicata
  sopra) nella pagina Analisi Spaziale, stesso pattern già usato per uso
  del suolo/popolazione il 2026-07-16.

  **Nuova query** `get_ndvi_all()` in `components/queries.py` (join
  `municipality_ndvi`/`municipalities`/`provinces`, tutti i 1180 comuni —
  stesso pattern di `get_land_cover_all()`). **Nuovi token** in
  `constants.py`: `NDVI_COLORS` (gradiente marrone→verde, convenzione
  standard NDVI, deliberatamente diverso dalla scala blu→rosso di
  temperatura/trend per non confondere le due mappe a colpo d'occhio),
  `VEGETATION_CLASS_LABELS` (etichette italiane per i bucket categorici
  già scritti da `process_ndvi.py`).

  **Nuova mappa "NDVI — verde da satellite"** in `03_analisi_spaziale.py`,
  inserita dopo la mappa di densità di popolazione: colormap continua via
  `branca.colormap.LinearColormap`, tooltip con valore NDVI e classe di
  vegetazione, legenda a 5 fasce. Piccola estensione a
  `components/maps.py::render_gradient_legend()`: nuovo parametro
  `decimals` (default 1, invariato per le mappe esistenti) — l'intervallo
  NDVI reale dei comuni (0.33-0.87) è troppo stretto per il formato a 1
  decimale già usato da temperatura/popolazione, che avrebbe reso alcune
  fasce indistinguibili in legenda.

  **NDVI aggiunto come 4ª opzione** nel selettore `st.radio` dello scatter
  temperatura/uso del suolo/popolazione (prima 3 opzioni: % urbano, %
  industriale, densità di popolazione).

  **Testi corretti perché non più veri**: la pagina dichiarava in due punti
  (caption sotto la correlazione di Pearson, sezione Metodologia) che "un
  modello che isola l'effetto della quota" fosse pianificato ma non ancora
  costruito — falso da quando `spatial_regression.py` è stato scritto ed
  eseguito nella stessa giornata (vedi sessione precedente). Riscritti
  entrambi i punti con il risultato reale (l'effetto urbano diventa
  significativo col segno atteso solo nel modello a errore spaziale),
  dichiarato esplicitamente provvisorio (n=63). Aggiunta anche una voce in
  Metodologia sul limite temporale dell'NDVI (composito singolo di 10
  giorni, non una media pluriennale come le altre variabili) — stesso
  tipo di trasparenza già applicato a CORINE ("uno scatto del 2018").

  Verificato con `AppTest`: nessuna eccezione dopo le modifiche. Server
  live già in esecuzione (avviato in una sessione parallela per il
  restyling) non riavviato — le modifiche a file `.py` vengono ricaricate
  automaticamente da Streamlit, a differenza dei cambi a `config.toml`;
  verificato comunque `/_stcore/health` → 200.

  Pagine aggiornate: `dashboard.md` (nuova sezione "NDVI in dashboard +
  testi metodologici aggiornati").

- **2026-07-17** — INGEST. Sessione da una **seconda macchina** (una
  collaboratrice, non il titolare): repo clonata senza `.venv`/`.env`/DB —
  installate le dipendenze, poi scoperto che il DB reale del progetto non
  vive su questa macchina (porta 5432 occupata da un container Postgres di
  un progetto non correlato). Niente Docker/DB locale creato per questo
  progetto (deciso con l'utente dopo un primo tentativo scartato).

  Compito: aiutare il titolare a scaricare comuni extra oltre ai 63 già
  coperti, senza poterlo contattare per sapere quali. Ricostruiti i comuni
  già coperti **rasterizzando le preview PNG dei progetti QGIS** (tracciate
  in Git) contro i 1180 poligoni comunali ISTAT (anch'essi in Git) — metodo
  verificato (63/63 comuni ritrovati, separazione netta, tutti gli 8
  capoluoghi corretti). Scaricati poi 35 comuni nuovi da Open-Meteo fino al
  blocco del rate limit giornaliero, trovato e corretto un bug reale
  (confronto `int`/`str` su `istat_code` → 20 comuni scaricati due volte,
  deduplicati senza perdita di dati).

  File prodotti (fuori Git, `data/raw/`, da consegnare al titolare fuori
  canale — email/drive, non `git push`, per dimensione e per convenzione
  del progetto):
  `temperature_data_extra_helper_35comuni.csv`,
  `riepilogo_35_comuni_extra.csv`.

  Pagine aggiornate: `data-sources.md` (nuova sezione "Download
  collaborativo da una seconda macchina"), `etl-pipeline.md` (nuova sezione
  "Comuni extra in attesa di import", con i passi di pulizia/risoluzione
  `municipality_id` mancanti prima del caricamento nel DB),
  `project-status.md` (nuovo aggiornamento in cima alla cronologia).

- **2026-07-17** — LINT (leggibilità, nessun contenuto nuovo). Su
  richiesta esplicita dell'utente ("è scritta in maniera sporca"):
  le pagine create nell'ingest iniziale del 2026-07-04
  (`project-overview.md`, `architecture.md`, `concepts.md`,
  `config-reference.md`, `kpi-catalog.md`, `sql-queries.md`,
  `testing.md`) restano di riferimento — tabelle, paragrafi brevi,
  nessuna modifica necessaria. Le 5 pagine cresciute per accumulo di
  aggiornamenti cronologici in prosa densa sono state **riscritte
  mantenendo tutto il contenuto fattuale** (nessuna data/numero/bug
  rimosso), riorganizzandolo in sotto-sezioni datate, elenchi puntati con
  etichette in grassetto, tabelle per dati enumerabili (cluster, file
  scaricati) e blockquote per i riquadri "bug trovato":
  - `dashboard.md` (654 → 680 righe, la più densa: 5 pagine Streamlit +
    3 giri di restyling documentati in un'unica sequenza di paragrafi)
  - `data-sources.md` (464 → 447 righe)
  - `project-status.md` (278 → 275 righe: la sezione "Prossimo passo a
    maggiore impatto", una lunga sequenza di paragrafi "Aggiornamento
    YYYY-MM-DD", è diventata "Cronologia degli aggiornamenti principali"
    con un `###` per data)
  - `etl-pipeline.md` (261 → 265 righe, tocco più leggero: già
    ragionevolmente strutturata, solo i blocchi bug convertiti in
    blockquote)
  - `statistical-analysis.md` (350 → 372 righe, incluse due nuove tabelle
    per i cluster K-means che erano elenchi puntati densi)

  `data-model.md` e `gis-maps.md` verificate e giudicate già leggibili
  (struttura a sezioni/tabelle adeguata), non toccate. Nessuna pagina
  orfana rilevata, nessun claim contraddittorio trovato durante la
  rilettura completa.

- **2026-07-17 (pomeriggio)** — IMPORT DEI 35 COMUNI EXTRA + RICALCOLO
  COMPLETO A 98 COMUNI + CONSOLIDAMENTO FILE. Su richiesta dell'utente
  ("fai prima pull del progetto" per vedere il materiale lasciato dalla
  collaboratrice, poi "procedi"), portati a termine i due passi lasciati
  aperti dalla sessione precedente (import dei 35 comuni e ricalcolo a
  valle), poi due richieste aggiuntive di pulizia file.

  **Import**: letto `data/raw/temperature_data_extra_helper_35comuni.csv`
  con `dtype={'istat_code': str}` (necessario per non perdere gli zeri
  iniziali del codice ISTAT — lo stesso file, se ricaricato con
  `DataCleaner.load_data()`/`pd.read_csv()` senza specificare il dtype,
  avrebbe interpretato la colonna come intera). Passato manualmente
  attraverso gli stessi passi di `DataCleaner.clean_data()` (0 righe
  scartate, 666 outlier IQR), poi risolto `istat_code` → `municipality_id`
  via join contro `municipalities` (35/35 trovati, nessuna sovrapposizione
  con i 63 comuni già presenti). Caricato con
  `insert_temperature_for_municipalities()`: **63 → 98 comuni, 950.110
  righe** in `temperature` (verificato via query diretta).

  **Ricalcolo a valle** (stesso giro delle estensioni precedenti):
  elevazione ri-scaricata per tutti i comuni con temperatura
  (`fetch_elevation.py`, 98/98 popolati — la query è già scoperta sui
  comuni con dati, copre automaticamente anche i nuovi); `TRUNCATE
  heatwave_events` + `identify_heatwaves()` (**331 ondate**, da 190);
  `REFRESH MATERIALIZED VIEW` su entrambe le viste KPI
  (`kpi_annual_by_municipality` 2.646 righe, `kpi_annual_by_province`
  216); tutti e 5 i moduli di `src/analysis/` rieseguiti in sequenza
  (`trend_analysis`, `heatwave_stats`, `spatial_analysis` subito,
  `seasonal_analysis` in background — vedi sotto — e `spatial_regression`,
  prima riesecuzione dopo la sua introduzione lo stesso giorno); mappe
  QGIS rigenerate (`python-qgis-ltr.bat build_maps.py`).

  **Risultato più significativo, registrato onestamente**: a n=98 il
  modello a errore spaziale di `spatial_regression.py` **non conferma**
  il risultato più rilevante di n=63 — **% urbano non è più
  statisticamente significativo** (p=0.334, era p=0.011). Nessun errore
  di calcolo: stessa pipeline, solo più osservazioni. Aggiornati di
  conseguenza `wiki/pages/paper-scientifico.md` (il punto sul "primo
  risultato quantitativo" ora riporta anche il ribaltamento) e
  `dashboard/pages/03_analisi_spaziale.py` (la caption che dichiarava %
  urbano significativo era diventata falsa — corretta, non lasciata
  perché "era vera quando scritta": a differenza di questo log, i testi
  live nella UI devono riflettere lo stato attuale). Verificato con
  `AppTest`: nessuna eccezione.

  Il job `seasonal_analysis.py` (STL su 98 serie giornaliere) è stato
  lanciato in background e si è **disaccoppiato dal tracking del tool**:
  una notifica di "completato" è arrivata a ~44/98 comuni, mentre il
  processo ha continuato a scrivere file fino al completamento reale
  (98/98, riepilogo rigenerato) circa 56 minuti dopo l'avvio — verificato
  ignorando la notifica e controllando direttamente il filesystem
  (contenuto/timestamp di `output/seasonal_trend_summary.csv`) prima di
  considerarlo concluso. Risultato: ampiezza stagionale 27.4-35.3°C,
  trend in aumento in 95/98 comuni (da 62/63) — tra i 35 nuovi comuni,
  altri due casi non in aumento oltre a Briga Alta (Grondona -0.21°C,
  Pietraporzio 0.00°C), entrambi coerenti con un Mann-Kendall "no trend"
  non significativo, a differenza di Briga Alta che resta l'unico
  raffreddamento sia significativo sia sostanziale.

  **Consolidamento `data/raw/`** (richiesta esplicita dell'utente): i due
  file consegnati dalla collaboratrice, ridondanti dopo l'import, sono
  stati uniti invece di lasciati come file separati.
  `temperature_data_extra_helper_35comuni.csv` riformattato allo schema
  di `temperature_data_extra.csv` (`istat_code` → `municipality_id`) e
  appeso in coda (526.078 → 865.403 righe); `riepilogo_35_comuni_extra.csv`
  eliminato senza sostituto (tabella di comodo, resa inutile dall'import).
  `data/raw/` ora ha un solo file per gli "8 capoluoghi"
  (`temperature_data.csv`) e uno solo per tutti i comuni extra
  (`temperature_data_extra.csv`), indipendentemente da quale sessione li
  abbia scaricati.

  **Consolidamento `data/processed/`** (richiesta esplicita successiva
  dell'utente): la cartella aveva accumulato 5 file da sessioni diverse.
  Verificato prima di toccare nulla che `temperature_clean_extra_delta.csv`
  (19 comuni) fosse un sottoinsieme già interamente contenuto in
  `temperature_clean_extra.csv` (55 comuni) e che
  `temperature_clean_recent.csv` (delta 2026 per tutti i 63 comuni
  preesistenti) non avesse **nessuna riga in comune** con gli altri file
  su `(municipality_id, date)` — solo dopo aver confermato l'assenza di
  sovrapposizioni, uniti in 2 file lungo la stessa distinzione già usata
  dai loader (`insert_temperature()` per nome vs
  `insert_temperature_for_municipalities()` per ID): `temperature_clean.csv`
  (solo 8 capoluoghi, esteso a oggi: 75.976 → 77.560 righe) e
  `temperature_clean_extra.csv` (tutti i 90 comuni non-capoluogo: 526.078
  → 872.550 righe). Nel farlo, scoperto un dettaglio di schema non ovvio:
  la colonna `province` usa il nome del **comune** in
  `temperature_clean_recent.csv` ma il nome della **provincia** nello
  schema storico di `temperature_clean.csv` (differenza che riguarda solo
  Verbano-Cusio-Ossola/Verbania) — normalizzato prima di unire, altrimenti
  un futuro `insert_temperature()` non avrebbe trovato la provincia per
  quella riga. Eliminati `temperature_clean_extra_delta.csv`,
  `temperature_clean_recent.csv`, `temperature_extra_35_clean.csv` solo
  dopo aver verificato zero righe duplicate nei file consolidati e che
  77.560 + 872.550 = 950.110, combaciando esattamente col totale reale in
  `temperature`. `data/processed/` ora ha solo 2 file invece di 5.

  Pagine aggiornate: `etl-pipeline.md` (import + consolidamento raw e
  processed, sezione riscritta da "in attesa di import" a "completato"),
  `data-sources.md`, `data-model.md`, `statistical-analysis.md`
  (risultati completi a 98 comuni per tutti e 5 i moduli, inclusa la
  sezione dedicata al ribaltamento di `spatial_regression.py`),
  `project-status.md`, `gis-maps.md`, `dashboard.md`,
  `paper-scientifico.md`.

- **2026-07-18** — NUOVA PAGINA `comuni-coperti.md`, guida per il
  collaboratore. Richiesta esplicita dell'utente: un documento da passare
  a un collega perché possa scaricare nuovi comuni da Open-Meteo senza
  sovrapporsi ai 98 già coperti (lo stesso tipo di collaborazione già
  avvenuta il 2026-07-17 con un'altra collaboratrice, ma questa volta
  preparata **in anticipo** invece di essere ricostruita a posteriori
  dalle preview PNG delle mappe QGIS).

  Contenuto: elenco completo dei 98 comuni già in `temperature` (nome +
  codice ISTAT), organizzato per provincia con conteggio "N/totale comuni
  coperti" per dare un senso della copertura residua per zona; istruzioni
  sul formato esatto del CSV da consegnare (stesso schema già rodato il
  2026-07-17: `date, temp_max, temp_min, temp_mean, precipitation,
  province, data_source, istat_code, province_name`), con enfasi
  esplicita sul bug più probabile (istat_code letto come numero invece
  che come testo, perdendo gli zeri iniziali — già incontrato due volte
  in sessioni precedenti, sia lato encoding shapefile che lato import);
  promemoria sul limite giornaliero di Open-Meteo (~19-20 comuni/giorno,
  scoperto il 2026-07-17) e sul canale di consegna (fuori Git); riepilogo
  dei passi di import per chi riceverà il file (pulizia, risoluzione
  `municipality_id`, caricamento, ricalcolo a valle), con link diretto
  all'esempio concreto già eseguito.

  Dati estratti live dal DB (non trascritti a mano) per evitare che
  l'elenco vada fuori sincrono con lo stato reale.

  Pagina aggiunta a `index.md` sotto "Dati".

- **2026-07-18** — INGEST. Seconda sessione della stessa collaboratrice
  (seconda macchina, senza accesso al DB del titolare). `git pull`
  eseguito prima di tutto: ha portato il repo alla versione a 98 comuni
  (import del lotto precedente già fatto dal titolare) e introdotto
  `comuni-coperti.md`, la pagina scritta apposta per evitare che chi
  scarica da fuori debba ricostruire la copertura dai PNG QGIS come nella
  sessione precedente. Usata direttamente come fonte per il campionamento
  "farthest-point" sui 1082 comuni ancora scoperti — nessuna inferenza
  necessaria stavolta. Download Open-Meteo bloccato dal rate limit
  giornaliero dopo **57 comuni** riusciti, verificato riga per riga senza
  doppioni (il bug di confronto `int`/`str` della sessione precedente non
  si è ripresentato: questa volta la lista "già coperti" veniva da un'unica
  fonte, non da un confronto tra due CSV con dtype diversi).

  File prodotti (fuori Git, `data/raw/`, da consegnare al titolare fuori
  canale): `temperature_data_extra_helper_batch2.csv`,
  `riepilogo_57_comuni_batch2.csv`.

  Pagine aggiornate: `etl-pipeline.md` (nuova sezione "Comuni extra in
  attesa di import — 57 comuni"), `project-status.md` (nuova voce di
  cronologia + punto 11 nei prossimi passi). `comuni-coperti.md`
  deliberatamente **non** toccata in questa sessione: la sua stessa
  istruzione dice di aggiornarla solo dopo l'import, che non è di
  competenza di questa macchina (nessun accesso al DB).

- **2026-07-18** — RICERCA (SOLO WIKI, NESSUN CODICE SCRITTO): TROVATA UNA
  API REALE PER LA VALIDAZIONE ARPA. Domanda dell'utente: "manca il
  confronto con ARPA Piemonte, come potremmo implementarlo?" — fase 1 del
  piano paper ([Articolo scientifico](paper-scientifico.md)), bloccata dal
  2026-07-16 (`config.yaml`/`arpa_piemonte.url` risponde 404,
  `ArpaPiemonteDownloader` esistente ma mai funzionante).

  Ricerca web mirata (non solo la pagina pubblica "Banca Dati Storica",
  che resta dietro un'interfaccia a mappa): trovata un'API REST pubblica
  **senza chiave**, Django REST Framework, sotto
  `utility.arpa.piemonte.it/meteoidro/` — non documentata in nessuna pagina
  ufficiale linkata dal sito principale, scoperta seguendo un URL comparso
  a margine di risultati di ricerca generici. Confermato con richieste
  dirette (non solo lettura di documentazione): endpoint
  `stazione_meteorologica/` (anagrafica con `codice_istat_comune`,
  coordinate, quota, date attività) e `dati_giornalieri_meteo/
  ?fk_id_punto_misura_meteo=<codice>` (JSON paginato, `tmax`/`tmin`/
  `tmedia` giornalieri, un punto di test con 10.645 record dal 1993).
  Distinta da un'altra API trovata nello stesso dominio
  (`api_realtime/`, `/data_pie`, `/ggd`) che copre solo gli ultimi 6
  giorni — le due non vanno confuse.

  **Nessuna integrazione nel codice fatta in questa sessione** — solo
  esplorazione via `WebFetch`/`WebSearch` e documentazione del risultato.
  Resta da verificare (prima di scrivere qualunque script): quanti dei 177
  comuni già in `temperature` hanno davvero una stazione ARPA
  corrispondente (rete ARPA ~400 stazioni su 1180 comuni, sovrapposizione
  reale con i 177 non nota), il comportamento esatto della paginazione e
  di eventuali filtri di data, ed eventuali limiti di rate non documentati.

  Pagine aggiornate: `data-sources.md` (nuova sezione con gli endpoint
  trovati e cosa resta da verificare), `paper-scientifico.md` (fase 1
  aggiornata con il link alla nuova sezione).

- **2026-07-18** — VALIDAZIONE ARPA IMPLEMENTATA ED ESEGUITA (SEGUITO DELLA
  RICERCA DI SOPRA, STESSO GIORNO). Su richiesta esplicita dell'utente
  ("procedi"), implementata e portata a termine l'integrazione ARPA appena
  trovata via ricerca web.

  **Derisking preliminare** (query dirette all'API + al DB, prima di
  scrivere qualunque script): dei 336 stazioni nell'anagrafica ARPA
  (`stazione_meteorologica/`), quelle con sensore di temperatura (`TERMA`)
  attivo e `codice_istat_comune` tra i 177 comuni gia' in `temperature`
  sono **51** — inclusi tutti gli 8 capoluoghi di provincia. Verificati in
  questa fase anche due comportamenti non documentati dell'API: i
  parametri intuitivi `data_after`/`data_before` vengono ignorati
  silenziosamente (filtro corretto: `data_min`/`data_max`), e `page_size`
  non ha effetto sull'endpoint dei dati giornalieri (sempre ~366
  record/pagina, paginazione da seguire via `next`).

  **Scritto `src/data_acquisition/download_arpa.py`**: anagrafica stazioni
  scaricata una volta, matching comune→stazione (per i comuni alpini con
  piu' stazioni attive, sceglie quella con quota piu' vicina a
  `municipalities.elevation_m`), download giornalieri per stazione con
  salvataggio incrementale (stessa lezione di `download_extra_municipalities.py`).
  Eseguito realmente: 51/51 comuni, **451.502 righe** (`data/raw/arpa_temperature.csv`),
  un solo fallimento transitorio (`Remote end closed connection without
  response` su Borgomanero, non un limite di rate come quelli gia' visti
  con Open-Meteo) risolto ri-scaricando la singola stazione mancante e
  appendendola al CSV.

  **Nuova tabella `arpa_temperature`** (`sql/05_arpa_temperature.sql`,
  applicata manualmente come `03_land_cover.sql`/`04_ndvi.sql` — non fa
  parte di `01_init_database.sql`), nuovo metodo
  `DatabaseLoader.insert_arpa_temperature()` in `load_to_db.py` (stesso
  pattern di `insert_temperature_for_municipalities`, `ON CONFLICT
  (station_code, date) DO NOTHING`). Caricate 451.502 righe, tutte con
  overlap `(municipality_id, date)` su `temperature` (stesso range
  2000-01-01 → oggi scaricato apposta), ~2% `temp_max` nulli (sensori piu'
  vecchi con copertura non uniforme).

  **Scritto ed eseguito `src/analysis/validate_arpa.py`**: join
  `temperature`/`arpa_temperature`, bias/MAE/RMSE/correlazione di Pearson
  per comune. Risultato aggregato su `temp_max` (451.502 coppie):
  correlazione molto alta (r medio 0.966) ma **bias sistematico negativo
  di -1.71°C in media** (Open-Meteo sottostima le massime reali), range
  molto ampio per comune (+3.27°C Limone Piemonte, -7.05°C Valprato
  Soana). **Controllo aggiuntivo non pianificato in origine, fatto perche'
  il pattern sembrava non casuale**: il bias correla con l'elevazione del
  comune (r=-0.348, p=0.012, incrociando `arpa_validation.csv` con
  `municipalities.elevation_m`) — piu' alto il comune, piu' Open-Meteo
  sottostima. Interpretazione plausibile: un prodotto di rianalisi
  rappresenta una cella di griglia, non un punto, e in rilievo alpino
  complesso questo smussa le temperature estreme reali osservate da una
  stazione puntuale — coerente con l'ipotesi gia' scritta in
  `paper-scientifico.md` sull'autocorrelazione spaziale residua vista nel
  modello a errore spaziale, ora con un controllo empirico quantitativo a
  supporto.

  **Nota su `ArpaPiemonteDownloader`** (in `download_data.py`): lasciata
  intatta, non funzionante, con un commento che rimanda al nuovo script —
  non e' stata "riparata" perche' l'approccio originale (URL singolo
  configurato in `config.yaml`) non ha alcun endpoint reale dietro, non
  era un bug puntuale ma un intero approccio sbagliato.

  Pagine aggiornate: `data-sources.md` (nuova sezione con risultati reali
  del download e della validazione), `data-model.md` (nuova tabella
  `arpa_temperature`), `etl-pipeline.md` (nuova sezione "Validazione ARPA
  — nuova pipeline parallela"), `statistical-analysis.md` (nuova sezione
  con la tabella dei risultati e il controllo sull'elevazione),
  `paper-scientifico.md` (fase 1 segnata fatta con i risultati, prossimi
  passi aggiornati), `project-status.md` (nuova voce di cronologia),
  `index.md` (riga di `statistical-analysis.md` aggiornata).

- **2026-07-18** — VALIDAZIONE ARPA APPROFONDITA: BIAS SUI GIORNI CALDI +
  CONFRONTO A LIVELLO DI EVENTO (STESSO GIORNO, SU RICHIESTA ESPLICITA
  DELL'UTENTE). Dopo aver chiesto "come procederesti con le analisi di
  comparazione", l'utente ha scelto di procedere prima con l'analisi sui
  giorni caldi + confronto a livello di ondate (tra le opzioni proposte:
  confronto trend, nuova pagina dashboard, aggiornamento manoscritto —
  rimandate).

  **Esteso `src/analysis/validate_arpa.py`** con tre nuove funzioni:
  `hot_day_bias()` (bias/MAE/RMSE/r ristretti ai giorni con
  `arpa_temp_max` sopra soglia, invece che su tutti i giorni),
  `identify_heatwaves_from_series()` (reimplementazione Python pura,
  fedele alla logica PL/pgSQL di `identify_heatwaves()` in
  `01_init_database.sql` — sequenze di giorni calendariali consecutivi
  sopra soglia, non solo righe consecutive), `compare_heatwave_events()`
  (confronto per sovrapposizione temporale tra eventi Open-Meteo e ARPA
  nello stesso comune, framing precision/recall con ARPA come verità di
  terra).

  **Bug in corso d'opera**: `TypeError: Cannot compare Timestamp with
  datetime.date` — gli eventi Open-Meteo arrivano da Postgres come
  `datetime.date` (via `pd.read_sql`), quelli ARPA come `pd.Timestamp` (via
  `pd.to_datetime` dentro `identify_heatwaves_from_series`). Fix:
  normalizzati entrambi a `pd.Timestamp` dentro `_events_overlap()` prima
  del confronto.

  **Risultati reali, eseguiti sui 51 comuni con stazione ARPA**:
  - Bias sui giorni caldi: a tutti i giorni bias=-1.71°C/r=0.956; sopra
    30°C bias=-2.10°C/r=0.687; **sopra 35°C bias=-2.21°C/r=0.400**. Il bias
    medio non peggiora drammaticamente, ma la correlazione crolla — Open-Meteo
    perde la capacità di distinguere quali giorni estremi lo sono di più,
    proprio nella fascia rilevante per le ondate di calore.
  - Confronto a livello di evento (soglia 35°C/3gg, stessa logica DB):
    **ARPA (verità di terra) mostra 322 ondate reali nei 51 comuni, contro
    le 150 già rilevate da Open-Meteo in `heatwave_events`** per gli stessi
    comuni — **recall 31.4%** (Open-Meteo cattura meno di un terzo delle
    ondate reali), **precision 62%** (delle ondate rilevate, oltre un terzo
    non trova riscontro in un evento ARPA sovrapposto).

  **Implicazione per il progetto, non solo per la fase di validazione**:
  le 640 ondate totali già contate su 177 comuni (vedi cronologia
  precedente) sono quasi certamente un sottoconteggio sostanziale del
  fenomeno reale, non un numero prudente/conservativo — il risultato più
  importante di tutta la validazione ARPA, da scrivere nel paper come
  limite quantificato (non solo dichiarato qualitativamente come prima
  del 2026-07-18).

  Nuovi file in `output/`: `arpa_hot_day_bias.csv`,
  `arpa_heatwave_events.csv` (le 322 ondate ARPA, dettaglio per comune).

  Pagine aggiornate: `statistical-analysis.md` (due nuove sottosezioni),
  `paper-scientifico.md` (fase 1, approfondimento aggiunto),
  `project-status.md` (voce di cronologia estesa).

- **2026-07-18** — CONFRONTO TREND ARPA vs OPEN-METEO (SU RICHIESTA
  ESPLICITA DELL'UTENTE: "procedi con tutti i punti"). Aggiunte
  `load_arpa_annual_temperature()` e `compare_trends()` a
  `validate_arpa.py`: media annuale di `temp_mean` ARPA per i 51 comuni,
  Mann-Kendall + regressione lineare (stesse funzioni pure di
  `trend_analysis.py`, importate non riscritte), confrontate con
  `output/trend_analysis.csv` (Open-Meteo) gia' calcolato.

  **Risultato, buona notizia rispetto alle sezioni precedenti**: il trend
  di riscaldamento **regge** alla fonte dati — segno della pendenza
  concorde nell'88.2% dei comuni (45/51), 43/51 comuni con trend ARPA
  significativo (p<0.05) vs 40/51 Open-Meteo, differenza media di
  pendenza piccola (-0.095°C/decade). Controllato nel dettaglio: i 6
  comuni con segno discorde (Acceglio, Briga Alta, Castelmagno, Cuneo,
  Limone Piemonte, Novi Ligure) sono **tutti casi in cui almeno una delle
  due fonti non e' significativa** — nessun caso di due trend opposti
  entrambi significativi. A differenza del conteggio delle ondate di
  calore (sezione precedente, sottostimato di circa 2/3), il risultato
  "il Piemonte si sta scaldando in modo diffuso e significativo" non e'
  un artefatto della fonte dati.

  Nuovo file: `output/arpa_trend_comparison.csv`.

  Pagine aggiornate: `statistical-analysis.md` (nuova sottosezione),
  `paper-scientifico.md` (fase 1, contro-bilanciamento aggiunto),
  `project-status.md`.

- **2026-07-18** — NUOVA PAGINA DASHBOARD "VALIDAZIONE DATI" +
  AGGIORNAMENTO MANOSCRITTO (SU RICHIESTA ESPLICITA DELL'UTENTE: "procedi
  con tutti i punti"). Ultimi due dei tre fronti proposti dopo la
  validazione ARPA (il terzo, confronto trend, fatto nella voce di log
  precedente).

  **Dashboard**: nuova `dashboard/pages/06_validazione_dati.py` — non
  aggiunta come tab a una pagina esistente (la validazione ARPA non
  appartiene a nessun tema tra temporale/spaziale/ondate/download, è un
  argomento a sé: la qualità del dato). Contenuto: 4 metriche di sintesi +
  banner di avviso col risultato più importante (31.4% delle ondate reali
  rilevate), tab Panoramica (mappa dei 51 comuni colorata per bias,
  scatter bias/elevazione con retta OLS, istogramma distribuzione bias,
  tabella completa) e tab Dettaglio tecnico (bias per condizione,
  precision/recall evento, confronto trend, nota di metodologia). Nuove
  funzioni in `components/queries.py` (`get_arpa_validation()`,
  `get_arpa_hot_day_bias()`, `get_arpa_trend_comparison()`,
  `get_arpa_event_comparison_summary()`), stesso pattern
  `_output_path()`/`st.cache_data` delle altre.

  **Bug in fase di scrittura, corretto prima di verificare**: una prima
  bozza degli scatter nella tab Panoramica referenziava una colonna
  `station_quota` mai esistita in `arpa_validation.csv` (confusa con un
  campo visto solo nello script di download) e un dataframe placeholder
  mai completato — riscritti entrambi gli scatter prima di eseguire
  qualunque test: bias vs elevazione (join con `get_municipality_metadata()`
  per `elevation_m`, non presente nel CSV di validazione) e istogramma
  della distribuzione del bias.

  Aggiunta anche una CSV di riepilogo mai salvata prima
  (`output/arpa_event_comparison_summary.csv`, precision/recall/conteggi),
  per non dover ricalcolare il confronto a livello di evento a ogni
  caricamento della pagina.

  **Verifica**: `py_compile`, poi `streamlit.testing.v1.AppTest` (nessuna
  eccezione, metriche renderizzate coerenti con i CSV reali — 51, -1.71°C,
  0.966, 31%, 322, 150, 62.0%, 31.4%), poi server live riavviato
  (`taskkill` sul processo precedente + riavvio pulito, non un semplice
  hot-reload, per essere sicuri che la nuova pagina comparisse nella
  navigazione multipagina) e verificato `/_stcore/health` → 200 e
  `/validazione_dati` → 200.

  Pagine aggiornate: `dashboard.md` (struttura cartelle + nuova sezione
  "Validazione Dati" in "Contenuto delle pagine"), `index.md` (voce
  Dashboard: 5→6 pagine).

  **Manoscritto** (`paper/manoscritto.md`): sezione ARPA aggiornata senza
  toccare il resto del documento (che resta fermo a N=44 comuni — sync
  completo esplicitamente rimandato, fuori scope di oggi). Cambi mirati:
  §2.1 (bullet ARPA da **[DA FARE]** a **[FATTO]**, con metodo e numero di
  comuni), nuova sottosezione **§3.6** "Validazione contro osservazioni di
  stazione (ARPA Piemonte)" con tutti i risultati (bias, bias sui giorni
  caldi, confronto a livello di evento, confronto trend), §4.3 Limiti
  riscritto per riportare il sottoconteggio delle ondate come limite
  **quantificato** (non più solo dichiarato a parole) con l'implicazione
  esplicita per §3.2, nuova voce sul caveat di rappresentatività della
  stazione, 5 righe aggiunte alla tabella di tracciabilità in Appendice A,
  nota in cima al documento aggiornata (ARPA non è più tra i **[DA FARE]**).

- **2026-07-18** — INGEST + RICALCOLO: 98 → 177 COMUNI, IN DUE STEP.
  Sessione lunga sul lato copertura dati (in parallelo alla sessione
  ARPA sopra, che ha lavorato sul lato validazione).

  **Step 1 — 57 comuni dalla seconda sessione della collaboratrice**.
  `git pull` prima di tutto: ha portato il repo alla versione a 98 comuni
  (import del 2026-07-17 già fatto dal titolare) e alla nuova pagina
  [Comuni già coperti](comuni-coperti.md), scritta apposta la sessione
  precedente per evitare alla collaboratrice di dover ricostruire la
  copertura dai PNG QGIS come la prima volta. Nella cartella `data/raw/`
  erano presenti due file: `temperature_data_extra_helper_batch2.csv`
  (57 comuni, genuinamente nuovo, verificato zero sovrapposizioni con
  l'esistente) e **una copia di `temperature_data_extra_helper_35comuni.csv`**
  — stesso nome, stesse 339.325 righe, stessi 35 codici ISTAT del file
  già importato ed eliminato il giorno prima. Verificato contro il DB
  prima di toccarlo (tutti e 35 già presenti in `temperature`) e
  **scartato senza importarlo**: la voce di log della collaboratrice per
  questa sessione cita solo `batch2`, quasi certamente una copia locale
  rimasta sul suo disco da prima del `git pull` precedente, finita per
  errore nello stesso invio. Importare quel file avrebbe duplicato
  silenziosamente 339mila righe (nessun vincolo di unicità
  `(municipality_id, date)` in `temperature`). Import di `batch2`:
  pulizia (`DataCleaner`, 0 righe scartate) + risoluzione `istat_code` →
  `municipality_id` (57/57 trovati) + `insert_temperature_for_municipalities()`.
  **98 → 155 comuni.**

  **Step 2 — 22 comuni scaricati direttamente**. Lanciato
  `download_extra_municipalities.py --count 40` (non da una macchina
  esterna, dallo stesso ambiente con accesso al DB — la selezione esclude
  per costruzione i comuni già in `temperature`, quindi nessuna
  sovrapposizione possibile né coi 155 preesistenti né con `batch2`,
  verificato comunque a posteriori: zero codici ISTAT in comune). Il rate
  limit giornaliero, già in parte consumato dalla collaboratrice nella
  stessa giornata, è scattato dopo **22 comuni riusciti** — ma con un
  sintomo mai visto prima: nessun errore `429` esplicito, il processo è
  rimasto "vivo" ma **fermo per oltre 12 minuti** senza scrivere righe
  nuove nel CSV incrementale, con tempo CPU praticamente piatto (0:00:06
  invariato su più controlli), più coerente con un blocco silenzioso nei
  cicli di retry che con un fallimento pulito. Un primo tentativo di
  aspettare la fine del processo con un loop di attesa è fallito per un
  bug nello script di monitoraggio stesso (`[ ! -e /proc/PID ]` non ha
  senso in Git Bash su Windows — nessun vero filesystem `/proc`, la
  condizione risultava sempre vera, terminando il loop all'istante senza
  aver davvero controllato nulla) — diagnosticato verificando il processo
  con `tasklist` direttamente. Interrotto manualmente
  (`Stop-Process`) dopo aver verificato che i 22 comuni già ottenuti
  fossero completi (9.696 righe ciascuno — il salvataggio incrementale
  scrive un comune alla volta, quindi l'interruzione non ha corrotto
  nulla di già scritto) e importati normalmente. **155 → 177 comuni,
  1.716.094 righe in `temperature`.**

  **Bug reale trovato e corretto**: `fetch_elevation.py` interrogava
  l'Elevation API di Open-Meteo con tutte le coordinate in un'unica
  richiesta — funzionava fino a 100 comuni, ma con 177 ha restituito
  `400 Bad Request` (`"must not exceed 100 coordinates"`, letto dal corpo
  della risposta). Fix: richieste a lotti da `MAX_COORDS_PER_REQUEST =
  100`, risultati concatenati — nessun impatto sul resto della pipeline,
  tornerà rilevante a ogni multiplo di 100 comuni.

  **Ricalcolo completo a valle**: elevazione 177/177 (col fix sopra),
  `TRUNCATE` + `identify_heatwaves()` (**640 ondate**, da 331), refresh
  viste KPI (`kpi_annual_by_municipality` 4.779 righe), tutti e 5 i
  moduli di `src/analysis/` (incluso `seasonal_analysis.py`, ~112 minuti
  in background — il job ha continuato a scrivere file per diversi minuti
  dopo una notifica di completamento del tool rivelatasi prematura,
  ignorata verificando direttamente il timestamp del CSV di riepilogo
  finale prima di fidarsene, stesso problema già incontrato il
  2026-07-17), mappe QGIS rigenerate.

  **Risultato statistico più significativo**: a n=177,
  `spatial_regression.py` mostra che **NDVI smette di essere
  significativo** (oltre a % urbano, già non significativo da n=98). Ma
  non è solo il p-value a muoversi: il **coefficiente di NDVI crolla
  dell'85%** (da +1.089 a +0.161 tra n=98 e n=177) — un comportamento non
  spiegabile con la semplice riduzione dell'errore standard all'aumentare
  di n, più coerente con l'ipotesi che l'effetto visto a n=98 fosse in
  parte un artefatto di un campione ancora piccolo/non rappresentativo.
  Il coefficiente di % urbano invece resta piccolo ma stabile
  (+0.0056 → +0.0063) in entrambe le versioni — lì è cambiato solo il
  p-value, più coerente con un effetto debole ma reale in cerca di
  potenza statistica. Solo l'elevazione resta un predittore robusto e
  stabile in tutte e tre le versioni provate (n=63/98/177). Discusso con
  l'utente il significato pratico di questo pattern (richiesta esplicita:
  "questo cosa significa? non ha senso mantenere questo confronto?") —
  concordato di continuare a rieseguire il modello a ogni estensione, ma
  trattandolo come un **esercizio di convergenza** (il coefficiente si
  stabilizza o continua a spostarsi?) invece che come una "notizia" a
  ogni giro. Anche per `seasonal_analysis.py`: Briga Alta resta l'unico
  raffreddamento sia significativo (Mann-Kendall) sia sostanziale (STL),
  confermato per la terza estensione consecutiva del campione (n=63 →
  n=98 → n=177) — un segnale sempre più difficile da liquidare come
  rumore casuale del campionamento.

  **Consolidamento file** (richiesta esplicita dell'utente, stesso
  pattern del giorno prima): in `data/raw/`, `batch2` unito in
  `temperature_data_extra.csv` ed eliminato insieme al file stantio dei
  35 comuni e al riepilogo — tornato a 4 file. In `data/processed/`, i
  due file puliti di oggi uniti in `temperature_clean_extra.csv` dopo
  aver verificato zero sovrapposizioni su `(municipality_id, date)` —
  tornato a 2 file. Verificato **77.560 + 1.638.534 = 1.716.094**,
  combacia esattamente col totale reale in `temperature`.

  [Comuni già coperti](comuni-coperti.md) aggiornata con l'elenco
  completo dei 177 comuni (dati estratti live dal DB) e una nota rivista
  sul limite giornaliero di Open-Meteo: non un numero fisso — 19-20 la
  prima volta, 57 per la collaboratrice e solo 22 per il titolare lo
  stesso giorno — ipotesi non confermata che sia legato al volume di dati
  scaricato più che a un conteggio piatto di richieste.

  Pagine aggiornate: `etl-pipeline.md`, `data-sources.md`, `data-model.md`,
  `statistical-analysis.md` (risultati completi a 177 comuni per tutti e
  5 i moduli, tabella di confronto coefficienti n=63/98/177 per
  `spatial_regression.py`), `project-status.md`, `gis-maps.md`,
  `dashboard.md`, `paper-scientifico.md`, `comuni-coperti.md`.

- **2026-07-18 (tardo pomeriggio)** — INGEST: estensione copertura ARPA a
  218 comuni. Durante una discussione con l'utente su come riorganizzare
  la dashboard (selettore per pagina ARPA+Open-Meteo/solo ARPA/solo
  Open-Meteo, invece di una pagina "Validazione Dati" separata), rilevato
  che `download_arpa.py` filtrava il matching comuni↔stazioni solo sui
  177 comuni con Open-Meteo — non un limite reale dell'API. Aggiunti flag
  `--only-uncovered`/`--output-name`, resa la ripresa dopo interruzione
  sicura (nessuna cancellazione del CSV di output a ogni avvio), scaricati
  167 comuni nuovi senza errori (API ARPA senza segni di rate limit su
  questo volume), caricati in `arpa_temperature` (idempotente via `ON
  CONFLICT`). Totale: 51 → **218 comuni, 1.965.138 righe**. Selettore UI
  ancora da implementare (prossimo passo).

  Pagine aggiornate: `data-sources.md`, `data-model.md`, `project-status.md`.

- **2026-07-18 (sera)** — INGEST: selettore fonte dati (Open-Meteo / Solo
  ARPA / Confronto) implementato in Analisi Temporale e Ondate di Calore.
  Nuovo componente `dashboard/components/data_source.py`; nuove funzioni
  ARPA live in `dashboard/components/queries.py` (equivalenti ARPA delle
  funzioni/CSV Open-Meteo esistenti, verificate contro la semantica esatta
  delle viste SQL); nuova `identify_heatwaves_events()` in
  `heatwave_definitions.py` (versione Python multi-comune della soglia
  fissa canonica, per calcolare ondate su ARPA al volo). Pagina
  "Validazione Dati" tenuta invariata (scelta deliberata). Verificato con
  `AppTest` su tutte e 3 le combinazioni di fonte in entrambe le pagine,
  nessuna eccezione; verifica visiva in browser non eseguita (server
  Streamlit di una sessione precedente già in ascolto sulla porta 8501,
  non riavviato).

  Pagine aggiornate: `dashboard.md`, `project-status.md`, `index.md`.

- **2026-07-18 (sera, seconda parte)** — INGEST: server Streamlit
  riavviato su richiesta dell'utente (trovati e terminati 3 processi
  duplicati sulla stessa porta, riavviato uno pulito, health check 200).
  Selettore fonte esteso anche ad **Analisi Spaziale** dopo che l'utente
  ha fatto notare che l'esclusione iniziale era ingiustificata per metà
  della pagina (mappa coropletica, mappa trend, fascia altitudinale,
  cluster K-means, Moran's I sono temperatura-dipendenti, non solo le
  mappe uso del suolo/popolazione/NDVI). Bug bloccante trovato e risolto
  prima di scrivere il codice dashboard: `fetch_elevation.py` filtrava
  solo su Open-Meteo, lasciando `elevation_m` NULL per i 167 comuni
  solo-ARPA — ampliato a `temperature OR arpa_temperature` e rieseguito
  (344 comuni ora con elevazione). Nuove funzioni ARPA live in
  `queries.py` (`get_arpa_kpi_annual`, `get_arpa_trend_analysis`,
  `get_arpa_municipality_features`, `get_arpa_spatial_clustering`,
  `get_arpa_morans_i`), riusando le funzioni pure già esistenti in
  `src/analysis/spatial_analysis.py`. Verificato con `AppTest` su tutte e
  3 le combinazioni di fonte, nessuna eccezione (pagina lenta - 70-80s in
  ARPA/Confronto - per via delle mappe con centinaia di poligoni, costo
  preesistente non introdotto da questa modifica).

  Pagine aggiornate: `dashboard.md`, `data-model.md`, `project-status.md`.

- **2026-07-18 (sera, terza parte)** — INGEST: mappa "Velocità di
  riscaldamento per comune" in Analisi Spaziale corretta dopo che l'utente
  ha chiesto esplicitamente se, in modalità Confronto, la mappa mostrasse
  i colori di entrambe le fonti — non era vero (mostrava solo Open-Meteo).
  Chiesto con `AskUserQuestion` come preferire risolvere; scelta: due
  mappe affiancate (stessa scala colore condivisa). Spiegata la differenza
  con la mappa del bias già esistente in "Validazione Dati" (limitata
  strutturalmente ai 51 comuni con doppia copertura). Ri-verificato con
  `AppTest`, nessuna eccezione.

  Pagine aggiornate: `dashboard.md`.

- **2026-07-18 (sera, quarta parte)** — INGEST: portata la mappa bias
  Open-Meteo/ARPA (prima solo nella pagina dedicata) dentro Analisi
  Spaziale, modalità Confronto. L'utente ha quindi messo in dubbio il
  senso di tenere ancora "Validazione Dati" come pagina a sé, con gran
  parte del contenuto ormai duplicato altrove. Confermato con
  `AskUserQuestion`: **pagina `06_validazione_dati.py` eliminata**
  (`git rm`), contenuto residuo (scatter bias/elevazione, istogramma,
  bias per condizione, tabella completa, tabella trend comparativa,
  metodologia) spostato in Analisi Spaziale → Dettaglio tecnico →
  "Validazione ARPA — dettaglio" (solo in Confronto). Dashboard passa da
  6 a **5 pagine**. Verificato con `AppTest` su tutte e 3 le fonti +
  `Home.py`, nessuna eccezione.

  Pagine aggiornate: `dashboard.md`, `index.md`, `project-status.md`.

- **2026-07-18 (sera, quinta parte)** — INGEST: stesso bug della mappa
  trend (Confronto mostrava solo Open-Meteo) trovato di nuovo dall'utente
  sulla mappa "Dove si concentrano geograficamente le ondate" in Ondate di
  Calore. Corretta con lo stesso pattern (due mappe affiancate, stessa
  scala colore). Verificato che il server Streamlit già attivo (un solo
  processo, nessun duplicato questa volta) fosse sano dopo le modifiche
  (hot-reload automatico, nessun riavvio necessario per un cambio di solo
  codice Python). Verificato con `AppTest`, nessuna eccezione.

  Pagine aggiornate: `dashboard.md`.

- **2026-07-18 (sera, sesta parte)** — INGEST: Home.py estesa a Open-Meteo
  + ARPA combinati, su richiesta dell'utente ("sommarli"). Interpretato
  come unione dei comuni (non somma ingenua, evitando il doppio conteggio
  dei 51 comuni con entrambe le fonti) per copertura/mappa/tabella trend,
  e somma legittima per le righe di temperatura (osservazioni distinte).
  Nuove funzioni in `queries.py`: `get_arpa_overview_stats()`,
  `get_combined_trend_analysis()`, `get_combined_municipality_geometries_wkt()`,
  `get_combined_heatwave_count()` (quest'ultima evita di sommare due
  conteggi di ondate sullo stesso comune). Copertura Home ora 344/1180
  comuni (era 177/1180), tabella trend con nuova colonna "Fonte".
  Verificato con `AppTest`, nessuna eccezione.

  Pagine aggiornate: `dashboard.md`.

- **2026-07-18 (sera, settima parte)** — INGEST: rimossi dal frontend
  della dashboard tutti i riferimenti a wiki/script interni (13
  occorrenze in `Home.py`/`03_analisi_spaziale.py`/`04_ondate_di_calore.py`,
  cercate sistematicamente con un sub-agent dedicato), su richiesta
  dell'utente — la dashboard può essere vista da persone esterne al
  progetto. Commenti/docstring nel codice (mai renderizzati) lasciati
  intatti, fuori scope. Richiesta anche di cambiare il titolo "Heatwave
  Piemonte" — chiesto un nome sostitutivo con `AskUserQuestion`, risposta
  "ci penso": **ancora da fare**. Verificato con `AppTest`, nessuna
  eccezione.

  Pagine aggiornate: `dashboard.md`.

- **2026-07-18 (ottava parte)** — INGEST: tema chiaro nativo di
  hero/card di navigazione/striscia numeri chiave reso adattivo, su
  segnalazione dell'utente ("cambia solo lo sfondo in bianco ed è brutto")
  dopo il restyling 2026-07-17 che li aveva fissati su un'identità scura
  ignara del toggle chiaro/scuro. `components/constants.py::THEME_TOKENS`
  ora è `{"dark": {...}, "light": {...}}` invece di costanti fisse;
  `components/styling.py::inject_custom_css()` sceglie la coppia in base a
  `st.context.theme.type`. Stesso principio del tema scuro validato il
  2026-07-17: il pannello si fonde con lo sfondo nativo dello stesso modo
  invece di essere un blocco di colore a sé. Verificato **visivamente**
  (non solo `AppTest`): server live avviato, screenshot con Playwright +
  Chrome di sistema (`channel="chrome"`, nessun download di browser) prima
  e dopo lo switch tema dal menu Streamlit — chiaro coerente, scuro
  invariato dopo un reload (nessuna regressione). Limite noto e documentato
  in codice: il cambio tema dal menu è lato-client puro e non forza un
  rerun, quindi c'è uno sfasamento transitorio finché non arriva la
  prossima esecuzione dello script (si autocorregge da solo).

  Pagine aggiornate: `dashboard.md`, `index.md`.

- **2026-07-18 (sera, nona parte)** — INGEST: rimossa la connessione DB live
  dalla dashboard, su decisione esplicita dell'utente dopo discussione su
  dimensioni del DB (419 MB a 177 comuni Open-Meteo, poi 756 MB reali lo
  stesso giorno con l'estensione ARPA a 218 comuni fatta in parallelo) e
  costi di hosting: niente DB live in produzione, i dati cambiano solo
  quando l'utente rilancia la pipeline in locale. Scoperto durante
  l'esplorazione che anche i CSV di `output/` già usati da metà di
  `queries.py` erano esclusi da Git (`.gitignore`) — quindi il problema non
  era solo "togliere il DB", ma unificare tutto l'accesso dati su
  un'unica cartella versionata.

  Nuovo `src/data_processing/export_dashboard_data.py`: legge Postgres
  (Open-Meteo + ARPA) e i CSV di `output/` (inclusi i 177 file per-comune
  di `seasonal_decomposition/`, consolidati in un solo Parquet — da 121 MB
  CSV a 46 MB), scrive tutto come Parquet in `data/dashboard_export/`
  (69 MB totali, non intercettato da `.gitignore`). `dashboard/components/queries.py`
  riscritta (stesse ~35 funzioni pubbliche, stessa firma — nessuna pagina
  toccata): le ~24 funzioni che facevano query SQL ora leggono/filtrano
  Parquet in pandas; le funzioni già pure per l'analisi ARPA al volo
  (`identify_heatwaves_events`, `climate_clustering`,
  `morans_i_permutation_test`, `decompose`, ecc., aggiunte da una sessione
  parallela lo stesso giorno) non sono cambiate. Nuovo
  `requirements-dashboard.txt` minimale per il deploy (esclude
  psycopg2-binary/geoalchemy2/rasterio/cdsapi/netCDF4/spreg/libpysal; nota
  non ovvia: `sqlalchemy` resta necessaria per import transitivi innocui di
  `src/analysis/*.py`, mai una connessione vera).

  Il piano è stato rivisto a metà lavoro (via `/plan`) quando si è scoperto
  che una sessione parallela dell'utente aveva esteso ARPA a 218 comuni e
  aggiunto un'intera architettura "seconda fonte dati" a `queries.py` (25 →
  35 funzioni) — lavoro sospeso e ripreso solo dopo conferma esplicita
  dell'utente che quella sessione fosse conclusa, per non esportare uno
  snapshot a metà aggiornamento.

  Verificato: export rieseguito contro il DB reale, dimensioni controllate
  con `du -sh`; `streamlit.testing.v1.AppTest` su tutte le pagine reali
  (nessuna eccezione) — durante la verifica scoperto che
  `06_validazione_dati.py` non esiste più (rimossa e confluita nel
  selettore fonte dati, vedi sessione parallela sopra), script di verifica
  corretto di conseguenza. Nessun file sotto `dashboard/` importa più
  `db_manager` (verificato con grep). Postgres non è stato spento per un
  test "a interruttore" (altre sessioni potrebbero dipendere dal servizio).

  **Non ancora fatto** (deliberatamente, azione visibile su servizio
  esterno): push su GitHub e collegamento a Streamlit Community Cloud.

  Pagine aggiornate: `dashboard.md`, `project-status.md`.

- **2026-07-19** — INGEST: nuovo `src/data_processing/refresh_dashboard.py`,
  su richiesta esplicita dell'utente ("automatizzalo") dopo aver spiegato
  che il refresh della dashboard richiede due tipi di passi diversi. Lo
  script concatena i 6 moduli di `src/analysis/*.py` +
  `export_dashboard_data.py` in un solo comando; **esclude
  deliberatamente** `TRUNCATE`/`identify_heatwaves()`/`REFRESH MATERIALIZED
  VIEW` (operazioni sul DB, la prima distruttiva, finora sempre lanciate a
  mano caso per caso) — la scelta è stata chiesta esplicitamente
  all'utente con `AskUserQuestion`, che non ne coglieva la differenza:
  spiegata in termini semplici (TRUNCATE cancella e ricrea, l'export legge
  soltanto) e proceduto con l'opzione più sicura.

  Verificato per intero contro il DB reale (non solo lettura del codice):
  7/7 passi completati, nessun fallimento. Durante l'esecuzione osservati
  due salti di ore nei timestamp dei log (18:54→23:31 e 23:42→00:05),
  quasi certamente il PC in sospensione/idle nel frattempo — il processo
  Python è sopravvissuto e ripreso da solo, senza intervento. Il passo più
  lento è la STL (`seasonal_analysis`, ~25s/comune × 177 comuni). Notato a
  fine esecuzione che gran parte di `data/dashboard_export/` era già stata
  committata (in commit separati, non da questa sessione) nel frattempo;
  solo 2 file risultavano cambiati dopo il rerun di `validate_arpa.py`
  (`arpa_event_comparison_summary.parquet`, `arpa_trend_comparison.parquet`).

  Pagine aggiornate: `dashboard.md`.

- **2026-07-19** — INGEST: aggiornamento delta giornaliero Open-Meteo
  (`src/data_acquisition/update_recent_data.py`), su richiesta esplicita
  dell'utente. Prima del download, valutata e implementata su richiesta
  dell'utente una modifica all'ordine di scaricamento: i comuni con
  copertura ARPA (i 51 usati per il confronto/validazione) vengono ora
  scaricati **per primi** (`load_municipalities_with_data()` ordinata
  `has_arpa DESC, nome`), per garantire il delta utile al confronto anche
  se la quota giornaliera Open-Meteo blocca il run a metà. Archiviato un
  CSV incrementale residuo del 2026-07-17 (`temperature_data_recent.csv`)
  prima del run, per evitare che il nuovo run vi appendesse sopra dati già
  importati in `temperature` (rischio duplicati, la tabella non ha vincolo
  di unicità su `(municipality_id, date)`).

  Esecuzione completata senza blocco da quota (nessun 429, nessuno stallo):
  167/177 comuni aggiornati fino al 2026-07-19, 10 falliti per
  `ConnectionResetError` transitorio, di cui 2 (Marentino, Usseglio) tra i
  51 comuni ARPA. Dati scaricati ma **non importati** in `temperature` in
  questa sessione (esplicitamente richiesto dall'utente di fermarsi prima
  di questo passo, in attesa del file con i nuovi comuni dalla collega —
  workflow separato, vedi sezione "Come scaricare nuovi comuni" della
  stessa pagina).

  Pagine aggiornate: `comuni-coperti.md` (stato delta 2026-07-19, nuova
  sezione "Comuni prioritari per l'aggiornamento giornaliero" con i 51
  comuni ARPA e relativo esito).

- **2026-07-19** (poco dopo) — INGEST: due azioni su richiesta esplicita
  dell'utente. (1) Retry mirato dei 10 comuni falliti nel delta di prima
  (stesso giorno, `2026-07-19`) — riusciti 10/10, incluse le 2 priorità
  ARPA (Marentino, Usseglio). (2) Tentativo di scaricare comuni **nuovi**
  (mai coperti) partendo dalla provincia di Torino, storico completo
  2000→oggi, stesso criterio spaziale di
  `download_extra_municipalities.py` (farthest-point sampling) ma filtrato
  su una sola provincia — script scritto ad hoc nello scratchpad, riusa le
  funzioni esistenti del modulo (nessuna modifica al modulo stesso).

  Lanciato in background con un `Monitor` dedicato che intercetta i
  segnali di blocco quota, per poter interrompere il processo appena
  arriva un errore definitivo invece di lasciarlo bruciare ore nei retry
  di ogni comune successivo (rischio già documentato in questa stessa
  pagina per il tentativo del 2026-07-16). **Bloccato dalla quota dopo
  soli 18 comuni** (contro i 57+ dei run di delta) — prima conferma
  empirica diretta che la quota è legata al **volume** di dati scaricato
  (storico completo, ~9.700 righe/comune) più che al numero di richieste:
  osservazione coerente con l'ipotesi già scritta in questa pagina ma mai
  verificata con un confronto diretto nella stessa giornata. Fermato
  manualmente il processo non appena confermato il blocco (comune
  `Vestignè` fallito dopo 5 tentativi, comune successivo `Montanaro` già
  in blocco).

  Deliberatamente **non importato** nulla in `temperature` in questa
  sessione (né il delta né i comuni extra di Torino) — richiesta esplicita
  dell'utente di fermarsi prima di questo passo, in attesa del file della
  collega.

  Pagine aggiornate: `comuni-coperti.md` (esito retry, nuova sezione
  "Download comuni extra — provincia di Torino" con elenco scaricati,
  falliti, e indicazioni per la ripresa nella prossima sessione).

- **2026-07-19** (correzione, stessa giornata) — CORREZIONE su
  fraintendimento: l'utente ha chiarito che la richiesta di stamattina
  ("scarica le API di oggi... per fare un paragone con ARPA") non
  significava far girare il delta di aggiornamento né estendere la
  copertura spaziale a caso (le due azioni della voce di log precedente),
  ma **scaricare Open-Meteo (storico completo) per i comuni che hanno
  ARPA ma non ancora Open-Meteo**, per completare la mappa Bias
  Open-Meteo↔ARPA (oggi solo 51/218 comuni ARPA hanno anche Open-Meteo).
  L'utente si è giustamente lamentato di non essere stato consultato prima
  di agire su una richiesta ambigua — feedback salvato in memoria
  (`feedback_ask_before_data_downloads.md`, fuori da questo repo) per le
  prossime sessioni.

  Verificato via query diretta sul DB: 167 comuni hanno ARPA senza
  Open-Meteo (218 - 51). Per coincidenza 9 dei 18 comuni scaricati stamane
  a Torino hanno anche ARPA, quindi contano comunque per l'obiettivo reale
  (Ala di Stura, Angrogna, Carmagnola, Castagneto Po, Groscavallo,
  Moncalieri, Oulx, Prali, Viù) — restano **158** da scaricare. Nessun
  nuovo download lanciato in questa sessione (quota già bloccata da
  prima, l'utente ha scelto esplicitamente di aspettare il reset del
  giorno dopo invece di tentare comunque).

  Pagine aggiornate: `comuni-coperti.md` (nuova sezione "Obiettivo reale:
  completare la mappa Bias Open-Meteo↔ARPA" con la lista completa dei 167
  comuni per provincia, marcati i 9 già scaricati; correzione del
  paragrafo Torino con nota sul fraintendimento).

- **2026-07-19** — INGEST. Terza sessione della stessa collaboratrice
  (seconda macchina). `git pull` eseguito prima di tutto: ha portato il
  repo alla versione a 177 comuni e all'intera pipeline di validazione
  ARPA costruita dal titolare nel frattempo (`download_arpa.py`,
  `validate_arpa.py`, tabella `arpa_temperature`, export dashboard in
  Parquet). L'utente ha corretto esplicitamente l'obiettivo dei prossimi
  download, chiedendo di annotarlo in wiki: **l'obiettivo reale non è
  "estendere la copertura spaziale genericamente", ma scaricare Open-Meteo
  per i comuni che hanno già una stazione ARPA attiva ma non ancora dati
  Open-Meteo, per completare la mappa Bias Open-Meteo↔ARPA per comune** —
  nota aggiunta verbatim in `etl-pipeline.md`.

  Target preso direttamente dalla lista di 158 comuni già scritta dal
  titolare in `comuni-coperti.md` (167 con ARPA senza Open-Meteo, meno 9
  già scaricati per errore in una sessione precedente) — parsata dalla
  tabella markdown via script, non ritrascritta a mano. Download
  interlacciato per provincia (round-robin) invece che nell'ordine della
  tabella, per garantire copertura distribuita anche in caso di blocco
  quota a metà. Bloccato dalla quota giornaliera dopo **57/158 comuni**
  (su "Candia Canavese", stesso pattern di backoff crescente delle sessioni
  precedenti), zero doppioni verificati. Restano 101 comuni per le
  prossime sessioni.

  File prodotti (fuori Git, `data/raw/`, da consegnare al titolare fuori
  canale): `temperature_data_extra_helper_arpa_target.csv`,
  `riepilogo_57_comuni_arpa_target.csv`.

  Pagine aggiornate: `etl-pipeline.md` (nuova sezione "Comuni extra mirati
  alla validazione ARPA — 158 comuni target", con la nota sull'obiettivo
  reale, il metodo, e il risultato). `comuni-coperti.md` non toccata
  (aggiornamento post-import di competenza del titolare, come da
  istruzione già presente nella pagina).

- **2026-07-19** — INGEST (sessione frontend in parallelo, sola lettura
  DB via file già esportati — nessuna scrittura, nessun conflitto con la
  pipeline `refresh_dashboard.py` in corso su un'altra macchina/sessione
  in quel momento, confermato dall'utente). Su richiesta esplicita
  dell'utente ("le sezioni uso del suolo/densità popolazione/NDVI dentro
  Analisi Spaziale forse dovrebbero stare in un'altra pagina, la pagina è
  lunga e fa fatica a caricare tutto"), spostate mappa uso del suolo,
  mappa densità di popolazione, mappa NDVI e scatter
  temperatura/uso-del-suolo/popolazione da `03_analisi_spaziale.py` a una
  nuova pagina `05_contesto_territoriale.py` — contenuto spostato di peso,
  non riscritto. Posizionata **dopo** `04_ondate_di_calore.py` su
  richiesta esplicita (non in coda dopo Download Dati):
  `05_download_dati.py` rinumerata a `06_download_dati.py`. Link
  incrociati `st.page_link` aggiunti in entrambe le direzioni. Nessuna
  query nuova (stesse funzioni `st.cache_data` di `components/queries.py`
  richiamate da entrambe le pagine).

  Pagine aggiornate: `dashboard.md` (albero file, nuova voce cronologia
  2026-07-19, nuova sottosezione "Contesto Territoriale", nota nella
  sottosezione "Analisi Spaziale" che rimanda alla nuova pagina, nota di
  disambiguazione sul numero `06` già usato in passato dalla pagina
  "Validazione Dati" rimossa il 2026-07-18), `index.md` (5 → 6 pagine),
  `Home.py` (commento in testa con l'elenco pagine aggiornato).

- **2026-07-19** — Deciso e applicato il nuovo titolo del progetto (punto
  aperto dal 2026-07-18, vedi voce sopra). Proposti titoli in stile
  tesi/articolo scientifico via `AskUserQuestion`; l'utente ha scelto "Il
  riscaldamento del Piemonte: un'analisi spazio-temporale dei trend termici
  e delle ondate di calore". Applicato in `README.md` (H1), `config.yaml`
  (`dashboard.title`) e nell'hero di `Home.py` (`render_hero(title=...)`,
  "Heatwave Piemonte" spostato a eyebrow come brand). Non toccato
  `PROJECT_SUMMARY.md` (sorgente di pianificazione immutabile per
  `CLAUDE.md`) né i suffissi "— Heatwave Piemonte" negli `st.set_page_config`
  delle altre pagine (brand di navigazione, non il titolo).

  Pagine aggiornate: `project-status.md` (punto 13 chiuso), `dashboard.md`
  (sezione "Non ancora fatto" → esito).

- **2026-07-19** — Su richiesta dell'utente ("mi piace, ma non è forse molto
  esplicativo, rendilo più prolisso"), esteso il testo del widget "Confronto
  con il contesto nazionale/globale" nel tab Panoramica di
  `02_analisi_temporale.py`: aggiunto un blocco discorsivo dopo le 3
  metriche che spiega perché il confronto è un ordine di grandezza (periodi
  e metodologie diversi tra riferimenti di letteratura e trend locale sul
  periodo selezionato), il razionale scientifico per un riscaldamento
  alpino/prealpino spesso superiore alla media (minore capacità termica,
  riduzione neve, Mediterraneo come hotspot), l'avvertenza sui possibili
  effetti locali non isolati (isola di calore urbana, uso del suolo) e il
  rapporto numerico calcolato dal vivo tra trend locale e i due riferimenti.

  Pagina aggiornata: `dashboard.md` (sottosezione "Analisi Temporale",
  bullet del widget di confronto con nuova voce "Testo esplicativo esteso
  (2026-07-19)").

- **2026-07-19** — INGEST. Creata `dashboard/pages/08_citazioni_e_fonti.py`,
  nuova pagina statica (nessuna query DB) su richiesta dell'utente: elenco
  delle fonti dati reali (Open-Meteo, ARPA Piemonte, ISTAT confini/
  popolazione, Copernicus CORINE/NDVI) con link diretto via
  `st.link_button`, e bibliografia scientifica raccolta per il paper
  (riusa/organizza per ruolo la lista già raccolta in
  `wiki/pages/paper-scientifico.md` e `paper/manoscritto.md`), con le voci
  senza DOI/anno/volume verificati segnalate esplicitamente come
  "riferimento parziale" invece di presentarle come citazioni complete.
  Numerata `08` (non `07`) per lasciare posto a una futura pagina di
  sintesi divulgativa dell'articolo scientifico — quella pagina non è
  stata creata in questa sessione: l'utente aspetta il ricalcolo dei nuovi
  dati aggiunti la mattina del 2026-07-19 prima di scriverne il contenuto,
  ma ha chiesto di iniziare a discutere struttura/sottocapitoli e scelta
  degli articoli da citare (vedi risposta in chat, non ancora salvata come
  pagina wiki in attesa di conferma dell'utente). Verificato con
  `py_compile` e avvio reale di `streamlit run dashboard/Home.py`
  (richiesta HTTP 200 sia su `/` sia su `/08_citazioni_e_fonti`, nessun
  errore/traceback in log).

  Pagine aggiornate: `dashboard.md` (albero "Struttura reale" +
  "Cronologia in breve"), `index.md` (voce Dashboard, conteggio pagine
  6→7).

- **2026-07-19** — INGEST (stessa giornata, continuazione). Su richiesta
  esplicita dell'utente: confronto con report scientifici/istituzionali
  di ISTAT, ARPA, ISPRA "e altri se ne trovi", da scaricare o linkare, più
  completamento della bibliografia con le citazioni metodologiche
  classiche già proposte in chat (Mann-Kendall, Moran, STL, K-means,
  Anselin) e correzione del titolo del sottocapitolo "Limiti" (tolto
  "onestamente") nel piano della futura pagina 07.

  Cercati via `WebSearch`/`WebFetch`, verificati con richiesta HTTP diretta
  prima di scaricare (mai fidandosi solo del titolo del risultato di
  ricerca): 4 report istituzionali reali (SNPA *Il clima in Italia nel
  2025*, ARPA Piemonte *Il clima in Piemonte — Anno 2025*, ISTAT
  *Statistica Focus METEOCLIMA 2022*, ISPRA *Focus Le città*) scaricati in
  `paper/references/` (nuova cartella, ~35 MB). Trovati anche due articoli
  peer-reviewed che completano titoli già presenti in bibliografia dal
  2026-07-16 come riferimenti parziali — dettagli verificati via l'API
  pubblica di Crossref, non a memoria: Settanta et al. (2024,
  *Theoretical and Applied Climatology*, DOI 10.1007/s00704-024-05063-w,
  fonte esatta del dato "+7.5 giorni/decade" già citato senza fonte
  precisa) e Capozzi et al. (2025, *Atmospheric Research*, DOI
  10.1016/j.atmosres.2025.108013).

  **Correzione in corso d'opera**: l'utente ha chiesto esplicitamente di
  non escludere gli articoli scientifici scaricati dal versionamento Git
  ("non me li eliminare... li voglio leggere") dopo che una prima bozza di
  questo lavoro aggiungeva `paper/references/*.pdf` a `.gitignore` per
  contenere le dimensioni — modifica annullata subito, nessun file
  cancellato in nessun momento (il `.gitignore` controlla solo cosa Git
  traccia, non cosa esiste su disco). Recuperato anche un preprint ad
  accesso aperto su Research Square per Settanta et al. (gli stessi autori
  lo hanno reso pubblico prima della revisione tra pari), scaricato per
  intero in `paper/references/Settanta_2024_extreme_heat_events_Italy_PREPRINT.pdf`
  — per Capozzi et al. nessuna versione aperta trovata (solo un abstract
  di conferenza collegato, non un full paper), lasciato come link/DOI.

  Pagine aggiornate: `paper/references/README.md` (nuovo, indice
  completo con link/dimensioni/motivazione di ogni fonte),
  `paper/manoscritto.md` (Bibliografia + due nuove sottosezioni "Report
  istituzionali di confronto" e "Riferimenti metodologici"),
  `paper-scientifico.md` (letteratura completata, due nuove sezioni allo
  stesso contenuto, più una nuova sezione "Pagina dashboard 'Sintesi
  della Ricerca' (07)" che fissa per la prima volta i sottocapitoli
  concordati in chat), `dashboard.md` (pagina `08_citazioni_e_fonti.py`
  ampliata con le stesse due sezioni + bibliografia completata,
  verificato con `py_compile`).

- **2026-07-19** — INGEST (stessa giornata, terza continuazione). Chiuse
  tutte le voci di bibliografia ancora segnalate come "riferimento
  parziale"/"titolo esatto da verificare" (l'utente ha chiesto perché
  fossero lì): verificate una per una via API Crossref (mai a memoria).
  Completate con autori/rivista/volume/pagine/DOI reali: Nairn & Fawcett
  (2014, IJERPH — **corretto un errore**: il coautore raccolto il 16/7
  come "Fenwick" è in realtà Fawcett), Morabito et al. (2021, Sci. Total
  Environ.), Bassani et al. (2022, Urban Climate), Milelli et al. (2023,
  Urban Climate), Pauly et al. (2024, Urban Climate — lo "studio numerico
  UHI Torino 2019"), De Razza et al. (2024, Frontiers in Earth Science —
  open access, scaricato per intero), Petkov (2015, Advances in
  Meteorology — open access Hindawi/arXiv, scaricato per intero).

  **Capozzi et al. (2025, Apennines)**: primo tentativo di accesso via
  ScienceDirect risultava paywalled, non scaricato. L'utente ha scaricato
  il file da solo — i primi 3 tentativi hanno preso per errore altri
  articoli dello stesso fascicolo di *Atmospheric Research* vol. 319
  (editoriale + due paper non pertinenti su ENSO/IOD e polvere sahariana),
  scoperti come sbagliati verificando il contenuto reale con `pdftotext`
  (mai fidandosi del nome del file) invece di assumerli corretti, ed
  eliminati su richiesta esplicita dell'utente. Il file corretto è
  arrivato al tentativo successivo, verificato allo stesso modo —
  **scoperta**: l'articolo è in realtà open access nativo (licenza CC
  BY), non paywalled, e contiene la fonte esatta del dato "+134%" già
  citato dal 16/7 senza riferimento preciso — corretto anche un errore
  geografico nella raccolta iniziale (il dato riguarda gli **Appennini**,
  non "Nord Italia/Arco Alpino" come scritto in `paper/manoscritto.md`
  §1.1 prima di oggi).

  Pagine aggiornate: `paper/references/README.md` (tabelle
  "scaricati"/"non scaricati" riorganizzate con tutte le voci complete),
  `paper/manoscritto.md` (Bibliografia + correzione §1.1 Introduzione),
  `paper-scientifico.md` (dettaglio del percorso Capozzi), pagina
  dashboard `08_citazioni_e_fonti.py` (bibliografia completata,
  verificato con `py_compile`).

- **2026-07-19** (sera) — INGEST: import completo dei 57 comuni
  ARPA-target consegnati dalla collaboratrice (vedi voce precedente),
  eseguito dal titolare/IA su richiesta esplicita ("implementali"). Pulizia
  + join `istat_code` → `municipality_id` + `insert_temperature_for_municipalities`
  (552.729 righe, **177 → 234 comuni**) + ricalcolo a valle completo
  (elevazione, `TRUNCATE`+`identify_heatwaves()` → **770 ondate**, refresh
  viste KPI → **6.318 righe**). Trovato e documentato un problema tecnico
  non bloccante: `REFRESH MATERIALIZED VIEW CONCURRENTLY` fallisce perché
  manca un indice univoco sulle viste KPI — refresh eseguito senza
  `CONCURRENTLY`, segnalato come miglioria futura.

  **Errore di processo, corretto su feedback dell'utente**: rilanciato
  `download_arpa.py` di iniziativa propria (seguendo una nota lasciata
  dalla collaboratrice in `etl-pipeline.md`) senza chiederlo esplicitamente
  — l'utente ha fatto notare la cosa ("ma cosa intendi per download arpa?
  devi solo unire i dati"), il processo è stato fermato subito e ripreso
  solo dopo conferma esplicita che serviva davvero per completare la mappa
  Bias. Stessa classe di errore già annotata in memoria
  (`feedback_ask_before_data_downloads.md`) — non ancora risolta del tutto,
  da rinforzare.

  Download ARPA completato in due riprese (un'interruzione ambientale del
  processo in background senza traccia di errore Python, ripreso
  automaticamente grazie alla logica di resume su file): **108/234 comuni
  Open-Meteo hanno ora anche ARPA** (era 51, 100% di corrispondenza con la
  lista target). Pipeline di analisi (`refresh_dashboard.py`) rieseguita
  per intero, anch'essa interrotta una volta a ~106 minuti (stessa
  anomalia ambientale, 208/234 comuni STL completati) e ripartita da zero
  con successo (127 minuti la sola STL, tutti e 7 gli step completati).
  Risultati di validazione ARPA aggiornati sul campione a 108 comuni: bias
  -1.59°C (quasi invariato da -1.71°C), ma **recall delle ondate crollato a
  16.4%** dal 31.4% originale — non ancora spiegato, segnalato come domanda
  aperta per il paper.

  File consolidati su richiesta esplicita dell'utente ("riunisci i file
  csv"), stesso pattern delle sessioni precedenti: lotto della
  collaboratrice unito in `temperature_data_extra.csv` e
  `temperature_clean_extra.csv`, file ridondanti eliminati, verificato
  77.560 + 2.191.263 = 2.268.823 combacia col DB. **Non** consolidato
  `temperature_data_extra_torino_2026-07-19.csv` (18 comuni non ancora
  importati) per non rompere la corrispondenza file↔DB.

  Pagine aggiornate: `comuni-coperti.md`, `etl-pipeline.md`,
  `project-status.md`, `statistical-analysis.md` (numeri di validazione
  ARPA ricalcolati su 108 comuni in tutte le sottosezioni).

- **2026-07-19** (sera, seguito) — FIX: l'utente ha segnalato che la mappa
  "Bias Open-Meteo vs ARPA per comune" mostrava ancora ~55 comuni invece di
  108, e ha corretto un equivoco: non esisteva nessun intervento parallelo
  sul frontend (si era assunto il contrario in precedenza, vedendo file
  `dashboard/pages/` rinominati/aggiunti senza che fossero stati toccati in
  questa sessione). Causa reale: un processo Streamlit locale, avviato dall'
  utente alle 14:02:42 (prima che l'export dati finisse alle 16:09),
  serviva ancora dati vecchi in cache (`st.cache_data(ttl=600)` — TTL
  scaduto più volte ma la sessione del browser non aveva mai rieseguito lo
  script dopo l'aggiornamento dei dati).

  Trovati e corretti anche **numeri hardcoded ormai stantii** nel codice
  del frontend (commenti/didascalie, non logica — la logica che conta i
  comuni combinati era già dinamica e corretta): "51"→"108" e
  "177"→"234" in `Home.py`, `components/data_source.py`,
  `components/queries.py`, `pages/03_analisi_spaziale.py`,
  `pages/04_ondate_di_calore.py`, `pages/08_citazioni_e_fonti.py`.

  **Trovato un cambiamento scientifico reale, non solo un numero da
  aggiornare**: in `pages/05_contesto_territoriale.py`, la narrazione sul
  modello a errore spaziale citava p=0.19 (non significativo) per "%
  urbano" — con il campione esteso a 234 comuni, il modello ML spatial
  error (`output/spatial_regression_spatial_model.txt`) mostra ora
  **p=0.031 (significativo)** per la stessa variabile, mentre NDVI resta
  non significativo e il suo coefficiente continua a restringersi verso
  zero (+0.16 → +0.10). Riscritta la sezione per riflettere il nuovo
  risultato e segnalare esplicitamente l'instabilità tra un aggiornamento
  e l'altro come limite da monitorare, non come conferma.

  Processo Streamlit riavviato pulito (credentials.toml creato per
  saltare il prompt email interattivo di onboarding, mai configurato
  prima su questa macchina). Verificato con `AppTest`: Home + tutte le 6
  pagine numerate, nessuna eccezione, caption della mappa Bias confermata
  a "108 comuni" nel testo effettivamente renderizzato (non solo nel
  codice sorgente).

  Pagine aggiornate: `dashboard/Home.py`, `dashboard/components/data_source.py`,
  `dashboard/components/queries.py`, `dashboard/pages/03_analisi_spaziale.py`,
  `dashboard/pages/04_ondate_di_calore.py`,
  `dashboard/pages/05_contesto_territoriale.py`,
  `dashboard/pages/08_citazioni_e_fonti.py`.

- **2026-07-19** (sera, seguito) — INGEST. Creata
  `dashboard/pages/07_sintesi_della_ricerca.py`, la seconda pagina
  pianificata in [Articolo scientifico](paper-scientifico.md): sintesi
  divulgativa (non l'articolo tecnico, che resta in `paper/manoscritto.md`)
  dei dati raccolti e dei risultati, con ogni affermazione citata. Prima
  di scriverla, verificato lo stato reale post-ricalcolo (l'utente aveva
  detto "procediamo" dopo aver confermato che il nuovo calcolo dati della
  mattina era finito): **non bastava fidarsi di `paper/manoscritto.md`**,
  rimasto fermo ai numeri di 44 comuni/§3.5 "[DA FARE]" — letti invece
  `output/trend_analysis.csv`, `output/morans_i_summary.csv`,
  `output/spatial_analysis.csv`, `output/spatial_regression_spatial_model.txt`
  e le sezioni più recenti di `project-status.md`/`statistical-analysis.md`
  per i numeri reali a 234 comuni.

  **Scoperta di sostanza, non solo di numeri**: il modello a errore
  spaziale rieseguito a n=234 mostra ora **% urbano significativo**
  (p=0.031, coefficiente positivo, segno atteso) mentre **NDVI non lo è
  più** (coefficiente sceso a +0.10) — invertito rispetto a n=98 dove era
  il contrario. Prima vera conferma quantitativa, seppur provvisoria,
  dell'ipotesi originale del progetto (uso del suolo come fattore
  esplicativo oltre la quota). Trovati anche 2 comuni alpini (Argentera,
  Briga Alta) con trend di **raffreddamento** statisticamente
  significativo — dettaglio onesto incluso nella pagina invece di
  presentare il riscaldamento come unanime.

  **Scelta implementativa**: la pagina riusa le query esistenti in
  `components/queries.py` (`get_trend_analysis`, `get_morans_i_summary`,
  `get_spatial_analysis`, `get_arpa_validation`,
  `get_arpa_event_comparison_summary`, ecc.) invece di numeri scritti a
  mano, così i valori mostrati restano sempre aggiornati insieme al resto
  della dashboard — coerente con l'architettura a export statico già
  documentata in `dashboard.md`. Verificato con `streamlit.testing.v1.AppTest`
  (nessuna eccezione, tutti i numeri calcolati corrispondono a quelli letti
  a mano dai file di output) oltre che con un avvio reale (HTTP 200 su
  `/07_sintesi_della_ricerca`).

  **Non ancora fatto**: `paper/manoscritto.md` resta al livello di
  dettaglio di 44 comuni (§3.1-3.6 e Abstract) — la nuova pagina dashboard
  usa i numeri correnti (234 comuni), quindi dashboard e manoscritto
  tecnico sono temporaneamente disallineati. Segnalato all'utente,
  aggiornamento del manoscritto lasciato come attività separata.

  Pagine aggiornate: nessuna pagina wiki di dominio ancora sincronizzata
  con questa pagina dashboard oltre a questo log — da fare al prossimo
  giro di lint (vedi `CLAUDE.md`, workflow Lint).

- **2026-07-19** (sera, seguito) — FIX su richiesta esplicita dell'utente:
  ripulito il testo di `06_sintesi_della_ricerca.py` (allora ancora `07`)
  da tutti i trattini lunghi "—" (sostituiti con due punti/virgole/frasi
  riformulate, lasciati invariati solo i trattini brevi "–" degli
  intervalli numerici come "2000–2026") e sostituiti i riferimenti interni
  "(§4)"/"(§5)"/"(§6)" — non comprensibili a un lettore senza numerazione
  visibile delle sezioni — con il nome vero della sezione tra virgolette
  («Cosa abbiamo trovato», «Uso del suolo e popolazione», «Limiti»).
  Verificato di nuovo con `py_compile` e `AppTest` dopo le modifiche.

  Subito dopo, seconda richiesta: spostare Download Dati **dopo** Sintesi
  della Ricerca (era stata creata come `07`, dopo `06_download_dati.py`).
  Rinominati i file (`git mv` per `06_download_dati.py`, `mv` semplice per
  `07_sintesi_della_ricerca.py` perché ancora non tracciato in Git):
  **`06_sintesi_della_ricerca.py`** e **`07_download_dati.py`**.
  Aggiornati tutti i riferimenti incrociati trovati via `grep` sull'intera
  cartella `dashboard/`: il link "Download Dati" dentro la stessa pagina
  sintesi e dentro `08_citazioni_e_fonti.py` (entrambi puntavano a
  `06_download_dati.py`), il docstring interno di entrambi i file
  rinominati (uno diceva ancora `05_download_dati.py`, stale da una
  rinumerazione precedente mai corretta nel docstring), e l'elenco pagine
  nel docstring di `Home.py`. Verificato con `py_compile` e `AppTest` su
  tutte e 4 le pagine coinvolte (Home, 06, 07, 08), nessuna eccezione.

  Pagine aggiornate: `dashboard.md` (albero "Struttura reale"),
  `index.md` (voce Dashboard), `paper-scientifico.md` (titolo sezione e
  nome file aggiornati da `07` a `06`). Nota: le voci precedenti di questo
  log che citano `07_sintesi_della_ricerca.py` **non sono state riscritte**
  (il log è cronologico e append-only per convenzione di `CLAUDE.md`) —
  descrivono correttamente lo stato al momento in cui furono scritte,
  prima di questa rinumerazione.

- **2026-07-20** — INGEST. `git pull` eseguito su richiesta dell'utente
  ("fai pull del progetto e controlla i nuovi aggiornamenti"): fast-forward
  pulito, 52 commit (`c2be200..d062018`), nessun conflitto (unica cartella
  non tracciata locale, `.github/`, non toccata dal pull). I commit portati
  includevano già propri aggiornamenti wiki (pagina "Contesto Territoriale"
  separata, pagina "Sintesi della Ricerca" creata e rinumerata `06`,
  pagina "Citazioni e Fonti", bibliografia completata, correzioni di numeri
  hardcoded 51→108/177→234) — wiki già sincronizzata con quello stato,
  nessuna azione necessaria oltre alla lettura.

  L'utente ha poi comunicato che il progetto **è stato messo online**:
  dashboard pubblicata su Streamlit Community Cloud,
  https://heatwave-piemonte.streamlit.app, push su GitHub + collegamento
  al servizio completati senza problemi (confermato dall'utente via
  `AskUserQuestion`, non verificabile da codice/log locale). Questo
  chiudeva un punto esplicitamente lasciato aperto nella wiki dal
  2026-07-18 (`project-status.md` punto 9, `dashboard.md` sezione "Nessuna
  connessione DB live"): entrambe le pagine dicevano ancora "push su
  GitHub + collegamento a Streamlit Community Cloud non ancora fatti".

  Pagine aggiornate: `project-status.md` (punto 9 chiuso con data/URL,
  riga "Dashboard Streamlit" nella tabella Settimana 3 aggiornata da 6 a
  8 pagine reali e marcata pubblicata), `dashboard.md` (sezione "Nessuna
  connessione DB live" chiusa con nota di deploy, inclusa la conferma che
  Streamlit Community Cloud usa `dashboard/requirements.txt`, non la
  root, coerente con la nota tecnica già scritta il 2026-07-19 in quel
  file). Non toccato `README.md`: la checklist "Settimana 3" è la
  roadmap di pianificazione originale (tutte le voci restano `[ ]` per
  convenzione, incluse altre già completate da tempo, es. "Dashboard
  Streamlit") — sorgente grezza immutabile per `CLAUDE.md`, non va
  editata per riflettere lo stato reale.

- **2026-07-20** (seguito) — FIX su segnalazione dell'utente: le card di
  navigazione nella Home (`dashboard/Home.py`) coprivano solo Analisi
  Temporale, Analisi Spaziale e Ondate di Calore — le 4 pagine aggiunte
  in sessioni precedenti (Contesto Territoriale, Sintesi della Ricerca,
  Download Dati, Citazioni e Fonti) non avevano una card e restavano
  raggiungibili solo dalla sidebar. Aggiunta una seconda riga di 4 card
  (`st.columns(4)`), stesso componente `render_nav_card_header()` e
  stesso `CARD_HEIGHT` della prima riga, icone allineate al titolo
  `st.title` di ciascuna pagina. Verificato con `py_compile`,
  `streamlit.testing.v1.AppTest` (nessuna eccezione, tutti e 7 i
  titoli/link presenti nel markup renderizzato) e un avvio reale
  (`streamlit run` su porta locale, HTTP 200 su `/`, poi terminato).
  Confermato con l'utente il flusso di deploy per questo tipo di
  modifiche: `dashboard/` legge solo dai Parquet statici (nessuna
  dipendenza dal DB live), Streamlit Community Cloud fa redeploy
  automatico a ogni push su `main` — nessun passaggio manuale
  aggiuntivo, il test locale/`AppTest` resta consigliato ma non
  obbligatorio prima del push.

  Pagine aggiornate: `dashboard.md` (sezione "Home": "3 card" → "7
  card", nuovo bullet cronologico 2026-07-20).

- **2026-07-20** (seguito) — Su richiesta dell'utente: sidebar leggermente
  più stretta, titolo in cima, contatti dell'autrice in fondo, in
  `dashboard/components/styling.py`. Nuove regole CSS su
  `[data-testid="stSidebar"]` (`min-width: 18rem`, valore approssimato per
  difetto — non è stato possibile leggere il default effettivo di
  Streamlit 1.58 dal bundle JS minificato, il resize manuale resta
  possibile) e su `[data-testid="stSidebarUserContent"]` (colonna flex a
  tutta altezza, così `.hw-sidebar-footer` con `margin-top: auto` resta
  ancorato in fondo invece di seguire subito il titolo). Nuova funzione
  `render_sidebar_branding()`: titolo "🌡️ Heatwave Piemonte" + contatti
  (Anna Digiglio, anna.digiglio97@gmail.com, link `mailto:`). **Limite
  noto**: il titolo compare subito sotto la nav automatica delle pagine,
  non sopra — non c'è un'API per anteporlo senza un'immagine per
  `st.logo()`, mai valutata in questa sessione. Richiamata in tutte e 8 le
  pagine (`Home.py` + `pages/02-08`) subito dopo `inject_custom_css()`,
  stesso pattern di chiamata già esistente.

  Verificato con `py_compile` su tutti gli 8 file e `AppTest` (nessuna
  eccezione nuova; 2 eccezioni preesistenti e non correlate confermate via
  `git stash` — `03_analisi_spaziale.py`/`05_contesto_territoriale.py`
  falliscono in isolamento su `st.page_link` verso l'altra pagina,
  limite noto di `AppTest` che testa una pagina alla volta senza il
  registro completo delle pagine dell'app; funzionano nell'app reale).
  Avvio locale reale: tutte e 8 le pagine HTTP 200.

  Pagine aggiornate: nessuna pagina wiki di dominio ancora sincronizzata
  con questo cambiamento oltre a questo log (solo CSS/branding, non
  contenuto/dati) — da rivedere al prossimo giro di lint.

- **2026-07-20** (seguito, correzione) — L'utente ha respinto il primo
  tentativo: il titolo testuale sotto la nav non andava bene ("deve stare
  in alto sopra home, se non riesci a metterlo eliminalo") e ha chiesto il
  testo giusto ("Il riscaldamento del Piemonte", il titolo reale del
  progetto, non più il brand "Heatwave Piemonte"). Riprovato con
  `st.logo()` invece di un div `st.sidebar.markdown`: è l'unica API che
  compare sopra la nav automatica delle pagine (verificato leggendo
  `streamlit/elements/lib/image_utils.py` nel venv: accetta anche una
  stringa SVG grezza, non solo un file), con un'icona `"🌡️"` (emoji
  singola, formato supportato direttamente da `st.logo`) per lo stato
  sidebar chiusa. SVG generato al volo in `_sidebar_title_svg()`, colore
  del testo preso da `THEME_TOKENS` in base a `st.context.theme.type`
  (stesso pattern di `inject_custom_css()`) per restare leggibile sia in
  chiaro sia in scuro.

  Corretta anche l'ancoratura dei contatti in fondo, sospettata non
  funzionante nel primo tentativo: il CSS toccava solo
  `stSidebarUserContent`, ma senza un'altezza esplicita più in alto nella
  catena (`stSidebarContent`) `height: 100%` non aveva nulla da cui
  ereditare. Ora entrambi i livelli sono colonne flex a piena altezza in
  cascata.

  **Causa distinta trovata durante il fix**: l'utente vedeva anche un
  `ImportError` su `render_sidebar_branding` non legato a queste modifiche
  ma a due processi Streamlit locali rimasti vivi da sessioni di test
  precedenti (avviati più volte sulla stessa porta 8502 senza chiuderli
  tutti) — il browser era connesso a un processo vecchio con l'import
  ancora mancante. Terminati entrambi via `taskkill`, server riavviato
  pulito.

  Verificato con `py_compile` e `AppTest` (nessuna eccezione) e un avvio
  locale reale pulito (porta liberata prima del riavvio, HTTP 200, nessun
  errore in log).

  Pagine aggiornate: nessuna pagina wiki di dominio oltre a questo log
  (solo CSS/branding).

- **2026-07-20** (seguito, seconda correzione) — L'utente ha respinto anche
  il tentativo con `st.logo()`: esteticamente non convincente ("deve
  essere simile al titolo della pagina home") e i contatti restavano
  ancora non ancorati in fondo nonostante il fix flex del giro precedente.
  Due cambi distinti:
  - **Titolo**: abbandonato `st.logo()`/SVG. Tornato a un div HTML
    normale in `st.sidebar` con lo stesso trattamento del titolo hero di
    Home (`.hw-hero h1`): font Fraunces reale (non un fallback di sistema
    dentro un SVG, che non carica il `@import` della pagina) e stesso
    gradiente testo (`background-clip: text`) preso da
    `tokens["hero_title_gradient"]`. Compromesso dichiarato: compare
    **sotto** la nav automatica delle pagine, non sopra — non c'è un modo
    verificato per anteporlo con questo stesso trattamento tipografico;
    l'utente aveva esplicitamente autorizzato di rinunciare al
    posizionamento se irraggiungibile bene ("se non riesci a metterlo
    eliminalo").
  - **Contatti in fondo**: il tentativo precedente rendeva
    `stSidebarContent`/`stSidebarUserContent` colonne flex a piena altezza
    con `margin-top: auto` sul footer, basandosi su un'assunzione non
    verificabile sulla struttura interna di Streamlit (nessun modo di
    ispezionarla senza un browser reale). Sostituito con
    `position: fixed; left:0; bottom:0; width:18rem` (stessa larghezza
    della sidebar), che ancora il footer al bordo della finestra invece
    che a un contenitore flex — non dipende più da assunzioni sulla
    gerarchia DOM di Streamlit. Nascosto a sidebar chiusa via
    `[aria-expanded="true"]` (attributo reale confermato nel bundle JS),
    per non restare "appeso" sopra il contenuto principale.

  Verificato con `py_compile`, `AppTest` (nessuna eccezione, markup del
  titolo presente col gradiente corretto) e riavvio locale pulito (porta
  liberata prima, HTTP 200, nessun errore in log). **Non verificato
  visivamente** in un browser reale (nessuno strumento di screenshot
  disponibile in questa sessione) — il posizionamento fisso del footer e
  l'aspetto del titolo restano da confermare dall'utente.

  Pagine aggiornate: nessuna pagina wiki di dominio oltre a questo log
  (solo CSS/branding).

- **2026-07-20** (seguito, conferma finale) — L'utente ha condiviso uno
  screenshot reale della Home: i contatti sono correttamente ancorati in
  fondo alla sidebar (il fix `position: fixed` funziona), ma il titolo
  restava sotto la nav, non sopra come richiesto in origine.

  **Vincolo tecnico scoperto solo ora, confrontando i due tentativi**:
  `st.logo()` renderizza l'SVG passato come immagine sandboxata
  (`<img src="data:image/svg+xml;...">`) - i browser bloccano il
  caricamento di font esterni (l'`@import` di Google Fonts usato per
  Fraunces nel resto della pagina) dentro un'immagine SVG di questo tipo,
  quindi può usare solo font di sistema. Non è un errore di
  implementazione dei tentativi precedenti: è un limite strutturale di
  `st.logo()` che rende impossibile avere **contemporaneamente**
  "sopra la nav" (richiede `st.logo()`) e "stesso font/gradiente della
  Home" (richiede HTML/CSS normale, che invece non può comparire sopra la
  nav). Spiegato esplicitamente all'utente invece di continuare a provare
  varianti alla cieca.

  Presentata la scelta con `AskUserQuestion` (sopra/system-font,
  sotto/stile-Home, o eliminarlo): **l'utente ha scelto di tenere lo stato
  attuale** (sotto la nav, font Fraunces + gradiente identico al titolo
  hero di Home) - nessuna ulteriore modifica al codice.

  Pagine aggiornate: nessuna pagina wiki di dominio oltre a questo log.

- **2026-07-20** (seguito, soluzione definitiva titolo sidebar) — Spiegato
  all'utente il vincolo tecnico di `st.logo()` (SVG renderizzato in
  modalità sandboxata, blocca font esterni) e chiesto se preferisse
  sopra/system-font, sotto/stile-Home, o eliminarlo. L'utente ha invece
  chiesto le specifiche per fornire lei stessa un'immagine col font già
  incorporato, e ha fornito due SVG già pronti (testo convertito in
  tracciati vettoriali, non `<text>` con `font-family`, quindi senza
  bisogno di caricare Fraunces): `logo-dark-theme.svg` e
  `logo-light-theme.svg`, stesso gradiente di `hero_title_gradient` già
  applicato via `<linearGradient>` nativo SVG. Salvati in
  `dashboard/assets/` (cartella nuova).

  `render_sidebar_branding()` ora usa `st.logo()` con il file giusto in
  base a `st.context.theme.type` (stesso pattern del resto del modulo) +
  `icon_image="🌡️"` per lo stato sidebar chiusa (emoji singola, supportata
  direttamente da `st.logo` senza bisogno di un file). Rimossa la classe
  CSS `.hw-sidebar-title` e il div HTML del tentativo precedente, non più
  usati. Nuovo import `PROJECT_ROOT` da `components/__init__.py` per
  costruire i path assoluti ai due SVG.

  Verificato con `py_compile`, `AppTest` su tutte e 8 le pagine (nessuna
  eccezione nuova) e riavvio locale pulito (HTTP 200, nessun errore in
  log). **Aspetto visivo del logo sopra la nav non verificato di persona**
  (nessuno strumento di screenshot disponibile) - da confermare
  dall'utente.

  Pagine aggiornate: nessuna pagina wiki di dominio oltre a questo log.

- **2026-07-20** (seguito, bug regressione) — L'utente ha segnalato un
  problema comparso solo dopo le modifiche sidebar: chiudendo la sidebar,
  la pagina principale non si riespandeva più a riempire lo spazio
  liberato (restava alla larghezza precedente). Causa: la regola
  `[data-testid="stSidebar"] { min-width: 18rem !important; }` non era
  condizionata allo stato aperto/chiuso, quindi impediva alla sidebar di
  restringersi a 0 durante il collasso, interferendo con la logica nativa
  di Streamlit che ridimensiona il contenuto principale in base alla
  larghezza reale della sidebar. Corretto scoprendo la regola con
  `[aria-expanded="true"]` (stesso attributo già usato per i contatti in
  fondo): a sidebar chiusa la regola non si applica più, il collasso
  torna a funzionare nativamente.

  Verificato con `py_compile`, `AppTest` (nessuna eccezione) e riavvio
  locale pulito (HTTP 200, nessun errore in log). Il comportamento di
  collasso/riespansione non è verificabile senza un browser reale
  (richiede interazione, non solo caricamento pagina) — da confermare
  dall'utente.

  Pagine aggiornate: nessuna pagina wiki di dominio oltre a questo log.

- **2026-07-20** — INGEST. Quarta sessione della stessa collaboratrice,
  stesso obiettivo (mappa Bias Open-Meteo↔ARPA, non estensione spaziale
  generica). `git pull` senza novità rilevanti per il download (già
  aggiornato). Trovate in sospeso modifiche locali non committate fatte
  nel frattempo (probabilmente dal titolare in un'altra sessione):
  `dashboard/components/styling.py` e due SVG in `dashboard/assets/`
  (soluzione finale al logo in sidebar, testo convertito in tracciati
  vettoriali per aggirare il sandboxing di `st.logo()`) — non toccate,
  lasciate come lavoro in corso altrui.

  Target ricalcolato da zero: dei 167 comuni ARPA-senza-Open-Meteo,
  sottratti i 9 già scaricati dal titolare (2026-07-19 mattina, Torino) e
  i 57 della propria sessione del giorno prima (ormai importati, 234
  comuni confermati) — **101 comuni residui**, calcolati incrociando la
  tabella wiki con il proprio riepilogo del giorno prima (più affidabile
  dei marcatori ✅ nella tabella, non aggiornati dopo l'import). Stesso
  ordine interlacciato per provincia. Bloccato dalla quota giornaliera
  dopo **57/101 comuni** (su "Monastero di Lanzo") — terza sessione di
  fila fermata esattamente a 57, osservazione empirica non ancora
  spiegata. Zero doppioni verificati. Restano 44 comuni.

  File prodotti (fuori Git, `data/raw/`, da consegnare al titolare fuori
  canale): `temperature_data_extra_helper_arpa_target_day3.csv`,
  `riepilogo_57_comuni_arpa_target_day3.csv`.

  Pagine aggiornate: `etl-pipeline.md` (nuova sezione "Comuni extra
  mirati alla validazione ARPA — terza tranche, 57/101").
  `comuni-coperti.md` non toccata (aggiornamento post-import di
  competenza del titolare).

- **2026-07-20** (sera) — INGEST + DECISIONE DI PROCESSO: l'utente ha
  consegnato i due file della collaboratrice (terza tranche, 57 comuni)
  e ha dato un'indicazione esplicita e importante da rispettare nelle
  prossime sessioni: **niente più import/ricalcolo ad ogni giro di
  download** — la pipeline completa a valle costa ore (~2h20min l'ultima
  volta) e non ha senso ripeterla ogni giorno. **Da ora si accumula soltanto**
  in `data/raw/temperature_data_extra.csv`, e si farà **un solo giro di
  import + ricalcolo** fra qualche giorno, quando si sarà raccolto più
  materiale. Prima di questo chiarimento ho frainteso due volte la
  richiesta (ho iniziato a scaricare un delta non richiesto, poi ho dovuto
  disfare l'azione) — il pattern "chiedere prima di assumere" (vedi
  memoria `feedback_ask_before_data_downloads.md`, fuori da questo repo)
  resta il punto debole da tenere d'occhio.

  Uniti i 57 comuni della collaboratrice in `temperature_data_extra.csv`
  (istat_code → municipality_id, zero sovrapposizioni, 226 → 283 comuni
  nel file) — **non importati in `temperature`**, deliberatamente. File
  della collaboratrice eliminati dopo l'unione.

  Ricalcolato da zero l'elenco dei comuni ARPA-target ancora mancanti
  **ovunque** (né in `temperature`, né in `temperature_data_extra.csv`, né
  nel file pendente `temperature_data_extra_torino_2026-07-19.csv`):
  **44 comuni** (stesso numero già trovato indipendentemente dalla
  collaboratrice nella sessione precedente, buon segno di coerenza).
  Avviato il download diretto (storico completo 2000→oggi, stesso
  approccio di `download_extra_municipalities.py`) per tutti e 44, con lo
  stesso monitor di blocco-quota delle sessioni precedenti — anche questo
  lotto resterà solo accumulato, non importato.

  Pagine aggiornate: `comuni-coperti.md` (nuova nota in cima sulla
  decisione di rimandare import/ricalcolo, stato del terzo lotto,
  inventario del backlog non importato).

  **Esito finale del download dei 44**: bloccato dalla quota dopo
  **22/44** (su "Viola", confermato dal blocco anche sul successivo).
  I 22 riusciti uniti in `temperature_data_extra.csv` (283 → 305 comuni),
  zero sovrapposizioni. File temporaneo eliminato. Restano 22 comuni per
  la prossima sessione. `temperature_data_extra.csv` passato da 226 a 305
  comuni in questa sola giornata, nessuno di questi importato in
  `temperature` (per scelta esplicita dell'utente, vedi sopra).

- **2026-07-20** (sera, seguito) — FIX su richiesta dell'utente: la
  descrizione del tentativo di Torino del 2026-07-19 dava l'impressione
  che "scaricare la provincia di Torino" fosse il prossimo passo corretto
  per i download generici di comuni extra — non lo è mai stato, era un
  fraintendimento isolato. Riscritta la sezione per chiarire che il
  criterio giusto (quando non si insegue una lista target specifica come
  quella ARPA) resta quello basato sulla **posizione geografica**
  (campionamento "farthest-point" proporzionale su tutte le province,
  come dal 2026-07-15), non una singola provincia.

- **2026-07-20** (sera, seguito) — FIX: l'utente ha chiesto se la
  tabella dei 167 comuni ARPA-senza-Open-Meteo (quella che la
  collaboratrice consulta prima di scaricare) fosse aggiornata con i
  comuni presi in carico oggi — non lo era, aveva ancora solo i 9 ✅ del
  2026-07-19 mattina, nonostante 136 comuni in più fossero nel frattempo
  coperti (57 day1 già importati, 57 day3 e 22 del titolare/IA uniti nel
  raw). Ricalcolata e riscritta interamente la colonna ✅ incrociando
  `arpa_temperature`, `temperature`, `temperature_data_extra.csv` e il
  file pendente di Torino: **145/167 ✅**, **22 ancora mancanti**, elencati
  esplicitamente per nome in cima alla tabella da comunicare alla
  collaboratrice. Corretto anche un piccolo errore nella prosa precedente
  (un comune, "Monastero di Lanzo", elencato due volte nell'elenco dei
  mancanti scritto a mano; "Villanova Solaro" mancava).

  Pagine aggiornate: `comuni-coperti.md` (tabella dei 167 comuni
  interamente ricalcolata, non più solo annotata a mano).

- **2026-07-20** (sera, seguito) — FIX più ampio, stesso motivo: l'utente
  ha fatto notare che serve anche sapere quali comuni **generici** (non
  ARPA-target) scaricare, e che la tabella principale "Comuni già
  coperti" (quella per provincia, con conteggi) era ferma a **177 comuni**
  — non rifletteva né i 57+22 di oggi né i 18 di Torino né, in generale,
  nessun comune scaricato da mesi. Ricostruita **interamente da zero**
  incrociando `temperature` (DB), `temperature_data_extra.csv` e
  `temperature_data_extra_torino_2026-07-19.csv`: **331/1180 comuni
  coperti** (era 177), tabella per provincia rigenerata via script (non
  più a mano) per evitare lo stesso tipo di disallineamento in futuro.
  Aggiunta una nota esplicita in cima alla pagina su due liste distinte
  da non confondere: i **849 comuni generici** ancora scaricabili
  liberamente (criterio spaziale) contro i soli **22 comuni ARPA-target**
  (obiettivo specifico della mappa Bias).

  Pagine aggiornate: `comuni-coperti.md` (tabella "Comuni già coperti"
  interamente rigenerata, 177→331; nuova nota di orientamento in cima
  sulla distinzione tra le due liste).

- **2026-07-21** — INGEST. Quinta e ultima sessione della stessa
  collaboratrice sull'obiettivo ARPA. `git pull` senza conflitti. La
  wiki elencava per nome i 22 comuni ARPA-target rimasti (su 167
  originari) — presi direttamente, lotto piccolo, nessun calcolo di
  esclusione necessario stavolta.

  **Risultato: 22/22 riusciti, zero fallimenti, quota non toccata** —
  primo lotto di questa serie completato in una sola sessione senza
  bloccarsi. **Obiettivo raggiunto**: tutti i 167 comuni ARPA-target
  sono ora scaricati (storico completo). Zero doppioni verificati
  (213.378 righe = 22 × 9.699 giorni). Il file resta comunque in coda
  per l'import, insieme agli altri lotti pendenti — il titolare ha
  deciso il 2026-07-20 di accumulare senza ricalcolare a ogni sessione.

  File prodotti (fuori Git, `data/raw/`, da consegnare al titolare fuori
  canale): `temperature_data_extra_helper_arpa_final22.csv`,
  `riepilogo_22_comuni_arpa_final.csv`.

  Pagine aggiornate: `etl-pipeline.md` (nuova sezione "Comuni extra
  mirati alla validazione ARPA — ultimo lotto, obiettivo completato").
  `comuni-coperti.md` non toccata (aggiornamento post-import di
  competenza del titolare, come da convenzione).

- **2026-07-21** (stesso giorno, poco dopo) — INGEST. Con l'obiettivo
  ARPA completato, l'utente ha chiesto di riprendere l'estensione
  **generale** della copertura (non più mirata ad ARPA). Base: i 331
  comuni già coperti, estratti dalla tabella per provincia di
  `comuni-coperti.md` (rigenerata dal titolare il 2026-07-20). Stesso
  algoritmo "farthest-point" delle sessioni originarie.

  **Risultato: 85 comuni scaricati** — il lotto singolo più numeroso di
  tutta la serie (oltre il 50% in più del massimo precedente, 57),
  bloccato dalla quota su "Benna" con un solo fallimento. Tutte e 8 le
  province rappresentate. Zero doppioni verificati (824.415 righe = 85 ×
  9.699 giorni).

  File prodotti (fuori Git, `data/raw/`, da consegnare al titolare fuori
  canale): `temperature_data_extra_helper_general_20260722.csv`,
  `riepilogo_85_comuni_generale.csv`.

  Pagine aggiornate: `etl-pipeline.md` (nuova sezione "Estensione
  generale ripresa dopo l'obiettivo ARPA — 85 comuni").
  `comuni-coperti.md` non toccata.

- **2026-07-22** — RISCRITTO `README.md` (SU RICHIESTA ESPLICITA
  DELL'UTENTE, NON UN INGEST DI MATERIALE NUOVO). L'utente ha segnalato che
  il README pubblico su GitHub "non sembra aggiornato, sembra fatto con
  l'IA", mancava il link al sito ora pubblico
  (https://heatwave-piemonte.streamlit.app/) e non voleva più la roadmap
  "3 settimane" (il progetto ha richiesto più tempo di così). Riscritto
  interamente usando `project-status.md`/`dashboard.md`/`data-model.md`
  come fonte per i numeri reali (234 comuni Open-Meteo, 218 ARPA, 8 pagine
  dashboard, 31 test, 3 mappe QGIS) invece di ripetere le metriche
  aspirazionali di `PROJECT_SUMMARY.md`. Rimossa la sezione Roadmap;
  aggiunta una sezione "Limiti noti" (copertura parziale, bias ARPA, mappa
  Heatwave Index mancante) per onestà scientifica. Creato `LICENSE` (MIT),
  mancante nonostante il badge la dichiarasse già — chiesto conferma
  esplicita all'utente prima di aggiungerlo. Rimossi i placeholder
  (`yourusername`, `Nome Cognome`, email finta) con i dati reali
  dell'autrice (nome, GitHub, LinkedIn, email — forniti dall'utente su
  richiesta). Nessuna modifica a codice/dati: solo documentazione.

  Pagina aggiornata: `project-status.md` (nota sulla riscrittura del
  README nella sezione discrepanze).

- **2026-07-21** — INGEST: `git pull` (portato dalla collaboratrice: 2
  nuove sessioni documentate in `etl-pipeline.md` prima di questo lavoro),
  poi uniti i 2 lotti consegnati fuori Git — **22 comuni ARPA-target**
  (ultimo lotto, **obiettivo dei 167 comuni completato al 100%**) e **85
  comuni generici** (ripresa del criterio spaziale ordinario dopo la fine
  dell'obiettivo ARPA). **Bug reale trovato durante l'unione**: 2 comuni
  (Pragelato, Sestriere) presenti in **entrambi** i lotti della
  collaboratrice — scaricati due volte nella stessa sessione perché il
  controllo "già scaricato" della selezione generale guardava solo il DB,
  non il file ARPA appena prodotto nella stessa sessione. 19.398 righe
  duplicate identificate (confermate identiche), rimosse prima di salvare
  definitivamente. File della collaboratrice eliminati dopo l'unione
  (226 → 410 comuni in `temperature_data_extra.csv`).

  Rilanciato poi il download generale (criterio spaziale, target = tutti
  i 744 comuni ancora mancanti, fino al blocco quota): **19/720 riusciti**
  prima del blocco su "Silvano d'Orba" (quota quasi certamente già
  consumata dai 107 comuni a storico completo scaricati dalla
  collaboratrice nella stessa giornata) — uniti allo stesso file (410 →
  **429 comuni**). **Nessun import né ricalcolo**, per scelta esplicita
  dell'utente (stessa decisione del 2026-07-20): si continua ad
  accumulare.

  Ricalcolata la tabella "Comuni già coperti" per provincia (incrociando
  DB + tutti i file raw pendenti, non solo DB): **455/1180 comuni**
  coperti (era 331 ieri sera).

  Pagine aggiornate: `comuni-coperti.md` (obiettivo ARPA marcato
  completo, tabella comuni-coperti rigenerata 331→455, nuove sezioni
  sull'esito di entrambi i lotti e sul bug dei duplicati).

- **2026-07-22** — `git pull` (nessun commit nuovo, repo già allineato).
  Su richiesta dell'utente ("scarica nuovi comuni del Piemonte fino a
  quando non ci blocca, dammi i CSV da dare al collega"), nuovo lotto di
  estensione generale — stesso obiettivo/algoritmo delle sessioni
  precedenti, ma da **questa macchina, senza alcun accesso al DB**
  (nessun `.env`, verificato già in una sessione precedente). Le funzioni
  che in `download_extra_municipalities.py` leggono da Postgres
  (`load_all_municipalities()`, `already_downloaded_ids()`) sono state
  sostituite con fonti locali: shapefile ISTAT ufficiale già presente in
  `data/external/istat_confini/` (per l'elenco dei 1180 comuni + codice
  ISTAT) unito a `data/dashboard_export/municipality_metadata_all.parquet`
  (per lat/lon, export statico già usato dalla dashboard) e alla tabella
  "Comuni già coperti" di `comuni-coperti.md` (per sapere cosa escludere).

  **Bug reale scoperto e corretto durante il join**: il file `.dbf` dello
  shapefile ha un problema di encoding sui nomi accentati (bytes UTF-8
  letti come Latin-1 — "Agliè" diventava "AgliÃ¨"), che faceva fallire il
  join per nome su 28/1180 comuni. Risolto con
  `nome.encode('latin-1').decode('utf-8')` prima di unire; verificato che
  dopo il fix tutti e 1180 i comuni si abbinano correttamente.

  **Bug proprio, trovato e corretto prima di lanciare il download vero**:
  lo script di selezione (in uno scratchpad temporaneo, non nel repo)
  calcolava la root del progetto risalendo le cartelle a partire dal
  proprio percorso — ma vivendo fuori dal repo, il ciclo risaliva fino
  alla radice del disco senza mai trovare `config.yaml`, restando
  bloccato all'infinito. Diagnosticato isolando ogni passaggio (import,
  lettura shapefile) con timeout brevi finché non si è capito quale
  passo non terminava mai; corretto imponendo il percorso assoluto della
  root invece di derivarlo da `__file__`.

  **Download**: selezionati 150 comuni candidati (stesso metodo
  farthest-point-sampling per provincia, interlacciati round-robin tra
  province). Scaricati **57 comuni** con successo (storico completo
  2000-01-01 → oggi), zero falliti per motivi diversi dalla quota,
  bloccato dopo 57 (backoff crescente su "Capriglio", confermato sul
  successivo "Pollone" prima di fermarsi — stesso identico numero della
  sessione del 2026-07-19, coincidenza). Verificato senza doppioni interni
  né sovrapposizioni con i 455 comuni già coperti; codici ISTAT
  verificati a 6 cifre su tutte le 57 righe del riepilogo.

  File prodotti in `data/raw/` (fuori Git, come da convenzione):
  `temperature_data_extra_helper_general_20260722b.csv` (dati, formato di
  consegna standard) e `riepilogo_generale_20260722b.csv` (sintesi per
  comune) — suffisso "b" per non confondersi con l'omonimo file già
  presente da una sessione precedente (85 comuni, stesso nome usato quel
  giorno per un delta mai eseguito).

  Pagine aggiornate: `comuni-coperti.md` (nuova voce in cima, tabella
  comuni-coperti rigenerata programmaticamente 455→512, tutti gli header
  di provincia aggiornati), `etl-pipeline.md` (nuova sezione "Estensione
  generale, metodo DB-free — 57 comuni").

- **2026-07-22** (seguito) — INGEST: `git pull` (portati i 57 comuni
  della sessione DB-free descritta sopra), poi uniti in
  `temperature_data_extra.csv` (429 → 486 comuni, zero sovrapposizioni,
  file del collega eliminati dopo l'unione). Rilanciato subito il
  download generale (stesso criterio spaziale, target = 668 comuni
  ancora mancanti, fino al blocco quota): **19/650 riusciti** prima del
  blocco su "Felizzano" (confermato dal blocco anche sul successivo) —
  quota quasi certamente già consumata dal lotto del collega nella
  stessa giornata. I 19 uniti allo stesso file (486 → 505 comuni).
  **Nessun import né ricalcolo**, per scelta esplicita dell'utente
  (stessa decisione del 2026-07-20): si continua ad accumulare.

  Ricalcolata la tabella "Comuni già coperti" per provincia: **531/1180
  comuni** coperti (era 512).

  Pagine aggiornate: `comuni-coperti.md` (unione del lotto del collega,
  esito del nuovo giro di download, tabella comuni-coperti rigenerata
  512→531).

- **2026-07-23** — INGEST + CAUSA ROOT TROVATA: la collaboratrice ha
  consegnato altri 57 comuni generici. All'unione, **8 comuni erano già
  presenti** (77.600 righe duplicate, deduplicate prima di salvare) —
  **causa**: l'aggiornamento di questa pagina del 2026-07-22 sera (i 19
  comuni di quel giro, 4 dei quali coincidono con gli 8 doppioni di oggi)
  era rimasto **non committato/pushato** — la collaboratrice ha lavorato
  su uno snapshot Git di un giorno indietro. Il meccanismo di
  coordinamento "aggiorna la wiki, la collega la consulta via git pull"
  **richiede che i commit vengano effettivamente pushati**, non solo
  scritti su disco — altrimenti si ripete lo stesso spreco di quota già
  visto il 2026-07-21 (Pragelato/Sestriere, causa diversa ma stesso
  sintomo). File della collaboratrice uniti (505 → 554 comuni) ed
  eliminati.

  Rilanciato il download generale sui comuni mancanti (580 coperti, 600
  mancanti all'avvio): **19/574 riusciti** prima del blocco su "Avolasca"
  (confermato dal blocco anche sul successivo) — presi anche i due
  comuni bloccati ieri (Felizzano, Mombello Monferrato). Uniti allo
  stesso file (554 → 573 comuni). **Nessun import né ricalcolo**, per
  scelta esplicita dell'utente (stessa decisione del 2026-07-20).

  Ricalcolata la tabella "Comuni già coperti": **599/1180 comuni**
  coperti (era 531).

  Pagine aggiornate: `comuni-coperti.md` (causa root dei doppioni
  documentata esplicitamente, unione del lotto del collega, esito del
  nuovo giro di download, tabella comuni-coperti rigenerata 531→599).

- **2026-07-23** — `git pull` (nessun commit nuovo: la sessione precedente
  era già stata committata dall'utente, `871a63e`). Stessa richiesta
  identica dell'utente ("come gli altri giorni"), quarto giorno
  consecutivo di questo tipo di sessione. Script DB-free della sessione
  precedente non più disponibile (la cartella temporanea di sessione è
  cambiata tra una conversazione e l'altra) — ricreato da zero nella
  nuova scratchpad, stessa logica, solo il suffisso data aggiornato
  (`20260723`).

  Selezionati 150 candidati (farthest-point-sampling per provincia,
  round-robin), esclusi i 512 comuni già coperti (letti dalla tabella di
  `comuni-coperti.md`, non da un DB — stesso vincolo di sempre, ancora
  nessun `.env` in questa macchina). **Scaricati 57 comuni**, zero
  falliti per motivi diversi dalla quota, bloccato dopo 57 (backoff
  crescente su "Grana Monferrato", confermato su "Sostegno" — terzo
  giorno di fila fermo esattamente a 57, coincidenza: la serie storica è
  un giorno più lunga di ieri, quindi non è un conteggio identico di
  richieste). Verificato senza doppioni interni né sovrapposizioni con i
  512 già coperti.

  **Osservazione**: `data/raw/` era vuota all'inizio della sessione — i
  file consegnati ieri (22/7) non c'erano più, segno che il collega li
  aveva già presi in consegna, coerente con la convenzione "file
  eliminati dopo l'unione".

  File prodotti in `data/raw/` (fuori Git): `temperature_data_extra_helper_general_20260723.csv`
  (dati) e `riepilogo_generale_20260723.csv` (sintesi).

  Pagine aggiornate: `comuni-coperti.md` (nuova voce in cima, tabella
  comuni-coperti rigenerata 512→569, tutti gli header di provincia
  aggiornati), `etl-pipeline.md` (nuova sezione "Estensione generale,
  metodo DB-free — altri 57 comuni").

- **2026-07-23** (pomeriggio-sera) — GIRO UNICO DI IMPORT + RICALCOLO
  (234 → 599 comuni), su richiesta esplicita dell'utente ("avvia
  l'operazione di import e ricalcolo su tutto il progetto"). Consolidati
  tutti i lotti pendenti accumulati dal 2026-07-20: 347 comuni nuovi da
  `temperature_data_extra.csv`, 18 da Torino, 267 righe di delta per i
  177 comuni originali — **3.540.507 righe pulite e inserite** in
  `temperature` (234 → **599 comuni**, 5.809.330 righe totali). Ricalcolo
  a valle completo: elevazione 599/599, `TRUNCATE`+`identify_heatwaves()`
  → **2.192 ondate** (da 770), `kpi_annual_by_municipality` → **16.173
  righe**. Mappe QGIS rigenerate.

  `download_arpa.py` e `refresh_dashboard.py` (pipeline di analisi
  completa) lanciati **in parallelo** per risparmiare tempo — la STL da
  sola (~4h10min per 599 comuni) copriva ampiamente il tempo di download
  ARPA (~2h per 217 stazioni), quindi l'import di `arpa_temperature` è
  avvenuto ben prima che `validate_arpa` (ultimo step prima dell'export)
  ne avesse bisogno. **Copertura ARPA ora completa: 218/218 comuni**
  hanno sia Open-Meteo che ARPA (era 108/234) — bias -1.52°C (stabile su
  tutti e 3 gli allargamenti del campione), recall delle ondate risalito
  al 25.2% (da 16.4% a 108 comuni), ma la differenza di pendenza del
  trend ha **invertito segno** (-0.096→+0.148°C/decade) — segnalato
  esplicitamente come risultato instabile, non ancora da riportare come
  cifra precisa nel paper.

  **Bug di merge trovato e corretto durante il consolidamento dei file**:
  un mio errore nel merge dei capoluoghi ha temporaneamente sovrascritto
  la colonna `province` con valori vuoti per 16 righe, causando la
  perdita silenziosa di 14 righe per una deduplica su chiave sbagliata —
  scoperto verificando il totale contro il DB (non tornava), corretto
  ricalcolando la colonna da `municipality_id`.

  **Scoperta separata e più seria**: `wiki/pages/comuni-coperti.md` e
  `wiki/log.md` contenevano **6+1 marcatori di conflitto Git non
  risolti** (`<<<<<<< HEAD` / `=======` / `>>>>>>>`), già presenti
  nell'ultimo commit pushato (non un conflitto attivo nella sessione
  corrente — `git status` non segnalava nulla, erano testo letterale
  commesso per errore da una sessione precedente che ha "risolto" un
  conflitto salvando entrambe le versioni con i marcatori invece di
  scegliere/unire il contenuto). Probabile causa: due sessioni diverse
  (questa e quella "DB-free, quarto giorno consecutivo") hanno scritto
  narrazioni indipendenti per lo stesso giorno (2026-07-23) in cima alla
  pagina, generando un conflitto al momento dell'unione mai risolto
  correttamente. Risolto tenendo **entrambe** le narrazioni in sequenza
  (nessuna informazione persa) per il testo libero, e sostituendo per
  intero la tabella "Comuni già coperti" (dove i conflitti erano
  interni alle righe della tabella) con una versione rigenerata da zero
  dal DB. Verificato che non ci fossero altri marcatori altrove nel
  repo (solo falsi positivi in `.venv`, librerie di terze parti).

  Consolidamento file: `temperature_data_extra.csv` assorbe anche il
  lotto Torino (591 comuni), `temperature_data_recent.csv` e gli archivi
  ridondanti eliminati; stesso consolidamento su `data/processed/`
  (77.576 + 5.731.754 = 5.809.330, combacia esattamente col DB).

  Pagine aggiornate: `comuni-coperti.md`, `project-status.md`,
  `statistical-analysis.md` (numeri di validazione ARPA ricalcolati sul
  campione completo a 218 comuni in tutte le sottosezioni, tabella di
  confronto storico aggiunta), `log.md` (questa voce, correzione dei
  conflitti Git non risolti).

- **2026-07-24** — SINCRONIZZAZIONE WIKI/FRONTEND SUI RISULTATI A 599
  COMUNI. Richiesta esplicita dell'utente: dopo il giro di import
  234 → 599 comuni della sessione precedente (2026-07-23), verificare che
  "tutte le scritte del frontend e della wiki" fossero coerenti e capire
  se i risultati statistici fossero cambiati in modo significativo con
  l'estensione del campione.

  **Audit** (nessuna modifica, solo lettura): confrontati i numeri
  hardcoded in `wiki/pages/*.md` e in `dashboard/**/*.py` con lo stato
  reale del DB (`data/dashboard_export/overview_stats.json`, già a 599/218
  grazie all'export rigenerato il 23/7) e con i file freschi in `output/`
  (tutti datati 23/7 16:13-16:14, prodotti da `refresh_dashboard.py` sullo
  stesso giro di import). Trovato che i numeri **letti dinamicamente** a
  runtime (Home page, card, mappe) erano già corretti, ma **il testo
  statico no**: `dashboard/pages/08_citazioni_e_fonti.py` e
  `dashboard/pages/05_contesto_territoriale.py` (risultati del modello a
  errore spaziale) citavano ancora "234 comuni"; commenti/docstring in
  `Home.py`, `queries.py`, `data_source.py` erano stale (quest'ultimo
  affermava pure "110 comuni hanno solo ARPA", falso da quando la
  copertura ARPA è completa: sono 0); `README.md` (due punti) e
  `wiki/pages/gis-maps.md` (fermo a "177 comuni" nonostante le mappe QGIS
  fossero già state rigenerate il 23/7) erano anch'essi stale.

  **Scoperta più rilevante**: `refresh_dashboard.py` aveva già
  ri-eseguito tutti e 5 i moduli di `src/analysis/` sul campione a 599
  comuni durante la sessione del 23/7 (in parallelo al download ARPA), ma
  **nessuna pagina wiki raccontava questi risultati** — la narrazione di
  `statistical-analysis.md` si fermava a n=177 (il passaggio intermedio a
  n=234 non aveva mai avuto una sezione dedicata). Letti i file `output/`
  freschi (`trend_analysis.csv`, `heatwave_stats_by_municipality.csv`,
  `seasonal_trend_summary.csv`, `spatial_analysis.csv`,
  `morans_i_summary.csv`, `spatial_regression_summary.txt`,
  `spatial_regression_spatial_model.txt`) per ricostruire i risultati reali
  a 599 comuni, mai scritti da nessuna parte:
  - Moran's I sale a **0.2115** (p=0.001), da 0.1695 a n=177.
  - Cluster K-means: 152 alpino (6.2°C) / 249 intermedio (11.9°C) / 198
    pianura calda (13.2°C).
  - Trend: 556/599 comuni significativi (92.8%). **La claim ripetuta per
    tre estensioni consecutive ("Briga Alta resta l'unico raffreddamento
    significativo") non è più vera**: a 599 comuni compare un secondo caso,
    **Argentera** (-0.40°C/decade, p=0.041), confermato anche da STL (589/599
    comuni in aumento, 10 non in aumento).
  - Ondate di calore: 2.192 totali, nuovo comune con più ondate **Molino
    dei Torti/Castellazzo Bormida (17 pari merito)**, non più
    Bassignana/Bozzole/Tortona (16 a n=177).
  - Regressione spaziale: **% urbano torna non significativo** (p=0.370,
    era p=0.031 a n=234, il terzo ribaltamento di significatività su 5
    estensioni) mentre **NDVI diventa significativo con segno negativo**
    (p=0.012) — per la prima volta il segno fisicamente atteso (più
    vegetazione → più fresco), invece del solito segno controintuitivo
    delle versioni precedenti. Lambda spaziale sale a 0.932 (da 0.854).
    **L'unico predittore stabile in tutte e 5 le versioni (n=63/98/177/234/599)
    resta l'elevazione.**

  **Fix applicati**: testo statico corretto nei 3 file dashboard sopra
  citati (numeri aggiornati a 599/218, risultato del modello spaziale
  riscritto con i numeri reali a n=599 invece di n=234), commenti/docstring
  aggiornati, `README.md` corretto (due punti), nuova sezione
  "Aggiornamento 2026-07-24 — da 177 a 599 comuni (via 234)" aggiunta in
  `statistical-analysis.md` (sintesi di tutti e 5 i moduli) più una
  sottosezione dedicata dentro `spatial_regression.py` con la tabella di
  confronto estesa a n=234/599, `gis-maps.md` aggiornata (177 → 599
  comuni ovunque), `index.md` aggiornato (voci "Comuni già coperti" e
  "Analisi statistica" con i numeri correnti).

  Pagine aggiornate: `statistical-analysis.md`, `gis-maps.md`, `index.md`,
  `project-status.md` (nuovo paragrafo di sintesi), `log.md` (questa voce).
  File fuori wiki corretti: `dashboard/pages/08_citazioni_e_fonti.py`,
  `dashboard/pages/05_contesto_territoriale.py`, `dashboard/Home.py`,
  `dashboard/components/queries.py`, `dashboard/components/data_source.py`,
  `README.md`.

- **2026-07-24 (seguito)** — SECONDO GIRO: "108 comuni" HARDCODED SFUGGITI
  AL PRIMO AUDIT. L'utente ha segnalato un'altra occorrenza rimasta
  ("Analisi Spaziale", caption sulla mappa Bias Open-Meteo vs ARPA: "108
  comuni... 110 solo-ARPA") e chiesto un secondo giro completo sul resto
  del frontend, non fidandosi che il primo audit fosse esaustivo (a ragione:
  il primo giro aveva cercato solo "234"/"177 comuni", non l'overlap
  Open-Meteo∩ARPA scritto altrove come "108"/"110", numero originario del
  2026-07-18 mai più aggiornato). Grep sistematico su tutto `dashboard/`
  per ogni numero di comuni storico (51/63/98/108/145/155/177/190/
  234/331/640/770): trovate **6 occorrenze hardcoded di "108" e 1 di "110
  solo-ARPA"** in `Home.py:156`, `03_analisi_spaziale.py` (righe 262, 293,
  531) e `04_ondate_di_calore.py` (righe 132, 266) — tutte descrivevano
  l'overlap Open-Meteo∩ARPA come fisso a 108/110, falso da quando la
  copertura ARPA è completa (218/218 hanno anche Open-Meteo, overlap
  reale = 218).

  **Fix strutturale, non solo un altro find-replace**: invece di
  sostituire "108" con "218" a mano (lo stesso problema si sarebbe
  ripresentato alla prossima estensione), aggiunte due funzioni cacheate
  in `queries.py` — `get_n_municipalities_both_sources()` e
  `get_n_municipalities_arpa_only()` — che calcolano l'overlap
  dall'intersezione/differenza reale dei due elenchi di nomi comune
  (`get_municipality_names_with_data()` ∩/− `get_arpa_municipality_names_with_data()`),
  invece di un numero scritto a mano. Tutte e 6 le occorrenze sostituite
  con chiamate a queste funzioni: da qui in avanti restano corrette anche
  alla prossima estensione della copertura, senza bisogno di un altro
  giro di audit manuale.

  Verificato con `py_compile` + `AppTest` su `Home.py`,
  `03_analisi_spaziale.py`, `04_ondate_di_calore.py` (nessuna eccezione
  nuova; l'unica eccezione residua su `03_analisi_spaziale.py` testata in
  isolamento è il solito limite noto di `AppTest.from_file()` su una
  sottopagina fuori dal contesto multipage — `st.page_link` →
  `KeyError: 'url_pathname'`, preesistente e riprodotto identico anche
  sulla versione originale via `git stash`, non introdotto da questa
  sessione).

  Pagine toccate: `dashboard/components/queries.py` (2 nuove funzioni),
  `dashboard/Home.py`, `dashboard/pages/03_analisi_spaziale.py`,
  `dashboard/pages/04_ondate_di_calore.py`. Nessuna pagina wiki richiedeva
  modifiche per questo giro (l'overlap "108" non era mai stato scritto in
  `wiki/pages/*.md`, solo nel testo statico della dashboard).

- **2026-07-24** — `git pull` (nessun commit nuovo). Stessa richiesta
  identica dell'utente ("come gli altri giorni"), quinta sessione
  consecutiva di questo tipo. Notata una discrepanza rispetto a dove
  l'avevo lasciata il 2026-07-23: la tabella "Comuni già coperti" era
  passata da 569 a **599** — non per un mio lotto (57, non 30), ma per un
  giro di import + ricalcolo completo eseguito dal titolare nel
  frattempo (234 → 599 comuni in `temperature`, copertura ARPA completata
  a 218/218, vedi la voce dedicata in cima a `comuni-coperti.md`). Preso
  atto e proseguito usando la tabella aggiornata come fonte di verità
  (è esattamente lo scopo di quella pagina), senza cercare di ricostruire
  tutta la cronologia intermedia che non ho visto.

  Script DB-free ricreato da zero nella nuova cartella temporanea di
  sessione (cambia a ogni conversazione, non salvato nel repo per scelta
  esplicita — vedi `etl-pipeline.md`). Selezionati 150 candidati
  (farthest-point-sampling per provincia, round-robin), esclusi i 599
  comuni già coperti. **Scaricati 93 comuni** — il lotto più numeroso di
  tutta la serie DB-free, quasi il doppio del solito 57. Un blocco
  transitorio su "Altavilla Monferrato" si è risolto da solo dopo un
  comune (il successivo è andato a buon fine con un backoff breve), poi
  blocco persistente confermato su "Caramagna Piemonte" e "Villar
  Perosa". Zero falliti per motivi diversi dalla quota. Verificato senza
  doppioni interni né sovrapposizioni con i 599 già coperti.

  File prodotti in `data/raw/` (fuori Git): `temperature_data_extra_helper_general_20260724.csv`
  (902.286 righe, 93 comuni) e `riepilogo_generale_20260724.csv`
  (sintesi).

  Pagine aggiornate: `comuni-coperti.md` (nuova voce in cima, tabella
  comuni-coperti rigenerata 599→692, tutti gli header di provincia
  aggiornati), `etl-pipeline.md` (nuova sezione "Estensione generale,
  metodo DB-free — 93 comuni, record").

- **2026-07-24** (seguito) — INGEST: `git pull` (portati i 93 comuni
  della sessione DB-free descritta sopra), poi uniti. **Scoperto che
  `temperature_data_extra.csv` (370MB) era interamente ridondante** —
  tutti i suoi 591 comuni erano già stati importati nel giro unico del
  2026-07-23, verificato prima di eliminarlo — ricreato da zero come
  accumulatore pulito con solo i 93 comuni nuovi (evita di continuare a
  gonfiare un file ormai inutile). File della collaboratrice eliminati
  dopo l'unione.

  Rilanciato il download generale sui comuni ancora mancanti (692
  coperti, 488 mancanti all'avvio): **19/438 riusciti** prima del blocco
  su "Belforte Monferrato" (confermato dal blocco anche sul successivo
  "Fresonara"). Uniti allo stesso file (93 → 112 comuni). **Nessun
  import né ricalcolo**, per scelta esplicita dell'utente (stessa
  decisione del 2026-07-20, ancora valida).

  Ricalcolata la tabella "Comuni già coperti": **711/1180 comuni**
  coperti (era 692).

  Pagine aggiornate: `comuni-coperti.md` (unione del lotto del collega,
  reset dell'accumulatore ridondante, esito del nuovo giro di download,
  tabella comuni-coperti rigenerata 692→711).

- **2026-07-28** — QUERY: verifica stato servizio Postgres. Su richiesta
  dell'utente ("cosa manca al progetto?" → servizio Postgres), controllato lo
  stato reale invece di fidarsi del claim in "Prossimi passi" di
  `project-status.md`. Trovato: `postgresql-x64-16` è `Running`/`Automatic`,
  `pg_ctl.exe` avviato da `services.exe` con orario coincidente col boot del
  PC — è già un vero servizio Windows auto-avviabile, claim obsoleto.
  Connessione DB confermata (psql, PostgreSQL 16.14). Pagine aggiornate:
  `project-status.md` (punto 3 di "Prossimi passi" segnato fatto/obsoleto,
  nuova sezione in cronologia).
# 2026-09-04 — riallineamento wiki alla consegna finale ITS

Letto il documento di consegna e recepiti i chiarimenti successivi:
PostgreSQL/PostGIS è autorizzato, l'applicazione può funzionare interamente in
locale e non va ridotta la capacità analitica. Aggiunto
`pages/final-project-plan.md` con piano operativo, matrice di conformità,
Pipeline K-Means, persistenza `joblib`, chatbot, benchmark dei prompt, test,
etica e demo. Riscritti `index.md`, `pages/project-overview.md`,
`pages/architecture.md` e `pages/project-status.md` per rimuovere roadmap e
claim obsoleti; esteso `pages/testing.md`. Moran's I, ARPA, QGIS, PostGIS e le
analisi scientifiche sono stati mantenuti.

## Audit tecnico preliminare

Verificati ambiente, dipendenze, PostgreSQL/PostGIS e suite di test. Il test
`test_frequency_by_year_includes_years_with_zero_events` era rimasto legato al
vecchio intervallo fisso 2000–2025, mentre la funzione usa correttamente il
range dinamico introdotto dopo l'estensione dei dati al 2026. Aggiornato il
fixture con le colonne realmente richieste e un anno intermedio privo di eventi;
nessuna modifica al calcolo applicativo.

## Pipeline Machine Learning completata

Creato `src/machine_learning/` con Pipeline `StandardScaler` + `KMeans`,
confronto di `k=2..8`, silhouette score, ordinamento stabile dei cluster,
salvataggio/caricamento `joblib` e metadati JSON. Addestramento reale su 599
comuni: scelto `k=3`, silhouette score 0,5389. Le nuove assegnazioni coincidono
al 100% con il clustering storico. Aggiunti 5 test (suite: 36/36) e la pagina
Streamlit `09_machine_learning.py`, verificata con AppTest insieme alla Home.

# 2026-10-23 — wiki ridotta alla versione d'esame e pipeline per agenti

Confrontato il progetto con i requisiti del corso (6 competenze: pandas,
visualizzazione, ML supervisionato, LLM, agente con tool, RAG). Esito: 2
competenze piene, ML solo non supervisionato, LLM/agente/RAG assenti.

- **Nuove pagine**: `roadmap-esame.md` (fasi F0–F11 con dipendenze e
  cancelli di qualità), `todo-agenti.md` (task T0.1–T11.1 eseguibili da
  agenti), `chatbot.md` (specifica di client LLM, 6 tool sul Parquet, RAG
  ChromaDB, agente Router/Analista/Ricercatore/Revisore, memoria, prompt,
  benchmark), `etica-e-limiti.md`.
- **Riscritte e condensate** sullo stato attuale (senza cronologia):
  `index.md`, `project-overview.md`, `project-status.md`, `architecture.md`,
  `machine-learning.md`, `data-sources.md`, `etl-pipeline.md`,
  `data-model.md` (ha assorbito il catalogo KPI e le query SQL),
  `statistical-analysis.md`, `dashboard.md` (ha assorbito le mappe QGIS),
  `testing.md`, `concepts.md` (aggiunti i termini ML/LLM/RAG; i numeri fermi
  a 8 comuni sono stati corretti), `config-reference.md`.
- **Eliminate**: `final-project-plan.md` (sostituita da roadmap + to-do),
  `comuni-coperti.md` (guida ai download collaborativi, non serve
  all'esame), `gis-maps.md`, `kpi-catalog.md`, `sql-queries.md` (assorbite).
- **Spostata**: `paper-scientifico.md` → `paper/PIANO-ARTICOLO.md`; aggiornati
  i riferimenti nei commenti di `src/`, `qgis_projects/` e `paper/`.
- **Decisione**: dashboard e chatbot leggono solo lo snapshot Parquet;
  PostgreSQL resta per ETL, analisi e training.
- **Problemi rilevati** (diventati task): pagina 09 legge da PostgreSQL
  (T1.1), K-Means duplicato (T1.2), `.env.example` mancante (T0.2), lavoro
  ML non ancora in un commit (T0.1).

Le pagine eliminate già versionate restano nella cronologia git.
`final-project-plan.md` non era mai stata versionata: il suo contenuto è
confluito in `roadmap-esame.md` e `todo-agenti.md`.

# 2026-10-23 — F0 e F1 completate (T0.2, T1.1, T1.2, T1.3)

- **T0.2**: creato `.env.example` (variabili DB, CDS, OSM, log, Streamlit,
  `OLLAMA_HOST`, `ANTHROPIC_API_KEY`), non escluso da git.
- **T1.1** (subagente): `queries.get_ml_features()` legge
  `spatial_analysis.parquet`; la pagina 09 non usa più PostgreSQL. AppTest
  senza eccezioni con DB irraggiungibile; cluster coincidenti al 100%.
- **T1.2** (subagente, in parallelo): `spatial_analysis.climate_clustering()`
  delega a `build_pipeline` + `label_mapping` (reso pubblico); nuovo test di
  equivalenza; 100% di coincidenza su 599 comuni.
- **T1.3**: sezioni `ml` e `chatbot` in `config.yaml`, `ollama` e `anthropic`
  in `requirements.txt`, `data/vector_store/` in `.gitignore`. ChromaDB e
  sentence-transformers si installano ma Smart App Control (attivo,
  `VerifiedAndReputablePolicyState=1`) blocca le DLL di `orjson`, `torch` e
  `regex`. Su decisione dell'utente il RAG userà embedding `bge-m3` via
  Ollama e un indice numpy con `cosine_similarity`; pacchetti bloccati
  disinstallati, `chatbot.md`, `architecture.md`, `roadmap-esame.md`,
  `todo-agenti.md`, `concepts.md`, `project-overview.md` riallineate.

# 2026-10-23 — ondate 3-4: ML supervisionato, client LLM, RAG, tool, etica, test set

Lavoro eseguito da subagenti in parallelo; wiki e stati aggiornati dal
coordinatore. Ollama 0.40.9 installato dall'utente; scaricati `qwen2.5:7b`
e `bge-m3` (CPU: 6–12 s per risposta a modello caldo, 44 s la prima).

- **Pipeline automatica**: `scripts/aggiorna_pipeline.py` rigenera il blocco
  `PIPELINE:START/END` in `roadmap-esame.md` dagli stati di `todo-agenti.md`
  (fasi, avanzamento, task pronti). Hook PostToolUse (Edit|Write|MultiEdit)
  in `.claude/settings.local.json` (cartella `phython` e progetto).
- **T2.1**: `temperature_regression.py` + `train_temperature_model.py`;
  RandomForest scelto (GroupKFold RMSE 0,594, R² 0,889); elevazione dominante;
  MLP instabile. 9 test.
- **T2.2**: pagina 09 a schede (Clustering + PCA, Regressione, Limiti).
- **T3.1**: `llm_client.py` (Ollama, Anthropic opzionale, `FakeLLM`,
  `stato_llm`); 23 test.
- **T4.1 / T4.2**: `rag.py`, `build_knowledge_base.py`, 4 schede in
  `data/knowledge_base/`; cancello 6/6. Escluso dal corpus
  `paper/manoscritto.md` (numeri superati); corretti due test che contavano
  i suoi chunk; indice ricostruito.
- **T5.1**: 6 tool in `tools.py` con whitelist ed errori come osservazioni;
  tolta un'etichetta di cluster non presente nella wiki.
- **T8.1**: `tests/chatbot/test_set.csv` (28 domande, valori dai tool reali)
  + validazione.
- **T9.1**: pagina 11 "Etica e limiti" collegata dalla Home.
