# Articolo scientifico — piano e stato

**Sorgenti**: decisione dell'utente in conversazione (2026-07-16), non
derivata da codice. Letteratura raccolta via ricerca web nella stessa
sessione. Riferimenti incrociati: [Stato del progetto](project-status.md),
[Analisi statistica e spaziale](statistical-analysis.md),
[Fonti dati](data-sources.md).

Questa pagina traccia l'obiettivo di trasformare il progetto in un articolo
scientifico, target una rivista o conferenza peer-reviewed (non solo
portfolio). È una pagina di **pianificazione**, diversa dalle altre pagine
della wiki che descrivono codice esistente — va aggiornata mano a mano che
il piano diventa lavoro reale (a quel punto il dettaglio tecnico andrà anche
nelle pagine di dominio, es. `data-model.md`/`data-sources.md` quando
arriveranno nuove tabelle/fonti).

## Decisione (2026-07-16)

L'idea originale dell'utente: correlare le zone più calde/meno calde del
Piemonte alle cause (grandi città, industria, riscaldamento domestico).
Data la scelta tra un taglio solo descrittivo e uno anche esplicativo, e tra
portfolio/preprint/rivista vera, l'utente ha scelto:

- **Ambizione**: articolo completo, descrittivo **+** esplicativo (non solo
  uno dei due).
- **Target**: rivista o conferenza peer-reviewed vera, non solo un documento
  da portfolio.

## Perché non è solo "scrivere quello che abbiamo"

Il DB oggi ha temperatura giornaliera 2000-2025, elevazione (solo per i
comuni con temperatura), geometrie amministrative per tutti i 1180 comuni,
Moran's I e clustering K-means già calcolati e statisticamente significativi
(vedi [Analisi statistica](statistical-analysis.md)). **Non ha ancora** uso
del suolo, popolazione (`municipalities.population` è `NULL` su tutti i 1180
comuni) o dati industriali — cioè esattamente le variabili esplicative
richieste dall'idea originale. Il confronto "isola di calore urbana" già
presente in dashboard (`03_analisi_spaziale.py`) è dichiarato esplicitamente
"solo illustrativo" (Torino vs media provincia), non un vero studio UHI.

## Le 5 fasi del piano

1. **Validazione contro dati stazione reali (ARPA Piemonte)** — **fatta il
   2026-07-18**, priorità alta risolta. Le temperature Open-Meteo sono
   derivate da reanalisi/modello, non osservazioni dirette; un revisore lo
   contesterebbe per primo. `ArpaPiemonteDownloader` in
   `src/data_acquisition/download_data.py` non ha mai funzionato (URL
   404, verificato il 2026-07-16) — trovata via ricerca web una vera API
   REST pubblica e senza chiave (`utility.arpa.piemonte.it/meteoidro/`),
   implementata in `src/data_acquisition/download_arpa.py` e scaricata per
   davvero: **51 comuni** (dei 177 con temperatura Open-Meteo) hanno una
   stazione ARPA reale corrispondente, 451.502 righe caricate in una nuova
   tabella `arpa_temperature`. Vedi
   [Fonti dati](data-sources.md#arpa-piemonte--integrata-e-scaricata-2026-07-18)
   per il dettaglio tecnico completo (endpoint, gotcha dell'API) e
   [Analisi statistica](statistical-analysis.md#validazione-contro-arpa-piemonte-2026-07-18)
   per i risultati.

   **Risultato, sostanziale per il paper**: correlazione molto alta (r
   medio 0.966 su temp_max) ma un **bias sistematico negativo** — Open-Meteo
   sottostima le massime reali di **-1.71°C in media**, e il bias è **tanto
   più negativo quanto più alto il comune** (r=-0.348, p=0.012 tra bias ed
   elevazione). Interpretazione plausibile: un prodotto di rianalisi
   rappresenta una cella di griglia, non un punto — in rilievo alpino
   complesso questo media quote/esposizioni diverse, smussando le
   temperature estreme reali osservate in quota da una stazione puntuale.
   Questo è un risultato citabile direttamente nel paper (sezione
   metodologia/limiti): non solo dichiara la limitazione nota delle
   rianalisi, la **quantifica** con un controllo empirico reale, ed è
   coerente con l'autocorrelazione spaziale residua già vista nel modello
   a errore spaziale (fase 4 sotto) — un'ipotesi già scritta in questa
   pagina prima ancora di avere il dato per verificarla.

   **Approfondimento 2026-07-18 (stesso giorno, su richiesta esplicita
   dell'utente): bias sui giorni caldi + confronto a livello di evento**.
   Il bias medio sopra è calcolato su tutti i giorni — ristretto ai giorni
   davvero caldi (ARPA temp_max > 35°C), il bias resta simile (-2.21°C) ma
   la **correlazione crolla da 0.956 a 0.400**: Open-Meteo perde quasi del
   tutto la capacità di distinguere quali giorni estremi lo sono di più,
   proprio nella fascia che conta per le ondate di calore. Più diretto
   ancora: riapplicando la stessa logica di `identify_heatwaves()` ai dati
   ARPA (verità di terra) per i 51 comuni e confrontando con
   `heatwave_events` (Open-Meteo) per sovrapposizione temporale, **ARPA
   mostra 322 ondate reali contro le 150 rilevate da Open-Meteo — un
   recall del 31.4%**: Open-Meteo cattura meno di un terzo delle ondate di
   calore effettivamente accadute in questi comuni. Anche le 150 rilevate
   non sono tutte "vere" (precision 62%). **Questo è il risultato più
   importante di tutta la validazione**: non solo le temperature Open-Meteo
   sono distorte, ma le **640 ondate totali già contate nel progetto su 177
   comuni sono quasi certamente un sottoconteggio sostanziale** del
   fenomeno reale — non un numero "prudente", un numero probabilmente
   troppo basso. Va scritto nel paper come limite quantificato (non
   qualitativo) del disegno di studio, non minimizzato. Vedi
   [Analisi statistica](statistical-analysis.md#bias-sui-giorni-davvero-caldi-2026-07-18)
   per il dettaglio completo.

   **Contro-bilanciamento importante, stesso giorno**: il **trend di
   riscaldamento regge** alla fonte dati — Mann-Kendall/regressione
   rieseguiti sulla media annuale ARPA per i 51 comuni concordano in
   segno con Open-Meteo nell'88.2% dei casi, e i 6 casi discordi sono
   tutti situazioni in cui almeno una delle due fonti non è
   statisticamente significativa (nessun trend opposto significativo su
   entrambe le fonti). Differenza media di pendenza piccola (-0.095
   °C/decade) rispetto alla dispersione dei trend nel campione. Da
   scrivere nel paper insieme al limite sopra, non al suo posto: il
   risultato "il Piemonte si sta scaldando in modo diffuso e
   significativo" è robusto; "abbiamo contato N ondate di calore" non lo
   è altrettanto. Vedi
   [Analisi statistica](statistical-analysis.md#il-trend-di-riscaldamento-regge-sui-dati-di-stazione-reali-2026-07-18).
2. **Estendere il campione di comuni con temperatura** oltre gli attuali
   44/1180, per dare potenza statistica a una regressione multivariata **—
   in corso**: l'utente sta estendendo la copertura a 300 comuni tramite
   `src/data_acquisition/download_extra_municipalities.py` (vedi
   [Fonti dati](data-sources.md) per il dettaglio della corsa a 44; questa
   nuova corsa a 300 va documentata separatamente quando completa e caricata
   nel DB).
3. **Acquisire le covariate esplicative mancanti**:
   - Uso del suolo (Copernicus CORINE Land Cover) — overlay via PostGIS
     sulle geometrie comunali già presenti per tutti i 1180 comuni, per
     ottenere % superficie urbana/artificiale, agricola, forestale per
     comune. Non richiede nuovi download di temperatura.
   - Popolazione residente — **fatto il 2026-07-16**. Dopo due vicoli ciechi
     (l'API SDMX `esploradati.istat.it` ha la struttura giusta — stessi
     codici `istat_code`, dataflow Piemonte-specifico identificato
     `22_315_DF_DCIS_POPORESBIL1_3` — ma non restituisce osservazioni reali
     per questo dataset; il portale legacy `dati.istat.it` è dismesso,
     redirect a un avviso di decommissioning), trovato `demo.istat.it`
     (sistema attivo e separato, ZIP scaricabile per provincia, nessun
     account) — vedi [Fonti dati](data-sources.md) per il dettaglio
     completo. Script `src/data_acquisition/download_population.py`,
     eseguito su tutte le 8 province: **1180/1180 comuni aggiornati**
     (`municipalities.population`), non solo quelli con temperatura.
     Valori verificati plausibili (Torino 6580 ab/km², Formazza alpina
     3.1 ab/km²).
   - CORINE Land Cover — **fatto il 2026-07-16**. Via manuale (non API,
     vedi sopra la motivazione): l'utente ha scaricato
     `U2018_CLC2018_V2020_20u1.gpkg` (52.794 poligoni, EPSG:3035) via
     "Download by area" su `land.copernicus.eu`. Overlay geopandas
     (`src/data_acquisition/process_land_cover.py`, ~16 secondi per tutti
     i 1180 comuni) → nuova tabella `municipality_land_cover` con %
     urbano/agricolo/forestale/zone umide/acqua per comune. Risultati
     verificati plausibili: Torino 75% urbano, Verbania 41% acqua (sul
     Lago Maggiore), Vercelli/Alessandria/Cuneo/Asti 67-84% agricolo,
     Bardonecchia/Formazza >94% forestale. Vedi [Fonti dati](data-sources.md)
     per il dettaglio completo (inclusi i due tentativi prima del file
     giusto: la prima cartella era solo documentazione, senza geometrie).
   - Entrambe indipendenti dall'estensione a 300 comuni: operano su tutti i
     1180 comuni già in `municipalities`, non solo su quelli con
     temperatura.
4. **Modellazione statistica** — **prima iterazione fatta il 2026-07-17**
   (`src/analysis/spatial_regression.py`), non appena popolazione/CORINE/NDVI
   sono state tutte disponibili per i 63 comuni con temperatura. OLS
   classico (elevazione+popolazione+%urbano+NDVI, VIF tutti <5) →
   Moran's I sui residui ancora significativo (I=0.081, p=0.001) → modello
   a **errore spaziale** (via `spreg`/`libpysal`, regola di Anselin non
   ambigua: LM-error fortemente significativo anche robusto, LM-lag no).
   Risultato piu' rilevante a n=63: **% urbano diventa significativo con
   il segno atteso solo nel modello spaziale** (l'OLS classico lo
   mascherava) — prima conferma quantitativa, seppur provvisoria (n=63, da
   rifare al crescere del campione), dell'ipotesi originale del paper.
   NDVI resta significativo ma con segno controintuitivo (piu' verde →
   piu' caldo), da indagare. **Rieseguito lo stesso giorno (pomeriggio) su
   n=98** dopo l'import di 35 comuni extra da una seconda macchina (vedi
   [Fonti dati](data-sources.md)): a campione piu' ampio **% urbano non e'
   piu' significativo** (p=0.334, coefficiente ancora positivo ma piccolo)
   — il risultato di n=63 non si e' confermato. NDVI resta significativo
   con lo stesso segno controintuitivo. Onesto registrare il cambio invece
   di tenere solo il risultato "piu' favorevole": con un campione ancora
   piccolo per la spatial econometrics, questo genere di risultato non
   robusto al variare di n va aspettato e discusso nel paper stesso, non
   nascosto. **Rieseguito due volte in piu' il 2026-07-18** (n=155 poi
   n=177, dopo un'altra collaborazione esterna piu' un download diretto):
   a n=177 **anche NDVI smette di essere significativo** (p=0.58, era
   p=0.007 a n=98) — nessuna delle due covariate (% urbano, NDVI) e'
   risultata significativa in piu' di una versione su tre provate
   (n=63/98/177), mai le stesse due insieme. Solo l'elevazione resta un
   predittore robusto e stabile in tutte le versioni (stesso segno,
   stessa grandezza, sempre p<0.001).

   **Le due covariate non instabili si comportano in modo diverso, e
   vale la pena distinguerli nel paper**: per NDVI non e' solo il
   p-value a superare/scendere sotto 0.05, e' il **coefficiente stesso a
   crollare dell'85%** tra n=98 e n=177 (+1.089 → +0.161) — un
   comportamento non spiegabile con la semplice riduzione dell'errore
   standard all'aumentare di n (che renderebbe la stima piu' precisa
   attorno allo stesso valore, non diversa), piu' coerente con l'ipotesi
   che il "segnale" NDVI a n=98 fosse in parte un artefatto di un
   campione ancora piccolo e non rappresentativo. % urbano invece ha un
   coefficiente piccolo ma stabile sia a n=98 sia a n=177 (+0.0056 →
   +0.0063): li' e' cambiato solo il p-value, piu' coerente con un
   effetto debole ma reale che richiede piu' potenza statistica (quindi
   piu' comuni) per emergere con sicurezza. Questa distinzione — "il
   coefficiente si muove" vs "solo la sua significativita' oscilla" — e'
   essa stessa un risultato da riportare nel paper, non solo un dettaglio
   tecnico: allo stato attuale del campione, il progetto non ha evidenza
   solida di un effetto urbano o di vegetazione sulla temperatura, oltre
   alla quota, ma le due covariate meritano un trattamento diverso man
   mano che il campione cresce (NDVI da rivalutare da capo, % urbano da
   continuare a monitorare per convergenza). Dettaglio completo, incluso
   il caveat sulla sensibilita' alla matrice pesi spaziale, in
   [Analisi statistica](statistical-analysis.md).
5. **Percorso di pubblicazione realistico senza affiliazione accademica**:
   preprint (arXiv/EarthArXiv, gratuito e citabile subito) → conferenza SISC
   (Società Italiana per le Scienze del Clima, barriera d'ingresso bassa per
   ricercatori indipendenti/studenti) → eventualmente rivista (candidate:
   *Urban Climate*, *Theoretical and Applied Climatology*, *Climate*/
   *Atmosphere* di MDPI con richiesta di waiver sull'APC).

## Letteratura raccolta (2026-07-16)

Da citare, organizzata per ruolo nel paper:

- **Definizione di ondata di calore/metriche**: Perkins & Alexander (2013,
  J. Climate, *On the Measurement of Heat Waves*) — definizione a
  percentile 90°, già discussa nel tab "Dettaglio tecnico" della dashboard
  (vedi [Dashboard](dashboard.md), `components/heatwave_definitions.py`);
  Nairn & Fenwick, *The Excess Heat Factor* — metrica alternativa
  all'`intensity_index` del progetto.
- **UHI a Torino/Piemonte** (il più vicino a quello che vuole fare
  l'utente): Garzena et al. (2019, *Weather*/Wiley) — 147 anni di dati,
  Torino vs stazioni rurali; *An innovative approach to select
  urban-rural sites for UHI analysis: the case of Turin* (Urban Climate) —
  metodologia di selezione siti; *Characterization of the Urban Heat and
  Dry Island effects in the Turin metropolitan area* (Urban Climate) — 20
  anni di dati orari ARPA Piemonte; studio numerico su UHI a Torino durante
  l'ondata di calore 2019 (pattern termici e circolazione locale, incluso
  il Foehn).
- **Uso del suolo → temperatura** (template metodologico per la fase 3-4):
  *Surface urban heat islands in Italian metropolitan cities: Tree cover
  and impervious surface influences* (Sci. Total Environ.) — quantifica
  +4°C di SUHI ogni +10% di superficie impermeabile, regressione con
  CORINE Land Cover su città italiane; Frontiers, *Mapping urban heatwaves
  and islands: the reverse effect of Salento's "white cities"* — caso
  controintuitivo utile per la discussione su fattori mitiganti.
- **Contesto climatico regionale/nazionale** (per l'introduzione): Settanta
  et al. (2024, *Theoretical and Applied Climatology*, 155, DOI
  10.1007/s00704-024-05063-w) — fonte esatta del dato "+7.5 giorni/decade"
  (250+ stazioni, 1991-2020, 77% delle stazioni +3gg/decade), preprint ad
  accesso aperto scaricato in `paper/references/`; Capozzi, Di Bernardino
  & Budillon (2025, *Atmospheric Research*, 319, DOI
  10.1016/j.atmosres.2025.108013) — completa il titolo già raccolto il
  2026-07-16 ("Changes in large-scale circulation..."), paywall, nessuna
  versione aperta trovata; variabilità termica Po Valley da radiosondaggi
  (arXiv, titolo esatto ancora da recuperare).

## Confronto con report istituzionali (ISTAT, ARPA, ISPRA/SNPA) — aggiunto il 2026-07-19

Su richiesta esplicita dell'utente ("vorrei fare il confronto con altri
articoli scientifici di istat, arpa, ispra e altri"), cercati e scaricati
report ufficiali recenti per confrontare i risultati del progetto con
stime istituzionali indipendenti sullo stesso territorio/fenomeno. Tutti
verificati con una richiesta HTTP diretta (200 OK, `Content-Type:
application/pdf`) prima del download, non solo citati a memoria — PDF
completi in `paper/references/` (vedi `paper/references/README.md` per
il dettaglio completo, incluse le dimensioni dei file e perché ciascuno è
stato scelto):

- **SNPA — *Il clima in Italia nel 2025*** (Report Ambientali SNPA n.
  48/2026, pubblicato 2026-07-01) — sintesi nazionale annuale, coordinata
  da ISPRA con dati di tutte le ARPA regionali.
- **ARPA Piemonte — *Il clima in Piemonte — Anno 2025*** (pubblicato
  2026-02-18) — il confronto diretto più rilevante per questo progetto,
  stessa regione: **2025 quinto anno più caldo dal 1958** in Piemonte
  (temperatura media annua ~10.8°C, +quasi 1°C sopra il trentennio di
  riferimento 1991-2020) — da confrontare esplicitamente in discussione
  col trend Mann-Kendall 2000-2025 già calcolato (+0.3/+1.4 °C/decade su
  44 comuni, `paper/manoscritto.md` §3.1).
- **ISTAT — Statistica Focus METEOCLIMA, anno 2022** (pubblicato
  2024-10) — indice di ondata di calore a percentile per capoluogo di
  provincia: stessa famiglia metodologica (soglia relativa) della
  definizione alternativa già implementata in
  `dashboard/components/heatwave_definitions.py`, utile per discutere il
  limite della soglia fissa usata come definizione canonica del progetto.
- **ISPRA — Focus "Le città, la sfida dei cambiamenti climatici"** —
  approfondimento sull'isola di calore urbana nelle città italiane,
  complementare alla letteratura UHI su Torino già raccolta sopra.

Anche la bibliografia già raccolta il 2026-07-16 è stata completata dove
possibile con dettagli verificati via l'API pubblica di Crossref
(autori/rivista/volume/DOI), non lasciata a titoli informali quando un
riscontro reale era reperibile — vedi la sezione sopra e
`paper/manoscritto.md` per il dettaglio.

**Capozzi et al. (2025), Appennini — procurato dall'utente lo stesso
giorno, dopo un primo tentativo fallito**: il primo giro di ricerca
web aveva trovato solo il DOI/link ScienceDirect (apparentemente
paywalled) di *Changes in large-scale circulation behind the increase
in extreme heat events in the Apennines (Italy)* (Capozzi, Di
Bernardino, Budillon — *Atmospheric Research*, 319, 108013). L'utente
ha scaricato il file da solo, ma i primi 3 tentativi hanno preso per
errore altri articoli dello stesso fascicolo di rivista (l'editoriale
+ due paper non pertinenti — uno su previsione stagionale ENSO/IOD in
Asia, uno su polvere sahariana e fulmini in Corsica), scoperti come
sbagliati leggendo il contenuto reale con `pdftotext` invece di
fidarsi del nome del file, ed eliminati su richiesta dell'utente. Il
file giusto è arrivato al tentativo successivo — verificato allo
stesso modo (prima pagina reale = titolo/autori/abstract corretti).
**Scoperta utile dalla lettura del testo**: l'articolo è in realtà
**open access nativo (licenza CC BY)**, non paywalled come sembrava
dal primo tentativo di accesso via ScienceDirect — e contiene la
**fonte esatta del dato "+134%"** citato dal 16/7 senza riferimento
preciso: eventi estremi di caldo negli **Appennini** (non "Nord
Italia/Arco Alpino" come erroneamente scritto nella raccolta
iniziale — corretto in `paper/manoscritto.md` §1.1), 1991-2020 vs
1961-1990, **+134% in estate, +102% in primavera** (+53% inverno,
+27% autunno, questi ultimi due non sempre significativi). File in
`paper/references/Capozzi_2025_Apennines_extreme_heat_circulation.pdf`
(22.7 MB).

## Riferimenti metodologici (aggiunti il 2026-07-19)

Su richiesta esplicita dell'utente, aggiunti i riferimenti classici dei
metodi statistici/spaziali già usati in `src/analysis/` — necessari
perché la futura pagina dashboard "Sintesi della Ricerca" (vedi sotto)
cita ogni affermazione, non solo i risultati: Mann (1945) e Kendall
(1975) per il test di trend; Moran (1950) per l'indice di
autocorrelazione spaziale; Cleveland et al. (1990) per la scomposizione
STL; MacQueen (1967) per il K-means; Anselin (1988) per il modello a
errore spaziale. Elenco completo con DOI dove disponibile in
`paper/manoscritto.md` (sezione Bibliografia) e nella pagina dashboard
[Citazioni e Fonti](dashboard.md).

## Idee da esplorare (non implementate, tracciate il 2026-07-16)

Discusse con l'utente, non ancora avviate — l'utente ha scelto di procedere
prima con la scomposizione urbana (vedi sopra) e di aspettare i 300 comuni
prima del resto.

**1. Aggiungere popolazione/uso del suolo alla dashboard — fatto il
2026-07-16.** Mappa uso del suolo dominante e mappa densità di popolazione
(tutti i 1180 comuni), più uno scatter temperatura/uso del
suolo/popolazione con selettore di variabile, che sostituisce il vecchio
confronto "isola di calore urbana" (Torino vs media provincia, dichiarato
"solo illustrativo"). Dettaglio completo in [Dashboard](dashboard.md).

**2. Altre covariate esplicative candidate**, in ordine di sforzo
crescente:
- NDVI/verde da satellite — **fatto (2026-07-17)**. Scartato Sentinel-2
  vero (10m, via Google Earth Engine o Copernicus Data Space Ecosystem
  Statistical API) a favore di Copernicus Global Land Service NDVI 300m V3
  (prodotto gia' calcolato, stesso pattern low-effort di CLC), decisione
  presa con l'utente — un'apparente scorciatoia verso un prodotto NDVI
  10m reale (HR-VPP) si e' rivelata un vicolo cieco (non raggiungibile dal
  Copernicus Browser). `municipality_ndvi` popolata per tutti i 1180
  comuni. Dettaglio completo (incluse le difficolta' reali del portale di
  download e la verifica empirica scala/offset/flag sul file) in
  [Fonti dati](data-sources.md) e [Modello dati](data-model.md).
- Pendenza ed esposizione del versante da un DEM (es. Copernicus GLO-30) —
  più dettagliato della sola elevazione del centroide già disponibile; un
  versante esposto a sud scalda diversamente da uno a nord, specie in
  montagna.
- Distanza dal Po/dai laghi — più precisa dell'attuale `pct_water` (che è
  0 per la maggior parte dei comuni pur essendo vicini all'acqua senza
  contenerla).
- Densità stradale/edificato da OpenStreetMap — proxy di traffico/
  urbanizzazione; il progetto ha già un `OpenStreetMapDownloader` in
  `src/data_acquisition/download_data.py`, mai attivato di default (vedi
  [Fonti dati](data-sources.md)).

## Pagina dashboard "Sintesi della Ricerca" (06) — implementata il 2026-07-19 (sera)

Su richiesta dell'utente: due nuove pagine dashboard, non solo il paper
tecnico. Entrambe fatte: [Citazioni e Fonti](dashboard.md) (`08`, vedi
sopra) e questa, `06_sintesi_della_ricerca.py` (creata come `07`, poi
rinumerata a `06` lo stesso giorno su richiesta esplicita dell'utente:
Download Dati doveva spostarsi dopo questa pagina, non prima, quindi
rinumerato a `07`) — una pagina divulgativa
(non il paper tecnico, quello resta in `paper/manoscritto.md`) che
riassume dati raccolti e risultati per un pubblico non specialistico,
citando ogni affermazione. Scritta dopo la conferma dell'utente che il
ricalcolo dati della mattina (44→234 comuni) era concluso — i numeri
usati vengono dai file `output/*.csv` correnti e dalle query live di
`components/queries.py`, **non** da `paper/manoscritto.md`, rimasto
stale ai numeri di 44 comuni (vedi nota sotto). Dettaglio implementativo
completo in [Dashboard](dashboard.md).

**Scoperta di sostanza emersa verificando i numeri correnti prima di
scrivere la pagina**: il modello a errore spaziale rieseguito a n=234
mostra ora **% urbano significativo** (p=0.031, segno atteso) mentre
**NDVI non lo è più** (coefficiente sceso a +0.10) — invertito rispetto
a n=98, dove era il contrario. Prima conferma quantitativa, seppur
provvisoria, dell'ipotesi originale del progetto. Trovati anche 2 comuni
alpini (Argentera, Briga Alta) con trend di **raffreddamento**
significativo, inclusi nella pagina invece di presentare il
riscaldamento come unanime.

**Disallineamento aperto**: `paper/manoscritto.md` (§3.1-3.6, Abstract)
descrive ancora l'analisi su 44 comuni — non aggiornato in questa
sessione, segnalato esplicitamente all'utente. La dashboard (questa
pagina e le altre) e il manoscritto tecnico raccontano quindi, per ora,
due stati diversi del progetto: la dashboard è allineata al campione
corrente (234 comuni), il manoscritto no.

Sottocapitoli:

1. Perché questo progetto — contesto (riscaldamento Nord Italia/Arco
   Alpino, letteratura consolidata su Torino ma non sul resto della
   regione).
2. I dati raccolti — riassunto di tutti i dati del progetto (comuni,
   anni, fonti, righe).
3. Come misuriamo il riscaldamento — trend Mann-Kendall, stagionalità
   STL, in breve e citate (vedi "Riferimenti metodologici" sopra).
4. Cosa abbiamo trovato — trend diffuso, pattern spaziale, ondate di
   calore, confronto con Garzena et al. (2019) su Torino e con i report
   istituzionali sopra (ARPA Piemonte in particolare).
5. Uso del suolo e popolazione — se il modello a errore spaziale lo
   conferma dopo il ricalcolo.
6. **Limiti** (titolo corretto il 2026-07-19 su richiesta esplicita
   dell'utente: non più "Limiti, onestamente" — il contenuto resta lo
   stesso, solo il titolo è stato reso più neutro) — dati da rianalisi,
   validazione ARPA, copertura parziale.
7. Cosa significa in pratica.
8. Rimando alla pagina [Citazioni e Fonti](dashboard.md) per l'elenco
   completo.

## Manoscritto

Lo scheletro vero e proprio del paper (Abstract/Intro/Metodi/Risultati/
Discussione/Bibliografia, con marcatori **[FATTO]**/**[DA FARE]** per
distinguere cosa si basa su risultati reali già calcolati da cosa dipende
da lavoro non ancora completato) vive in `paper/manoscritto.md`, non in
questa pagina wiki — questa pagina resta il livello di pianificazione/
tracciamento, il file in `paper/` è il contenuto del paper stesso. Creato
il 2026-07-16, in italiano (da tradurre in inglese solo a ridosso della
sottomissione).

## Prossimi passi

Vedi [Stato del progetto](project-status.md) per lo stato operativo
aggiornato di ETL/analisi. Con popolazione, uso del suolo, NDVI (2026-07-16/17)
e ora anche la validazione ARPA (2026-07-18, vedi fase 1 sopra) fatti,
restano aperti:
(a) l'estensione del campione di comuni con temperatura (in corso,
gradualmente — 44→63→98→155→177 al 2026-07-18, vedi
[Fonti dati](data-sources.md)) — priorita' alta anche per la
modellazione: n=177 resta piccolo per la spatial econometrics, e nessun
risultato su % urbano/NDVI e' stato stabile passando da 63 a 98 a 177
(vedi punto 4 sopra) — il campione crescente andra' rilanciato attraverso
`spatial_regression.py` via via che arrivano nuovi comuni; la validazione
ARPA andra' probabilmente ri-eseguita alla fine per gli stessi motivi
(nuovi comuni possono aggiungere nuovi match con stazioni ARPA finora non
coperte);
(b) ~~la validazione ARPA~~ — **fatta il 2026-07-18** (vedi fase 1 sopra):
confermato che le temperature Open-Meteo sono sistematicamente distorte in
modo dipendente dall'elevazione (bias -1.71°C medio, più negativo nei
comuni alti, r=-0.348 p=0.012) — non solo l'ipotesi qualitativa "dati di
rianalisi spazialmente lisci", ma una quantificazione reale del fenomeno,
utilizzabile nel paper sia come limite dichiarato sia come possibile
spiegazione parziale dell'autocorrelazione residua vista nel modello
spaziale;
(c) approfondire il segno controintuitivo di NDVI nel modello (vedi punto
4) prima di scriverlo nel manoscritto come risultato consolidato.
Il file `paper/manoscritto.md` va aggiornato in parallelo.
