# Comuni già coperti — guida per nuovi download collaborativi

**A cosa serve questa pagina**: elenco di tutti i comuni che hanno **già**
temperature reali in `temperature` (tabella del DB), da consultare
**prima** di scaricare nuovi dati da Open-Meteo — sia per chi lavora da
una seconda macchina senza accesso diretto al DB del titolare (vedi
[Fonti Dati](data-sources.md#download-collaborativo-da-una-seconda-macchina--35-comuni-extra-2026-07-17)
per il precedente di questo tipo), sia per chiunque scarichi nuovi lotti
in autonomia. Evita di ripetere lo stesso lavoro due volte o, peggio, di
scaricare due volte lo stesso comune sprecando quota di rate limit
giornaliero (vedi [Fonti Dati](data-sources.md) per il limite scoperto il
2026-07-17).

**Aggiornamento 2026-07-24 — quinto giorno consecutivo, metodo DB-free,
93 comuni (record della serie)**: stessa richiesta dell'utente ("come gli
altri giorni"), stesso script DB-free descritto in
[Pipeline ETL](etl-pipeline.md) (ricreato da zero, la cartella temporanea
di sessione cambia a ogni conversazione). Candidati selezionati escludendo
i **599 comuni** già coperti dopo il giro di import del 2026-07-23 (vedi
voce subito sotto) — non più 569, la base è cambiata nel frattempo.

**Scaricati 93 comuni**, il lotto più numeroso di tutta la serie DB-free
(quasi il doppio del solito 57) — un blocco transitorio su "Altavilla
Monferrato" si è risolto dopo un solo comune fallito (il comune successivo,
"Camerano Casasco", è andato a buon fine con un backoff breve), poi blocco
persistente confermato su "Caramagna Piemonte" e "Villar Perosa". Zero
falliti per motivi diversi dalla quota. Verificato senza doppioni interni
né sovrapposizioni con i 599 già coperti.

File prodotti in `data/raw/` (fuori Git, da consegnare al collega fuori
canale): `temperature_data_extra_helper_general_20260724.csv` (902.286
righe, 93 comuni, 2000-01-01 → 2026-07-24) e
`riepilogo_generale_20260724.csv` (sintesi per comune).

Tabella "Comuni già coperti" sotto rigenerata di conseguenza:
**692/1180 comuni coperti** (era 599), **488 ancora scaricabili
liberamente**.

**Aggiornamento 2026-07-24 (seguito) — unione + reset dell'accumulatore +
nuovo giro dal titolare/IA**: dopo `git pull`, uniti i 93 comuni sopra.
**`temperature_data_extra.csv` (370MB) era interamente ridondante** — tutti
i suoi 591 comuni erano già stati importati nel giro unico del 2026-07-23
(vedi sotto) — verificato prima di eliminarlo (nessun comune fuori dal
DB), poi ricreato da zero come accumulatore pulito con solo i 93 comuni
di oggi (902.286 righe), invece di appendere a un file ormai inutile.
Rilanciato subito dopo il download generale sui comuni ancora mancanti
(692 coperti, 488 mancanti all'avvio): **bloccato dopo 19/438** (su
"Belforte Monferrato", confermato dal blocco anche sul successivo
"Fresonara"). I 19 riusciti uniti allo stesso file (93 → **112 comuni**,
zero sovrapposizioni). Tabella "Comuni già coperti" sotto ricalcolata:
**711/1180 comuni coperti** (era 692), **469 ancora scaricabili
liberamente**. **Nessun import né ricalcolo**, come da decisione del
2026-07-20 (ancora valida: nessuna nuova indicazione di farlo prima
della prossima sessione).

**Aggiornamento 2026-07-23 (pomeriggio) — GIRO UNICO DI IMPORT ESEGUITO,
234 → 599 comuni**: su richiesta esplicita dell'utente, fatto il giro
unico di import + ricalcolo rimandato dal 2026-07-20. Consolidati tutti i
lotti pendenti (347 comuni nuovi da `temperature_data_extra.csv`, 18 da
Torino, 267 righe di delta per i 177 comuni originali) — **3.540.507
righe pulite e inserite**, **599 comuni** ora in `temperature`
(5.809.330 righe). Ricalcolo a valle: elevazione 599/599,
`TRUNCATE`+`identify_heatwaves()` → **2.192 ondate** (da 770),
`kpi_annual_by_municipality` → **16.173 righe** (599×27 anni). Mappe QGIS
rigenerate. `download_arpa.py` e `refresh_dashboard.py` (analisi
completa + export dashboard) lanciati **in parallelo** per risparmiare
tempo (217 comuni ARPA scaricati in ~2h, poi importati mentre la STL era
ancora a metà) — **STL completata in 4h10min** per 599 comuni, tutti e 7
gli step riusciti. **Copertura ARPA ora completa: 218/218 comuni** hanno
sia Open-Meteo che ARPA (era 108/234) — bias -1.52°C (stabile), recall
ondate risalito al 25.2% (da 16.4%), vedi [Analisi
statistica](statistical-analysis.md#validazione-contro-arpa-piemonte-2026-07-18-estesa-il-2026-07-19-copertura-completa-il-2026-07-23)
per il dettaglio completo. File raw/processed consolidati: `temperature_data_extra.csv`
assorbe anche il lotto Torino (591 comuni), `temperature_data_recent.csv`
e gli archivi ormai ridondanti eliminati; stesso consolidamento sui file
`data/processed/` (77.576 + 5.731.754 = 5.809.330, combacia col DB).
**Bug trovato e corretto durante il consolidamento**: un errore mio nel
merge dei capoluoghi ha temporaneamente sovrascritto la colonna
`province` con valori vuoti per 16 righe, causando la perdita silenziosa
di 14 righe per una deduplica su chiave sbagliata — scoperto verificando
il totale contro il DB (non tornava), corretto ricalcolando la colonna
da `municipality_id` invece che dalla colonna vuota.

**Decisione del 2026-07-20 — accumulo dati SENZA import/ricalcolo**:
l'utente ha deciso esplicitamente di **non importare né ricalcolare** ad
ogni sessione di download — l'intera pipeline a valle (pulizia, join,
insert, `TRUNCATE`+`identify_heatwaves()`, refresh viste, tutti i moduli
`src/analysis/`, mappe QGIS) richiede ore (vedi il ricalcolo del
2026-07-19, ~2h20min solo per l'ultimo giro) e non ha senso ripeterla ogni
giorno. **Il piano ora è**: continuare ad accumulare comuni scaricati (da
più fonti/sessioni) in `data/raw/temperature_data_extra.csv` per qualche
giorno, poi fare **un solo giro di import + ricalcolo completo** quando se
ne sarà raccolto abbastanza. Fino ad allora, **`temperature` (DB) resta
volutamente indietro** rispetto ai file raw — questo è intenzionale, non
un lavoro dimenticato. Vedi sezione "Obiettivo reale" più sotto per lo
stato aggiornato dei comuni ancora mancanti.

**Aggiornamento 2026-07-23 — 8 doppioni scoperti: causa root trovata
(wiki non pushata)**: la collaboratrice ha consegnato altri **57 comuni
generici** (`temperature_data_extra_helper_general_20260723.csv` +
riepilogo). All'unione, **8 comuni si sovrapponevano** con quanto già
accumulato (Cremolino, Frugarolo, Monleale, Pontestura, Pozzolo
Formigaro, Quargnento, Rivalta Bormida, Tagliolo Monferrato — 77.600
righe duplicate, deduplicate prima di salvare). **Causa identificata**:
il titolare/IA aveva aggiornato questa pagina la sera del 2026-07-22 (i
19 comuni del giro precedente, inclusi 4 di quelli sopra) ma **non aveva
mai committato/pushato** la modifica — la collaboratrice, lavorando da
`git pull`, ha visto uno snapshot di un giorno indietro e non poteva
sapere che quei comuni fossero già presi. **Lezione**: committare (e
idealmente pushare) gli aggiornamenti di questa pagina subito dopo ogni
sessione di download, non lasciarli come modifiche locali non
committate — altrimenti il meccanismo di coordinamento via wiki+git non
funziona. Uniti in `temperature_data_extra.csv` (505 → **554 comuni**
dopo la deduplica), file della collaboratrice eliminati.

Il titolare/IA ha rilanciato subito dopo il download generale sui comuni
ancora mancanti (**580 coperti, 600 mancanti** all'avvio): **bloccato
dopo 19/574** (su "Avolasca", confermato dal blocco anche sul successivo
"Sala Monferrato") — presi al volo anche i due comuni bloccati ieri
(Felizzano, Mombello Monferrato), ora scaricati con successo. I 19
riusciti uniti allo stesso file (554 → **573 comuni**, zero
sovrapposizioni). Tabella "Comuni già coperti" sotto ricalcolata:
**599/1180 comuni coperti** (era 531), **581 ancora scaricabili
liberamente** — quasi a metà strada. **Nessun import né ricalcolo**, come
da decisione del 2026-07-20.

**Aggiornamento 2026-07-23 — quarto giorno consecutivo, stesso metodo
DB-free, altri 57 comuni**: stessa richiesta dell'utente ("come gli altri
giorni"), stesso script della sessione precedente (non salvato nel repo,
solo descritto in [Pipeline ETL](etl-pipeline.md)), ricreato da zero
perché vive in una cartella temporanea fuori dal repo. **Scaricati altri
57 comuni** (2000-01-01 → 2026-07-23), zero falliti per motivi diversi
dalla quota, bloccato dopo 57 (backoff crescente su "Grana Monferrato",
confermato sul successivo "Sostegno" — terzo giorno di fila che si
ferma esattamente a 57, coincidenza numerica non un limite fisso: il
conteggio di righe scaricate è leggermente diverso ogni giorno, 552.957
oggi contro 552.900 il 2026-07-22, perché la serie storica si allunga di
un giorno ogni 24 ore). Verificato senza doppioni interni né
sovrapposizioni con i 512 comuni già coperti.

File prodotti in `data/raw/` (fuori Git, da consegnare al collega fuori
canale): `temperature_data_extra_helper_general_20260723.csv` (dati) e
`riepilogo_generale_20260723.csv` (sintesi). **Nota**: i file della
sessione del 2026-07-22 non erano più presenti in `data/raw/` all'inizio
di questa sessione — segno che sono già stati presi in consegna dal
collega, coerente con la convenzione "file eliminati dopo l'unione".

Tabella "Comuni già coperti" sotto rigenerata di conseguenza:
**569/1180 comuni coperti** (era 512), **611 ancora scaricabili
liberamente**.

**Aggiornamento 2026-07-22 — nuovo lotto generale, 57 comuni, metodo
DB-free**: su richiesta dell'utente ("scarica nuovi comuni... fino a
quando non ci blocca"), lanciato un altro giro di estensione generale
(stesso criterio spaziale farthest-point-sampling per provincia di
`download_extra_municipalities.py`) da **questa macchina, senza accesso al
DB** — stesso vincolo della collaboratrice delle sessioni precedenti.
Sostituite le due query dirette al DB (`load_all_municipalities()`,
`already_downloaded_ids()`) con fonti locali equivalenti:
- **Lista completa dei 1180 comuni + coordinate**: join tra lo shapefile
  ufficiale ISTAT già scaricato in
  `data/external/istat_confini/Com01012026_g/` (filtrato `COD_REG==1`) e
  `data/dashboard_export/municipality_metadata_all.parquet` (lat/lon,
  export statico già usato dalla dashboard, vedi [Dashboard](dashboard.md)).
  **Bug scoperto e corretto**: il `.dbf` dello shapefile ha un problema di
  encoding (bytes UTF-8 letti come Latin-1, "Agliè" diventava
  "AgliÃ¨") che faceva fallire il join per nome su 28/1180 comuni (tutti
  quelli con lettera accentata) — risolto con
  `nome.encode('latin-1').decode('utf-8')` prima del join, verificato poi
  che tutti e 1180 i comuni si abbinano.
- **Comuni già coperti (da escludere)**: parsati dalla tabella "Comuni già
  coperti" di questa stessa pagina (455 codici ISTAT), non da una query
  DB — è esattamente la fonte di verità che questa pagina è pensata per
  essere.

Scaricati **57 comuni** (2000-01-01 → oggi, storico completo), zero
falliti per motivi diversi dalla quota, **bloccato dalla quota dopo 57**
(pattern di backoff crescente su "Capriglio", confermato sul successivo
"Pollone", stesso identico numero della sessione del 2026-07-19 — pura
coincidenza, non un limite fisso). File prodotti in `data/raw/` (fuori
Git, da consegnare al collega fuori canale, stesso formato descritto
sotto): `temperature_data_extra_helper_general_20260722b.csv` (dati) e
`riepilogo_generale_20260722b.csv` (riepilogo per comune). Suffisso "b"
per non confondersi con `temperature_data_extra_helper_general_20260722.csv`
già presente da una sessione precedente (nome scelto quel giorno per un
delta mai eseguito con quel nome). Tabella "Comuni già coperti" sotto
aggiornata di conseguenza: **512/1180 comuni coperti** (era 455),
**668 ancora scaricabili liberamente**.

**Aggiornamento 2026-07-22 (seguito) — unione + nuovo giro dal
titolare/IA**: dopo `git pull`, uniti i 57 comuni sopra in
`temperature_data_extra.csv` (429 → **486 comuni**, zero sovrapposizioni,
file del collega eliminati). Rilanciato subito dopo un altro giro dello
stesso criterio spaziale sui **668 comuni ancora mancanti**: **bloccato
dopo 19/650** (su "Felizzano", confermato dal blocco anche sul successivo
"Mombello Monferrato") — quota quasi certamente già consumata dal lotto
del collega nella stessa giornata (57 comuni a storico completo). I 19
riusciti uniti allo stesso file (486 → **505 comuni**, zero
sovrapposizioni). Tabella "Comuni già coperti" sotto ricalcolata:
**531/1180 comuni coperti** (era 512), **649 ancora scaricabili
liberamente**. **Nessun import né ricalcolo**, come da decisione del
2026-07-20 — si continua ad accumulare.

**Aggiornamento 2026-07-21 — obiettivo ARPA completato al 100%, ripresa
estensione generale**: la collaboratrice ha consegnato gli ultimi **22
comuni ARPA-target** (0 falliti, quota non toccata) — **tutti e 167 i
comuni ARPA-senza-Open-Meteo sono ora scaricati**, storico completo.
Contestualmente ha consegnato anche **85 comuni generici** (ripresa del
criterio di estensione spaziale ordinario, non più ARPA-target).
**Entrambi i lotti uniti in `temperature_data_extra.csv`** (226 → 410
comuni nel file) — ma con un **bug reale trovato e corretto durante
l'unione**: 2 comuni (Pragelato, Sestriere) comparivano in **entrambi** i
lotti della collaboratrice, scaricati due volte nella stessa sessione
probabilmente perché il controllo "già scaricato" della sua selezione
generale ha guardato solo il DB (fermo a 234), non anche il file
`arpa_final22.csv` appena prodotto nella stessa sessione — 19.398 righe
duplicate rilevate e rimosse (verificate identiche prima di eliminarle,
non uno scarto arbitrario). **Lezione per le prossime sessioni,
collaboratrice inclusa**: il controllo "già coperto" deve sempre
guardare DB **+ tutti i file raw pendenti**, non solo il DB — esattamente
il motivo per cui la tabella "Comuni già coperti" sotto viene
ricalcolata incrociando tutte le fonti, non solo `temperature`.

Il titolare/IA ha poi rilanciato il download generale (stesso criterio
spaziale, tutti i **744 comuni ancora mancanti** come target, fino al
blocco quota): **bloccato dopo 19/720** (su "Silvano d'Orba", confermato
dal blocco anche sul successivo "Ozzano Monferrato") — il lotto più
piccolo di questa serie, quota evidentemente già parzialmente consumata
dai due lotti della collaboratrice nella stessa giornata (22+85=107
comuni a storico completo, volume enorme). I 19 riusciti uniti in
`temperature_data_extra.csv` (410 → **429 comuni**, zero sovrapposizioni).
**Nessun import né ricalcolo eseguito** (stessa decisione del 2026-07-20,
confermata): si continua ad accumulare in attesa di un giro unico.

**Totale accumulato non ancora importato**: `temperature_data_extra.csv`
a 429 comuni (da 226 il 2026-07-20 mattina — +203 in due giorni), più i
18 di Torino ancora a parte. Tabella "Comuni già coperti" sotto
ricalcolata di conseguenza: **455/1180 comuni coperti** (era 331 ieri
sera), quindi **725 comuni ancora scaricabili liberamente** (non 849 —
quel numero, nella nota di ieri sera più sotto, è superato). L'obiettivo
ARPA-target non esiste più come lista a parte: **completato al 100%**.

**Stato al 2026-07-20 (sera) — 331 comuni coperti su 1180, NON
riscaricare nessuno di questi**: la tabella "Comuni già coperti" sotto è
stata ricalcolata da zero incrociando **tutte** le fonti, non solo il DB —
234 comuni già in `temperature`, più altri 97 già scaricati ma ancora solo
su file raw in attesa d'importazione (`temperature_data_extra.csv` e
`temperature_data_extra_torino_2026-07-19.csv`, vedi nota sopra sul perché
non sono ancora nel DB). Questa distinzione **non conta** per chi deve
decidere cosa scaricare: un comune già presente in un file raw (anche se
non ancora importato) **non va ridownloadato**, altrimenti si spreca
quota e si creano doppioni al momento dell'import. La tabella per
provincia sotto riflette già questo — è la lista completa e aggiornata da
consultare prima di qualunque nuovo download, per la collaboratrice o per
chiunque altro.

**Comuni nuovi da scaricare (uso generico, non ARPA-target)**: qualunque
comune **non presente** nella tabella sotto — restano **849** su 1180.
Per questi va usato il criterio spaziale di sempre (vedi ["Come scaricare
nuovi comuni"](#come-scaricare-nuovi-comuni-open-meteo-storico-2000--oggi)
più sotto), **non** la lista ARPA-target (quella è un obiettivo diverso,
vedi sezione dedicata). Se invece l'obiettivo è completare la mappa Bias
ARPA, i comuni da scaricare sono solo i **22 elencati nella sezione
"Obiettivo reale"** più sotto, un sottoinsieme molto più piccolo e
specifico di questi 849.

**Stato al 2026-07-18 (aggiornato due volte in giornata)**: **177 comuni
coperti su 1180** (8 capoluoghi di provincia + 169 extra), 2000-01-01 →
oggi.

**Stato al 2026-07-19 (import comuni ARPA-target dalla collaboratrice)**:
**234 comuni coperti** — importati i 57 comuni consegnati dalla
collaboratrice (vedi sezione "Obiettivo reale" sotto per il dettaglio),
`temperature` ora a 2.268.823 righe. Ricalcolo a valle completo: elevazione
234/234, `heatwave_events` 640 → **770**, `kpi_annual_by_municipality`
**6.318 righe** (234 comuni × 27 anni), `kpi_annual_by_province` invariato
a 216. `download_arpa.py` rilanciato di conseguenza (su richiesta esplicita
dell'utente, dopo un primo fraintendimento): **108/234 comuni Open-Meteo
hanno anche ARPA** (era 51), la mappa Bias raddoppia di campione. Pipeline
di analisi completa rieseguita (`refresh_dashboard.py`, ~2h20min totali
con un'interruzione e ripartenza a metà) — vedi [Pipeline
ETL](etl-pipeline.md#import-dei-57-comuni-arpa-target-e-ricalcolo-completo-2026-07-19)
per il resoconto completo e [Analisi
statistica](statistical-analysis.md#validazione-contro-arpa-piemonte-2026-07-18-estesa-il-2026-07-19)
per i risultati aggiornati (bias -1.59°C, quasi invariato).

**Aggiornamento delta del 2026-07-19**: serie estesa fino al 2026-07-19 per
**177/177 comuni** via `update_recent_data.py` (nessun comune nuovo, solo
delta sui comuni già coperti — nessun blocco da quota Open-Meteo su questo
run, solo `ConnectionResetError` transitori). Primo passaggio: 167/177
riusciti, 10 falliti per connessione (Borgoratto Alessandrino, Cessole,
Fubine Monferrato, Marentino, Pietraporzio, Robella, Roletto, Usseglio,
Vigone, Vinchio); **retry mirato sugli stessi 10 riuscito 10/10**. Dati
scaricati ma **non ancora importati** in `temperature`, fermi in
`data/raw/temperature_data_recent.csv` in attesa di import manuale (pulizia
+ join + `insert_temperature_for_municipalities` + ricalcolo a valle, vedi
["Nota per chi importa"](#nota-per-chi-importa-di-solito-il-titolare-o-lia)
sotto).

**Download comuni extra (2026-07-19)**: su richiesta esplicita
dell'utente, oltre al delta si è provato a scaricare comuni **nuovi**
(non ancora in `temperature`), storico completo 2000-01-01 → oggi. **Non
è corretto (vedi correzione sotto) restringersi a una singola provincia
come prossimo passo** — il criterio giusto per i download generici di
comuni extra (quando non si insegue una lista target specifica come
quella ARPA più sotto) resta quello di sempre, **basato sulla posizione
geografica**: campionamento "farthest-point"
([`download_extra_municipalities.py`](#nota-per-chi-importa-di-solito-il-titolare-o-lia),
lo stesso usato dal 2026-07-15), che seleziona comuni distribuendoli su
tutte le province in proporzione alla loro dimensione, per massimizzare
la copertura spaziale invece di concentrarsi su una zona sola. In questa
sessione, per un fraintendimento (vedi sotto), il campionamento è stato
lanciato filtrato su una sola provincia (Torino, 266 mancanti su 312)
invece che su tutte — episodio isolato, non il metodo da riproporre.
**Bloccato dalla quota
giornaliera Open-Meteo dopo soli 18 comuni** (contro i 57+ osservati nei
run di delta da 1-2 giorni): conferma empirica che la quota è legata al
**volume di dati** scaricato, non al numero di richieste — uno storico
completo (~9.700 righe/comune) consuma la quota molto più in fretta di un
delta giornaliero (1-2 righe/comune). Segnale di blocco: dopo alcuni
throttle "al minuto" recuperabili (backoff crescente, si risolvono da
soli), su `Vestignè` i 5 tentativi sono tutti falliti
(`RuntimeError: Rate limit persistente`) e il comune successivo
(`Montanaro`) ha iniziato subito a fallire allo stesso modo — a quel punto
il run è stato interrotto manualmente per non bruciare ore sui retry dei
~246 comuni restanti (ogni comune bloccato costa fino a ~155s di backoff
prima di passare al successivo).

Esito: **18 comuni scaricati con successo** (storico completo, non ancora
importati), 2 falliti per `ConnectionResetError` (Pragelato, Roure — da
riprovare, non è quota), 1 bloccato da quota (Vestignè), 1 interrotto a
metà retry quando il processo è stato fermato (Montanaro, esito
sconosciuto — da riprovare). Output in
`data/raw/temperature_data_extra_torino_2026-07-19.csv` (nome scelto per
non mischiarsi con il precedente `temperature_data_extra.csv` del
2026-07-18, già importato). Comuni scaricati in questa sessione:
Ala di Stura, Angrogna, Burolo, Carmagnola, Castagneto Po, Cuorgnè,
Groscavallo, Ingria, Maglione, Moncalieri, Oulx, Pancalieri, Piscina,
Prali, Prarostino, Riva presso Chieri, Val della Torre, Viù.

**Correzione (stessa giornata)**: il download di Torino sopra era partito
da un fraintendimento — l'obiettivo reale della richiesta dell'utente non
era "estendere la copertura spaziale genericamente", ma **scaricare
Open-Meteo per i comuni che hanno già una stazione ARPA attiva ma non
hanno ancora dati Open-Meteo**, per completare la mappa **Bias
Open-Meteo↔ARPA per comune** (oggi disponibile solo sui 51 comuni che
hanno entrambe le fonti, su 218 comuni ARPA totali). Vedi la sezione
dedicata subito sotto per la lista esatta e lo stato.

Per puro caso **9 dei 18 comuni di Torino scaricati sopra hanno anche
ARPA** (Ala di Stura, Angrogna, Carmagnola, Castagneto Po, Groscavallo,
Moncalieri, Oulx, Prali, Viù) e contano comunque per l'obiettivo reale,
anche se non erano stati scelti per quello. Gli altri 9 (Burolo, Cuorgnè,
Ingria, Maglione, Pancalieri, Piscina, Prarostino, Riva presso Chieri, Val
della Torre) restano utili per la copertura spaziale generale ma non
contribuiscono al confronto ARPA.

## Obiettivo reale: completare la mappa Bias Open-Meteo↔ARPA

**A cosa serve questa sezione**: dei **218 comuni con stazione ARPA
attiva**, solo **51** hanno anche dati Open-Meteo (vedi sezione sopra) —
gli altri **167** hanno ARPA ma **non** Open-Meteo, quindi non compaiono
nella mappa di confronto/bias. Per completarla serve scaricare Open-Meteo
(**storico completo 2000-01-01 → oggi**, non un delta — il bias si calcola
su serie storiche, non su un giorno) per questi 167 comuni.

**Stato al 2026-07-19 (mattina)**: di questi 167, **9 sono già stati
scaricati per caso** durante il tentativo (mal indirizzato) di stamattina
su Torino, vedi sopra — ma **non ancora importati** in `temperature`.
Restano **158 comuni** da scaricare ancora. Quota Open-Meteo di oggi già
bloccata (vedi sopra) — **da riprendere il giorno dopo il reset**, non lo
stesso giorno.

**Aggiornamento (stesso giorno, poco dopo)**: la collaboratrice (stessa
seconda macchina delle sessioni precedenti) ha consegnato **57 comuni**
scaricati direttamente dalla lista dei 167 sopra (round-robin per
provincia, non nell'ordine della tabella — vedi
[Pipeline ETL](etl-pipeline.md#comuni-extra-mirati-alla-validazione-arpa--158-comuni-target-2026-07-19)
per il dettaglio completo del suo download, bloccato anche lei dalla
quota dopo 57/158). **Importati nel DB** (pulizia + join `istat_code` →
`municipality_id` + `insert_temperature_for_municipalities` + ricalcolo a
valle completo, vedi sopra): **234 comuni** ora in `temperature`.
`download_arpa.py` rilanciato di conseguenza: 108/234 comuni con
Open-Meteo hanno anche una stazione ARPA attiva (i 51 di prima + tutti i
57 nuovi, confermando che la lista target era corretta al 100%) — vedi
[Fonti Dati](data-sources.md) per l'esito finale del download e il nuovo
numero di comuni utilizzabili nella mappa Bias.

**Restano 101 comuni** (167 - 9 Torino - 57 collaboratrice) dei 167
originali ancora da scaricare per completare la copertura Open-Meteo su
tutti i comuni ARPA — target per le prossime sessioni, dopo il reset della
quota giornaliera.

**Aggiornamento 2026-07-20 — terzo lotto dalla collaboratrice + 44 in
corso dal titolare/IA**: la collaboratrice ha consegnato altri **57
comuni** (`temperature_data_extra_helper_arpa_target_day3.csv` +
riepilogo), scaricati direttamente dai 101 rimanenti. **Uniti nel file
raw canonico `temperature_data_extra.csv`** (istat_code → municipality_id
risolto, zero sovrapposizioni verificate, 226 → **283 comuni** nel file) —
**deliberatamente NON importati in `temperature`** (vedi nota in cima alla
pagina: import/ricalcolo rimandati di qualche giorno, per non ripetere un
ricalcolo di ore ad ogni sessione). File del collega eliminati dopo
l'unione, come da convenzione.

Contestualmente, il titolare/IA ha calcolato i comuni ARPA-target
**ancora mancanti ovunque** (né in `temperature`, né in `temperature_data_extra.csv`,
né nel file pendente di Torino): **44 comuni** (soprattutto Cuneo e
Torino), avviato il download diretto (storico completo) per tutti e 44,
stesso metodo delle sessioni precedenti. **Bloccato dalla quota dopo
22/44** (su "Viola", stesso pattern di backoff crescente, confermato dal
blocco anche sul comune successivo "Monastero di Lanzo") — fermato
manualmente. I 22 riusciti **uniti nel file raw canonico**
(`temperature_data_extra.csv`, zero sovrapposizioni verificate, 283 → **305
comuni** nel file) — anche questo lotto **non importato in
`temperature`**, in attesa come il resto. File temporaneo di download
eliminato dopo l'unione. **Restano esattamente 22 comuni** su tutti e 218 quelli con ARPA (marcati
senza ✅ nella tabella sotto — verificato incrociando `arpa_temperature`,
`temperature`, `temperature_data_extra.csv` e il file pendente di Torino):
Monastero di Lanzo, Parella, Perrero, Pinerolo, Pragelato, Rivoli, Ronco
Canavese, Sauze d'Oulx, Sestriere, Susa, Trana, Traversella, Valchiusa,
Varisella, Varzo, Venaria Reale, Venaus, Verolengo, Vialfrè, Villafranca
Piemonte, Villanova Solaro, Viola — **da comunicare alla collaboratrice
per la prossima sessione**, così non riscarica quelli già fatti.

**Stato del backlog non ancora importato (2026-07-20)**: `temperature_data_extra.csv`
è passato da 226 a **305 comuni** in giornata (57 collaboratrice + 22
titolare/IA), tutti in attesa del prossimo giro di import. A questi si
aggiungono i 18 comuni di Torino (file separato
`temperature_data_extra_torino_2026-07-19.csv`, dal 2026-07-19) e il
delta 2026-07-19→oggi per i 234 comuni già in `temperature` (anche quello
non ancora importato) — **fino a 97 comuni nuovi** in attesa (305 - 226 +
18), più i 22 ancora da scaricare.

**Aggiornamento 2026-07-21 — OBIETTIVO COMPLETATO AL 100%**: la
collaboratrice ha consegnato gli ultimi 22 comuni (0 falliti). **Tutti e
167 i comuni ARPA-senza-Open-Meteo del target originale sono ora
scaricati** (storico completo 2000→oggi) — uniti in
`temperature_data_extra.csv` (vedi nota in cima alla pagina). Non serve
più consultare l'elenco dei "22 mancanti" sopra: è chiuso. Resta solo da
**importare** (rimandato, vedi decisione del 2026-07-20) perché la mappa
Bias passi effettivamente da 108 a 218/218 comuni. La tabella sotto
resta come riferimento storico di come si è arrivati al 100%.

<details>
<summary>I 167 comuni ARPA senza Open-Meteo, per provincia — ✅ = ormai coperto (in `temperature` o in un file raw pendente: Torino, collaboratrice day1/day3, o il lotto del titolare/IA del 2026-07-20), aggiornato al 2026-07-20 sera. 145/167 ✅, 22 ancora da scaricare (vedi elenco sopra).</summary>

| Provincia | Comune | Codice ISTAT | Scaricato oggi |
|---|---|---|---|
| Alessandria | Acqui Terme | 006001 | ✅ |
| Alessandria | Arquata Scrivia | 006009 | ✅ |
| Alessandria | Basaluzzo | 006012 | ✅ |
| Alessandria | Brignano-Frascata | 006024 | ✅ |
| Alessandria | Cabella Ligure | 006025 | ✅ |
| Alessandria | Casale Monferrato | 006039 | ✅ |
| Alessandria | Casaleggio Boiro | 006038 | ✅ |
| Alessandria | Fabbrica Curone | 006067 | ✅ |
| Alessandria | Garbagna | 006079 | ✅ |
| Alessandria | Gavi | 006081 | ✅ |
| Alessandria | Ovada | 006121 | ✅ |
| Alessandria | Ponzone | 006136 | ✅ |
| Alessandria | Roccaforte Ligure | 006146 | ✅ |
| Alessandria | San Salvatore Monferrato | 006154 | ✅ |
| Alessandria | Sardigliano | 006157 | ✅ |
| Alessandria | Serralunga di Crea | 006159 | ✅ |
| Alessandria | Sezzadio | 006161 | ✅ |
| Alessandria | Vignale Monferrato | 006179 | ✅ |
| Asti | Buttigliera d'Asti | 005012 | ✅ |
| Asti | Castagnole delle Lanze | 005022 | ✅ |
| Asti | Castell'Alfero | 005025 | ✅ |
| Asti | Loazzolo | 005060 | ✅ |
| Asti | Mombaldone | 005064 | ✅ |
| Asti | Montaldo Scarampi | 005074 | ✅ |
| Asti | Montechiaro d'Asti | 005075 | ✅ |
| Asti | Nizza Monferrato | 005080 | ✅ |
| Asti | Roccaverano | 005094 | ✅ |
| Asti | San Damiano d'Asti | 005097 | ✅ |
| Biella | Graglia | 096028 | ✅ |
| Biella | Masserano | 096032 | ✅ |
| Biella | Pettinengo | 096042 | ✅ |
| Biella | Piatto | 096043 | ✅ |
| Biella | Pray | 096050 | ✅ |
| Biella | Salussola | 096058 | ✅ |
| Biella | Valdilana | 096088 | ✅ |
| Cuneo | Alba | 004003 | ✅ |
| Cuneo | Argentera | 004006 | ✅ |
| Cuneo | Baldissero d'Alba | 004010 | ✅ |
| Cuneo | Barge | 004012 | ✅ |
| Cuneo | Bellino | 004017 | ✅ |
| Cuneo | Belvedere Langhe | 004018 | ✅ |
| Cuneo | Boves | 004028 | ✅ |
| Cuneo | Bra | 004029 | ✅ |
| Cuneo | Brossasco | 004033 | ✅ |
| Cuneo | Canosio | 004038 | ✅ |
| Cuneo | Carrù | 004043 | ✅ |
| Cuneo | Castelletto Uzzone | 004050 | ✅ |
| Cuneo | Castellinaldo d'Alba | 004051 | ✅ |
| Cuneo | Ceva | 004066 | ✅ |
| Cuneo | Crissolo | 004077 | ✅ |
| Cuneo | Demonte | 004079 | ✅ |
| Cuneo | Dronero | 004082 | ✅ |
| Cuneo | Elva | 004083 | ✅ |
| Cuneo | Feisoglio | 004088 | ✅ |
| Cuneo | Fossano | 004089 | ✅ |
| Cuneo | Frabosa Soprana | 004090 | ✅ |
| Cuneo | Garessio | 004095 | ✅ |
| Cuneo | Marene | 004117 | ✅ |
| Cuneo | Mombarcaro | 004124 | ✅ |
| Cuneo | Mondovì | 004130 | ✅ |
| Cuneo | Morozzo | 004144 | ✅ |
| Cuneo | Neive | 004148 | ✅ |
| Cuneo | Ormea | 004155 | ✅ |
| Cuneo | Paesana | 004157 | ✅ |
| Cuneo | Pamparato | 004159 | ✅ |
| Cuneo | Paroldo | 004160 | ✅ |
| Cuneo | Perlo | 004162 | ✅ |
| Cuneo | Peveragno | 004163 | ✅ |
| Cuneo | Priero | 004175 | ✅ |
| Cuneo | Prunetto | 004178 | ✅ |
| Cuneo | Roccaforte Mondovì | 004190 | ✅ |
| Cuneo | Roddino | 004195 | ✅ |
| Cuneo | Rodello | 004196 | ✅ |
| Cuneo | Saluzzo | 004203 | ✅ |
| Cuneo | Sampeyre | 004205 | ✅ |
| Cuneo | San Damiano Macra | 004207 | ✅ |
| Cuneo | Somano | 004221 | ✅ |
| Cuneo | Treiso | 004230 | ✅ |
| Cuneo | Valdieri | 004233 | ✅ |
| Cuneo | Vernante | 004239 | ✅ |
| Cuneo | Villanova Solaro | 004246 |  |
| Cuneo | Viola | 004249 |  |
| Novara | Ameno | 003002 | ✅ |
| Novara | Armeno | 003006 | ✅ |
| Novara | Cameri | 003032 | ✅ |
| Novara | Paruzzaro | 003114 | ✅ |
| Novara | Varallo Pombia | 003154 | ✅ |
| Torino | Ala di Stura | 001003 | ✅ |
| Torino | Andrate | 001010 | ✅ |
| Torino | Angrogna | 001011 | ✅ |
| Torino | Avigliana | 001013 | ✅ |
| Torino | Balme | 001019 | ✅ |
| Torino | Borgofranco d'Ivrea | 001030 | ✅ |
| Torino | Borgone Susa | 001032 | ✅ |
| Torino | Brosso | 001036 | ✅ |
| Torino | Caluso | 001047 | ✅ |
| Torino | Candia Canavese | 001050 | ✅ |
| Torino | Carmagnola | 001059 | ✅ |
| Torino | Castagneto Po | 001064 | ✅ |
| Torino | Cesana Torinese | 001074 | ✅ |
| Torino | Chiomonte | 001080 | ✅ |
| Torino | Chivasso | 001082 | ✅ |
| Torino | Coazze | 001089 | ✅ |
| Torino | Colleretto Castelnuovo | 001091 | ✅ |
| Torino | Condove | 001093 | ✅ |
| Torino | Cumiana | 001097 | ✅ |
| Torino | Druento | 001099 | ✅ |
| Torino | Fenestrelle | 001103 | ✅ |
| Torino | Front | 001109 | ✅ |
| Torino | Giaglione | 001114 | ✅ |
| Torino | Groscavallo | 001118 | ✅ |
| Torino | Lanzo Torinese | 001128 | ✅ |
| Torino | Luserna San Giovanni | 001139 | ✅ |
| Torino | Monastero di Lanzo | 001155 |  |
| Torino | Moncalieri | 001156 | ✅ |
| Torino | Oulx | 001175 | ✅ |
| Torino | Parella | 001179 |  |
| Torino | Perrero | 001186 |  |
| Torino | Pinerolo | 001191 |  |
| Torino | Pragelato | 001201 |  |
| Torino | Prali | 001202 | ✅ |
| Torino | Rivoli | 001219 |  |
| Torino | Ronco Canavese | 001224 |  |
| Torino | Sauze d'Oulx | 001259 |  |
| Torino | Sestriere | 001263 |  |
| Torino | Susa | 001270 |  |
| Torino | Trana | 001276 |  |
| Torino | Traversella | 001278 |  |
| Torino | Valchiusa | 001318 |  |
| Torino | Varisella | 001289 |  |
| Torino | Venaria Reale | 001292 |  |
| Torino | Venaus | 001291 |  |
| Torino | Verolengo | 001293 |  |
| Torino | Vialfrè | 001296 |  |
| Torino | Villafranca Piemonte | 001300 |  |
| Torino | Viù | 001313 | ✅ |
| Verbano-Cusio-Ossola | Antrona Schieranco | 103001 | ✅ |
| Verbano-Cusio-Ossola | Baceno | 103006 | ✅ |
| Verbano-Cusio-Ossola | Bannio Anzino | 103007 | ✅ |
| Verbano-Cusio-Ossola | Bognanco | 103012 | ✅ |
| Verbano-Cusio-Ossola | Cannobio | 103017 | ✅ |
| Verbano-Cusio-Ossola | Ceppo Morelli | 103021 | ✅ |
| Verbano-Cusio-Ossola | Cesara | 103022 | ✅ |
| Verbano-Cusio-Ossola | Cossogno | 103023 | ✅ |
| Verbano-Cusio-Ossola | Crodo | 103026 | ✅ |
| Verbano-Cusio-Ossola | Domodossola | 103028 | ✅ |
| Verbano-Cusio-Ossola | Druogno | 103029 | ✅ |
| Verbano-Cusio-Ossola | Mergozzo | 103044 | ✅ |
| Verbano-Cusio-Ossola | Montecrestese | 103046 | ✅ |
| Verbano-Cusio-Ossola | Omegna | 103050 | ✅ |
| Verbano-Cusio-Ossola | Pieve Vergonte | 103054 | ✅ |
| Verbano-Cusio-Ossola | Premia | 103056 | ✅ |
| Verbano-Cusio-Ossola | Stresa | 103064 | ✅ |
| Verbano-Cusio-Ossola | Toceno | 103065 | ✅ |
| Verbano-Cusio-Ossola | Trasquera | 103067 | ✅ |
| Verbano-Cusio-Ossola | Trontano | 103068 | ✅ |
| Verbano-Cusio-Ossola | Valle Cannobina | 103079 | ✅ |
| Verbano-Cusio-Ossola | Varzo | 103071 |  |
| Vercelli | Albano Vercellese | 002003 | ✅ |
| Vercelli | Alto Sermenza | 002170 | ✅ |
| Vercelli | Boccioleto | 002014 | ✅ |
| Vercelli | Carcoforo | 002029 | ✅ |
| Vercelli | Cellio con Breia | 002171 | ✅ |
| Vercelli | Lozzolo | 002072 | ✅ |
| Vercelli | Rassa | 002110 | ✅ |
| Vercelli | Tricerro | 002147 | ✅ |
| Vercelli | Varallo | 002156 | ✅ |

</details>

**Per la prossima sessione**: aspettare il reset della quota (il giorno
dopo, non lo stesso giorno) e scaricare storico completo 2000→oggi per i
158 comuni sopra non ancora marcati ✅ (usando lo stesso approccio di
`download_extra_municipalities.py`, ma filtrando esplicitamente su questa
lista invece che su un campionamento spaziale generico — qui serve
**tutta** la lista, non un sottoinsieme rappresentativo). Dato il limite
osservato oggi (~18-20 comuni a storico completo prima del blocco), serviranno
**8-9 sessioni giornaliere** per completarla tutta, salvo che la quota si
riveli più permissiva in altri giorni. **Attenzione a non sovrapporsi con
il file che arriverà dalla collega** (vedi sezione sotto): se anche lei
sta scaricando comuni extra in questi giorni, controllare i nomi prima di
importare per evitare doppioni.

## Comuni già coperti (NON riscaricare questi)


### Alessandria (158/187 comuni coperti)

| Comune | Codice ISTAT |
|---|---|
| Acqui Terme | 006001 |
| Albera Ligure | 006002 |
| Alessandria | 006003 |
| Alfiano Natta | 006004 |
| Alice Bel Colle | 006005 |
| Alluvioni Piovera | 006192 |
| Altavilla Monferrato | 006007 |
| Arquata Scrivia | 006009 |
| Avolasca | 006010 |
| Balzola | 006011 |
| Basaluzzo | 006012 |
| Bassignana | 006013 |
| Bergamasco | 006015 |
| Bistagno | 006017 |
| Borghetto di Borbera | 006018 |
| Borgo San Martino | 006020 |
| Borgoratto Alessandrino | 006019 |
| Bosco Marengo | 006021 |
| Bosio | 006022 |
| Bozzole | 006023 |
| Brignano-Frascata | 006024 |
| Cabella Ligure | 006025 |
| Camagna Monferrato | 006026 |
| Camino | 006027 |
| Cantalupo Ligure | 006028 |
| Capriata d'Orba | 006029 |
| Carentino | 006031 |
| Carpeneto | 006033 |
| Carrega Ligure | 006034 |
| Carrosio | 006035 |
| Cartosio | 006036 |
| Casal Cermelli | 006037 |
| Casale Monferrato | 006039 |
| Casaleggio Boiro | 006038 |
| Casalnoceto | 006040 |
| Casasco | 006041 |
| Cassano Spinola | 006191 |
| Cassine | 006043 |
| Cassinelle | 006044 |
| Castellazzo Bormida | 006047 |
| Castelletto d'Erro | 006048 |
| Castelletto d'Orba | 006049 |
| Castelletto Merli | 006050 |
| Castelletto Monferrato | 006051 |
| Castelnuovo Bormida | 006052 |
| Castelnuovo Scrivia | 006053 |
| Castelspina | 006054 |
| Cavatore | 006055 |
| Cella Monte | 006056 |
| Cereseto | 006057 |
| Cerrina Monferrato | 006059 |
| Coniolo | 006060 |
| Conzano | 006061 |
| Costa Vescovato | 006062 |
| Cremolino | 006063 |
| Denice | 006065 |
| Dernice | 006066 |
| Fabbrica Curone | 006067 |
| Felizzano | 006068 |
| Fraconalto | 006069 |
| Francavilla Bisio | 006070 |
| Frassineto Po | 006073 |
| Frugarolo | 006075 |
| Fubine Monferrato | 006076 |
| Gabiano | 006077 |
| Gamalero | 006078 |
| Garbagna | 006079 |
| Gavi | 006081 |
| Giarole | 006082 |
| Gremiasco | 006083 |
| Grognardo | 006084 |
| Grondona | 006085 |
| Isola Sant'Antonio | 006087 |
| Lu e Cuccaro Monferrato | 006193 |
| Malvicino | 006090 |
| Masio | 006091 |
| Melazzo | 006092 |
| Merana | 006093 |
| Mirabello Monferrato | 006094 |
| Molare | 006095 |
| Molino dei Torti | 006096 |
| Mombello Monferrato | 006097 |
| Momperone | 006098 |
| Moncestino | 006099 |
| Mongiardino Ligure | 006100 |
| Monleale | 006101 |
| Montacuto | 006102 |
| Montaldeo | 006103 |
| Montecastello | 006105 |
| Montechiaro d'Acqui | 006106 |
| Montegioco | 006107 |
| Montemarzino | 006108 |
| Morano sul Po | 006109 |
| Morbello | 006110 |
| Morsasco | 006112 |
| Murisengo Monferrato | 006113 |
| Novi Ligure | 006114 |
| Occimiano | 006115 |
| Odalengo Grande | 006116 |
| Odalengo Piccolo | 006117 |
| Olivola | 006118 |
| Ovada | 006121 |
| Oviglio | 006122 |
| Ozzano Monferrato | 006123 |
| Pareto | 006125 |
| Parodi Ligure | 006126 |
| Pecetto di Valenza | 006128 |
| Pontecurone | 006132 |
| Pontestura | 006133 |
| Ponti | 006134 |
| Ponzone | 006136 |
| Pozzol Groppo | 006137 |
| Pozzolo Formigaro | 006138 |
| Predosa | 006140 |
| Quargnento | 006141 |
| Quattordio | 006142 |
| Rivalta Bormida | 006144 |
| Rivarone | 006145 |
| Rocca Grimalda | 006147 |
| Roccaforte Ligure | 006146 |
| Rocchetta Ligure | 006148 |
| Rosignano Monferrato | 006149 |
| Sala Monferrato | 006150 |
| Sale | 006151 |
| San Giorgio Monferrato | 006153 |
| San Salvatore Monferrato | 006154 |
| San Sebastiano Curone | 006155 |
| Sant'Agata Fossili | 006156 |
| Sardigliano | 006157 |
| Sarezzano | 006158 |
| Serralunga di Crea | 006159 |
| Serravalle Scrivia | 006160 |
| Sezzadio | 006161 |
| Silvano d'Orba | 006162 |
| Solero | 006163 |
| Solonghello | 006164 |
| Spigno Monferrato | 006165 |
| Spineto Scrivia | 006166 |
| Stazzano | 006167 |
| Strevi | 006168 |
| Tagliolo Monferrato | 006169 |
| Tassarolo | 006170 |
| Terruggia | 006171 |
| Terzo | 006172 |
| Ticineto | 006173 |
| Tortona | 006174 |
| Valenza | 006177 |
| Valmacca | 006178 |
| Vignale Monferrato | 006179 |
| Vignole Borbera | 006180 |
| Viguzzolo | 006181 |
| Villadeati | 006182 |
| Villalvernia | 006183 |
| Villanova Monferrato | 006185 |
| Visone | 006187 |
| Volpedo | 006188 |
| Volpeglino | 006189 |
| Voltaggio | 006190 |

### Asti (67/117 comuni coperti)

| Comune | Codice ISTAT |
|---|---|
| Albugnano | 005002 |
| Asti | 005005 |
| Azzano d'Asti | 005006 |
| Baldichieri d'Asti | 005007 |
| Bubbio | 005011 |
| Buttigliera d'Asti | 005012 |
| Calamandrana | 005013 |
| Calliano Monferrato | 005014 |
| Calosso | 005015 |
| Camerano Casasco | 005016 |
| Canelli | 005017 |
| Capriglio | 005019 |
| Casorzo Monferrato | 005020 |
| Castagnole delle Lanze | 005022 |
| Castel Boglione | 005024 |
| Castel Rocchero | 005032 |
| Castell'Alfero | 005025 |
| Castello di Annone | 005028 |
| Castelnuovo Belbo | 005029 |
| Castelnuovo Don Bosco | 005031 |
| Cellarengo | 005033 |
| Cerreto d'Asti | 005035 |
| Cerro Tanaro | 005036 |
| Cessole | 005037 |
| Cisterna d'Asti | 005040 |
| Coazzolo | 005041 |
| Cocconato | 005042 |
| Cortazzone | 005047 |
| Cortiglione | 005048 |
| Costigliole d'Asti | 005050 |
| Dusino San Michele | 005052 |
| Ferrere | 005053 |
| Grana Monferrato | 005056 |
| Loazzolo | 005060 |
| Maranzana | 005061 |
| Mombaldone | 005064 |
| Mombaruzzo | 005065 |
| Moncalvo | 005069 |
| Moncucco Torinese | 005070 |
| Mongardino | 005071 |
| Montaldo Scarampi | 005074 |
| Montechiaro d'Asti | 005075 |
| Montegrosso d'Asti | 005076 |
| Montemagno Monferrato | 005077 |
| Montiglio Monferrato | 005121 |
| Moransengo-Tonengo | 005122 |
| Nizza Monferrato | 005080 |
| Piea | 005084 |
| Refrancore | 005089 |
| Revigliasco d'Asti | 005090 |
| Roatto | 005091 |
| Robella | 005092 |
| Roccaverano | 005094 |
| San Damiano d'Asti | 005097 |
| San Giorgio Scarampi | 005098 |
| San Martino Alfieri | 005099 |
| San Marzano Oliveto | 005100 |
| Scurzolengo | 005103 |
| Serole | 005104 |
| Sessame | 005105 |
| Settime | 005106 |
| Tonco | 005109 |
| Viarigi | 005115 |
| Villa San Secondo | 005119 |
| Villafranca d'Asti | 005117 |
| Villanova d'Asti | 005118 |
| Vinchio | 005120 |

### Biella (45/74 comuni coperti)

| Comune | Codice ISTAT |
|---|---|
| Ailoche | 096001 |
| Benna | 096003 |
| Biella | 096004 |
| Borriana | 096006 |
| Camandona | 096009 |
| Camburzano | 096010 |
| Campiglia Cervo | 096086 |
| Candelo | 096012 |
| Caprile | 096013 |
| Cavaglià | 096016 |
| Cerrione | 096018 |
| Cossato | 096020 |
| Curino | 096023 |
| Donato | 096024 |
| Gifflenga | 096027 |
| Graglia | 096028 |
| Lessona | 096085 |
| Magnano | 096030 |
| Massazza | 096031 |
| Masserano | 096032 |
| Mezzana Mortigliengo | 096033 |
| Miagliano | 096034 |
| Mottalciata | 096037 |
| Occhieppo Superiore | 096041 |
| Pettinengo | 096042 |
| Piatto | 096043 |
| Piedicavallo | 096044 |
| Pollone | 096046 |
| Ponderano | 096047 |
| Portula | 096048 |
| Pray | 096050 |
| Quaregna Cerreto | 096087 |
| Roppolo | 096054 |
| Salussola | 096058 |
| Sandigliano | 096059 |
| Sostegno | 096064 |
| Tavigliano | 096066 |
| Torrazzo | 096069 |
| Valdengo | 096071 |
| Valdilana | 096088 |
| Villa del Bosco | 096078 |
| Villanova Biellese | 096079 |
| Viverone | 096080 |
| Zimone | 096081 |
| Zumaglia | 096083 |

### Cuneo (131/247 comuni coperti)

| Comune | Codice ISTAT |
|---|---|
| Acceglio | 004001 |
| Aisone | 004002 |
| Alba | 004003 |
| Alto | 004005 |
| Argentera | 004006 |
| Bagnasco | 004008 |
| Bagnolo Piemonte | 004009 |
| Baldissero d'Alba | 004010 |
| Barge | 004012 |
| Barolo | 004013 |
| Bastia Mondovì | 004014 |
| Beinette | 004016 |
| Bellino | 004017 |
| Belvedere Langhe | 004018 |
| Bene Vagienna | 004019 |
| Bergolo | 004021 |
| Boves | 004028 |
| Bra | 004029 |
| Briga Alta | 004031 |
| Brossasco | 004033 |
| Canosio | 004038 |
| Caraglio | 004040 |
| Cardè | 004042 |
| Carrù | 004043 |
| Casalgrasso | 004045 |
| Castelletto Stura | 004049 |
| Castelletto Uzzone | 004050 |
| Castellinaldo d'Alba | 004051 |
| Castelmagno | 004053 |
| Castino | 004057 |
| Cavallermaggiore | 004059 |
| Celle di Macra | 004060 |
| Centallo | 004061 |
| Ceresole Alba | 004062 |
| Ceva | 004066 |
| Cherasco | 004067 |
| Chiusa di Pesio | 004068 |
| Corneliano d'Alba | 004072 |
| Costigliole Saluzzo | 004075 |
| Cravanzana | 004076 |
| Crissolo | 004077 |
| Cuneo | 004078 |
| Demonte | 004079 |
| Dronero | 004082 |
| Elva | 004083 |
| Entracque | 004084 |
| Farigliano | 004086 |
| Faule | 004087 |
| Feisoglio | 004088 |
| Fossano | 004089 |
| Frabosa Soprana | 004090 |
| Frassino | 004092 |
| Gaiola | 004093 |
| Garessio | 004095 |
| Genola | 004096 |
| Govone | 004099 |
| Grinzane Cavour | 004100 |
| Lagnasco | 004104 |
| Limone Piemonte | 004110 |
| Mango | 004115 |
| Manta | 004116 |
| Marene | 004117 |
| Marmora | 004119 |
| Mombarcaro | 004124 |
| Mombasiglio | 004125 |
| Monastero di Vasco | 004126 |
| Monasterolo di Savigliano | 004128 |
| Monchiero | 004129 |
| Mondovì | 004130 |
| Montà | 004133 |
| Monterosso Grana | 004139 |
| Morozzo | 004144 |
| Murello | 004146 |
| Narzole | 004147 |
| Neive | 004148 |
| Oncino | 004154 |
| Ormea | 004155 |
| Ostana | 004156 |
| Paesana | 004157 |
| Pagno | 004158 |
| Pamparato | 004159 |
| Paroldo | 004160 |
| Perletto | 004161 |
| Perlo | 004162 |
| Peveragno | 004163 |
| Pianfei | 004165 |
| Pietraporzio | 004167 |
| Pontechianale | 004172 |
| Prazzo | 004174 |
| Priero | 004175 |
| Prunetto | 004178 |
| Racconigi | 004179 |
| Revello | 004180 |
| Rifreddo | 004181 |
| Roaschia | 004183 |
| Robilante | 004185 |
| Roburent | 004186 |
| Rocca de' Baldi | 004189 |
| Roccabruna | 004187 |
| Roccaforte Mondovì | 004190 |
| Roddino | 004195 |
| Rodello | 004196 |
| Rossana | 004197 |
| Saliceto | 004201 |
| Salmour | 004202 |
| Saluzzo | 004203 |
| Sambuco | 004204 |
| Sampeyre | 004205 |
| San Damiano Macra | 004207 |
| Sanfront | 004209 |
| Santo Stefano Belbo | 004213 |
| Somano | 004221 |
| Sommariva del Bosco | 004222 |
| Stroppo | 004224 |
| Tarantasca | 004225 |
| Torre Mondovì | 004227 |
| Torre San Giorgio | 004228 |
| Torresina | 004229 |
| Treiso | 004230 |
| Trinità | 004232 |
| Valdieri | 004233 |
| Valgrana | 004234 |
| Valloriate | 004235 |
| Verduno | 004238 |
| Vernante | 004239 |
| Vicoforte | 004242 |
| Vignolo | 004243 |
| Villanova Solaro | 004246 |
| Vinadio | 004248 |
| Viola | 004249 |
| Vottignasco | 004250 |

### Novara (54/87 comuni coperti)

| Comune | Codice ISTAT |
|---|---|
| Agrate Conturbia | 003001 |
| Ameno | 003002 |
| Armeno | 003006 |
| Bellinzago Novarese | 003016 |
| Bogogno | 003021 |
| Borgolavezzaro | 003023 |
| Borgomanero | 003024 |
| Briga Novarese | 003026 |
| Briona | 003027 |
| Caltignaga | 003030 |
| Cameri | 003032 |
| Casalbeltrame | 003037 |
| Casaleggio Novara | 003039 |
| Casalino | 003040 |
| Castelletto sopra Ticino | 003043 |
| Cavaglietto | 003044 |
| Cavallirio | 003047 |
| Cerano | 003049 |
| Colazza | 003051 |
| Comignago | 003052 |
| Fara Novarese | 003065 |
| Fontaneto d'Agogna | 003066 |
| Galliate | 003068 |
| Garbagna Novarese | 003069 |
| Gargallo | 003070 |
| Gattico-Veruno | 003166 |
| Ghemme | 003073 |
| Granozzo con Monticello | 003077 |
| Grignasco | 003079 |
| Lesa | 003084 |
| Meina | 003095 |
| Mezzomerico | 003097 |
| Momo | 003100 |
| Novara | 003106 |
| Oleggio | 003108 |
| Orta San Giulio | 003112 |
| Paruzzaro | 003114 |
| Pettenasco | 003116 |
| Pogno | 003120 |
| Prato Sesia | 003122 |
| Recetto | 003129 |
| Romentino | 003131 |
| San Nazzaro Sesia | 003134 |
| San Pietro Mosezzo | 003135 |
| Sillavengo | 003138 |
| Sozzago | 003141 |
| Suno | 003143 |
| Terdobbiate | 003144 |
| Tornaco | 003146 |
| Trecate | 003149 |
| Varallo Pombia | 003154 |
| Vespolate | 003158 |
| Vicolungo | 003159 |
| Vinzaglio | 003164 |

### Torino (149/312 comuni coperti)

| Comune | Codice ISTAT |
|---|---|
| Agliè | 001001 |
| Ala di Stura | 001003 |
| Andrate | 001010 |
| Angrogna | 001011 |
| Avigliana | 001013 |
| Balme | 001019 |
| Bardonecchia | 001022 |
| Barone Canavese | 001023 |
| Bobbio Pellice | 001026 |
| Borgofranco d'Ivrea | 001030 |
| Borgone Susa | 001032 |
| Bosconero | 001033 |
| Brandizzo | 001034 |
| Brosso | 001036 |
| Bruino | 001038 |
| Burolo | 001042 |
| Caluso | 001047 |
| Campiglione Fenile | 001049 |
| Candia Canavese | 001050 |
| Candiolo | 001051 |
| Canischio | 001052 |
| Carema | 001057 |
| Carignano | 001058 |
| Carmagnola | 001059 |
| Casalborgone | 001060 |
| Caselle Torinese | 001063 |
| Castagneto Po | 001064 |
| Castagnole Piemonte | 001065 |
| Castellamonte | 001066 |
| Castelnuovo Nigra | 001067 |
| Castiglione Torinese | 001068 |
| Cavagnolo | 001069 |
| Cavour | 001070 |
| Ceres | 001072 |
| Ceresole Reale | 001073 |
| Cesana Torinese | 001074 |
| Chialamberto | 001075 |
| Chianocco | 001076 |
| Chieri | 001078 |
| Chiomonte | 001080 |
| Chiusa di San Michele | 001081 |
| Chivasso | 001082 |
| Ciriè | 001086 |
| Claviere | 001087 |
| Coassolo Torinese | 001088 |
| Coazze | 001089 |
| Colleretto Castelnuovo | 001091 |
| Condove | 001093 |
| Corio | 001094 |
| Cumiana | 001097 |
| Cuorgnè | 001098 |
| Druento | 001099 |
| Favria | 001101 |
| Fenestrelle | 001103 |
| Fiano | 001104 |
| Foglizzo | 001106 |
| Front | 001109 |
| Giaglione | 001114 |
| Giaveno | 001115 |
| Gravere | 001117 |
| Groscavallo | 001118 |
| Grugliasco | 001120 |
| Ingria | 001121 |
| Isolabella | 001123 |
| Lanzo Torinese | 001128 |
| Leini | 001130 |
| Lemie | 001131 |
| Locana | 001134 |
| Lombriasco | 001136 |
| Luserna San Giovanni | 001139 |
| Macello | 001142 |
| Maglione | 001143 |
| Marentino | 001144 |
| Massello | 001145 |
| Mathi | 001146 |
| Mattie | 001147 |
| Mompantero | 001154 |
| Monastero di Lanzo | 001155 |
| Moncalieri | 001156 |
| Moncenisio | 001157 |
| Moriondo Torinese | 001163 |
| Nichelino | 001164 |
| Noasca | 001165 |
| Oulx | 001175 |
| Pancalieri | 001178 |
| Parella | 001179 |
| Perrero | 001186 |
| Pianezza | 001189 |
| Pinasca | 001190 |
| Pinerolo | 001191 |
| Pino Torinese | 001192 |
| Piscina | 001195 |
| Piverone | 001196 |
| Poirino | 001197 |
| Pomaretto | 001198 |
| Pragelato | 001201 |
| Prali | 001202 |
| Pralormo | 001203 |
| Prarostino | 001205 |
| Quincinetto | 001210 |
| Ribordone | 001212 |
| Riva presso Chieri | 001215 |
| Rivara | 001216 |
| Rivoli | 001219 |
| Rocca Canavese | 001221 |
| Roletto | 001222 |
| Ronco Canavese | 001224 |
| Rorà | 001226 |
| Rosta | 001228 |
| Roure | 001227 |
| Rubiana | 001229 |
| Salbertrand | 001232 |
| Samone | 001235 |
| San Giorgio Canavese | 001244 |
| San Giorio di Susa | 001245 |
| Santena | 001257 |
| Sauze d'Oulx | 001259 |
| Sauze di Cesana | 001258 |
| Scalenghe | 001260 |
| Scarmagno | 001261 |
| Sestriere | 001263 |
| Sparone | 001267 |
| Susa | 001270 |
| Torino | 001272 |
| Torrazza Piemonte | 001273 |
| Trana | 001276 |
| Traversella | 001278 |
| Traves | 001279 |
| Usseaux | 001281 |
| Usseglio | 001282 |
| Val della Torre | 001284 |
| Valchiusa | 001318 |
| Valprato Soana | 001288 |
| Varisella | 001289 |
| Venaria Reale | 001292 |
| Venaus | 001291 |
| Verolengo | 001293 |
| Verrua Savoia | 001294 |
| Vestignè | 001295 |
| Vialfrè | 001296 |
| Vigone | 001299 |
| Villafranca Piemonte | 001300 |
| Villar Pellice | 001306 |
| Villareggia | 001304 |
| Villastellone | 001308 |
| Vistrorio | 001312 |
| Viù | 001313 |
| Volpiano | 001314 |
| Volvera | 001315 |

### Verbano-Cusio-Ossola (55/74 comuni coperti)

| Comune | Codice ISTAT |
|---|---|
| Antrona Schieranco | 103001 |
| Anzola d'Ossola | 103002 |
| Baceno | 103006 |
| Bannio Anzino | 103007 |
| Baveno | 103008 |
| Bee | 103009 |
| Belgirate | 103010 |
| Beura-Cardezza | 103011 |
| Bognanco | 103012 |
| Borgomezzavalle | 103078 |
| Brovello-Carpugnino | 103013 |
| Calasca-Castiglione | 103014 |
| Cannero Riviera | 103016 |
| Cannobio | 103017 |
| Ceppo Morelli | 103021 |
| Cesara | 103022 |
| Cossogno | 103023 |
| Craveggia | 103024 |
| Crevoladossola | 103025 |
| Crodo | 103026 |
| Domodossola | 103028 |
| Druogno | 103029 |
| Formazza | 103031 |
| Ghiffa | 103033 |
| Gravellona Toce | 103035 |
| Intragna | 103037 |
| Loreglia | 103038 |
| Macugnaga | 103039 |
| Madonna del Sasso | 103040 |
| Malesco | 103041 |
| Masera | 103042 |
| Mergozzo | 103044 |
| Miazzina | 103045 |
| Montecrestese | 103046 |
| Oggebbio | 103049 |
| Omegna | 103050 |
| Ornavasso | 103051 |
| Piedimulera | 103053 |
| Pieve Vergonte | 103054 |
| Premia | 103056 |
| Premosello-Chiovenda | 103057 |
| Quarna Sotto | 103059 |
| Re | 103060 |
| Stresa | 103064 |
| Toceno | 103065 |
| Trarego Viggiona | 103066 |
| Trasquera | 103067 |
| Trontano | 103068 |
| Valle Cannobina | 103079 |
| Valstrona | 103069 |
| Vanzone con San Carlo | 103070 |
| Varzo | 103071 |
| Verbania | 103072 |
| Villadossola | 103075 |
| Vogogna | 103077 |

### Vercelli (52/82 comuni coperti)

| Comune | Codice ISTAT |
|---|---|
| Alagna Valsesia | 002002 |
| Albano Vercellese | 002003 |
| Alice Castello | 002004 |
| Alto Sermenza | 002170 |
| Asigliano Vercellese | 002007 |
| Bianzè | 002011 |
| Boccioleto | 002014 |
| Borgo Vercelli | 002017 |
| Borgosesia | 002016 |
| Buronzo | 002021 |
| Carcoforo | 002029 |
| Carisio | 002032 |
| Casanova Elvo | 002033 |
| Cellio con Breia | 002171 |
| Cervatto | 002041 |
| Civiasco | 002043 |
| Costanzana | 002047 |
| Cravagliana | 002048 |
| Crescentino | 002049 |
| Crova | 002052 |
| Fontanetto Po | 002058 |
| Ghislarengo | 002062 |
| Livorno Ferraris | 002071 |
| Lozzolo | 002072 |
| Mollia | 002078 |
| Moncrivello | 002079 |
| Motta de' Conti | 002082 |
| Palazzolo Vercellese | 002090 |
| Piode | 002097 |
| Postua | 002102 |
| Prarolo | 002104 |
| Quinto Vercellese | 002108 |
| Rassa | 002110 |
| Rimella | 002113 |
| Rive | 002115 |
| Ronsecco | 002118 |
| Rovasenda | 002122 |
| Sali Vercellese | 002127 |
| Saluggia | 002128 |
| San Giacomo Vercellese | 002035 |
| Scopello | 002135 |
| Serravalle Sesia | 002137 |
| Stroppiana | 002142 |
| Tricerro | 002147 |
| Trino | 002148 |
| Tronzano Vercellese | 002150 |
| Valduggia | 002152 |
| Varallo | 002156 |
| Vercelli | 002158 |
| Villarboit | 002163 |
| Villata | 002164 |
| Vocca | 002166 |

## Comuni prioritari per l'aggiornamento giornaliero (copertura ARPA)

**A cosa serve questa sezione**: dei 177 comuni coperti, **51 hanno anche
una stazione ARPA attiva** con sensore di temperatura (vedi [Fonti
Dati](data-sources.md#arpa-piemonte--integrata-e-scaricata-2026-07-18)) e
sono quindi gli unici utilizzabili per il confronto/validazione
Open-Meteo↔ARPA (bias, trend, eventi — vedi [Analisi
statistica](statistical-analysis.md#validazione-contro-arpa-piemonte-2026-07-18)).
Dal 2026-07-19 `update_recent_data.py` (funzione
`load_municipalities_with_data()`) li scarica **per primi** (query ordinata
`has_arpa DESC, nome`), perché la quota giornaliera Open-Meteo è
imprevedibile (vedi sotto) e un run interrotto a metà deve comunque aver
già garantito il delta utile al confronto, prima del resto dei comuni in
ordine alfabetico.

Se una sessione di aggiornamento si interrompe prima di coprire tutti i
177 comuni, **controllare per primi questi 51** (via log o query su
`temperature` per la data massima per comune) prima di considerare il
delta del giorno completo.

| Comune | Codice ISTAT | Esito delta 2026-07-19 |
|---|---|---|---|
| Acceglio | 004001 | ✅ |
| Alagna Valsesia | 002002 | ✅ |
| Alessandria | 006003 | ✅ |
| Asti | 005005 | ✅ |
| Bardonecchia | 001022 | ✅ |
| Biella | 096004 | ✅ |
| Bobbio Pellice | 001026 | ✅ |
| Borgomanero | 003024 | ✅ |
| Bosio | 006022 | ✅ |
| Briga Alta | 004031 | ✅ |
| Carrega Ligure | 006034 | ✅ |
| Caselle Torinese | 001063 | ✅ |
| Castelmagno | 004053 | ✅ |
| Cerano | 003049 | ✅ |
| Ceresole Reale | 001073 | ✅ |
| Chiusa di Pesio | 004068 | ✅ |
| Costigliole Saluzzo | 004075 | ✅ |
| Cuneo | 004078 | ✅ |
| Entracque | 004084 | ✅ |
| Formazza | 103031 | ✅ |
| Govone | 004099 | ✅ |
| Isola Sant'Antonio | 006087 | ✅ |
| Lemie | 001131 | ✅ |
| Limone Piemonte | 004110 | ✅ |
| Locana | 001134 | ✅ |
| Macugnaga | 103039 | ✅ |
| Marentino | 001144 | ✅ (riuscito al retry) |
| Massello | 001145 | ✅ |
| Momo | 003100 | ✅ |
| Monterosso Grana | 004139 | ✅ |
| Noasca | 001165 | ✅ |
| Novara | 003106 | ✅ |
| Novi Ligure | 006114 | ✅ |
| Piedicavallo | 096044 | ✅ |
| Pino Torinese | 001192 | ✅ |
| Piverone | 001196 | ✅ |
| Pontechianale | 004172 | ✅ |
| Pralormo | 001203 | ✅ |
| Salbertrand | 001232 | ✅ |
| Saliceto | 004201 | ✅ |
| Santena | 001257 | ✅ |
| Sauze di Cesana | 001258 | ✅ |
| Serole | 005104 | ✅ |
| Sparone | 001267 | ✅ |
| Torino | 001272 | ✅ |
| Tortona | 006174 | ✅ |
| Usseglio | 001282 | ✅ (riuscito al retry) |
| Valprato Soana | 001288 | ✅ |
| Verbania | 103072 | ✅ |
| Vercelli | 002158 | ✅ |
| Vinadio | 004248 | ✅ |

## Come scaricare nuovi comuni (Open-Meteo, storico 2000 → oggi)

**Fonte**: Open-Meteo Archive API (`https://archive-api.open-meteo.com/v1/archive`),
nessuna chiave richiesta. **Limite scoperto sul campo**: oltre al rate
limit "al minuto", esiste un **limite giornaliero**, ma la sua entità
esatta resta poco chiara — **variabile da un giorno all'altro**, non un
numero fisso: la prima volta (2026-07-17) ci si è bloccati dopo ~19-20
comuni, mentre il 2026-07-18 una sessione ne ha ottenuti 57 e un'altra,
in parallelo sullo stesso giorno, solo 22 prima di bloccarsi. Ipotesi non
confermata: la quota potrebbe essere legata al volume di dati scaricato
più che a un conteggio piatto di richieste (coerente con un'osservazione
simile del 2026-07-17, vedi [Fonti Dati](data-sources.md)). Consiglio
pratico: scaricare **a lotti piccoli** (10-20 comuni), fermarsi appena
arriva un errore `429`/messaggio di quota esaurita **o appena i download
smettono di progredire per diversi minuti senza errori espliciti**
(osservato il 2026-07-18: il processo può restare "vivo" ma bloccato nei
retry senza produrre output visibile), e riprendere il giorno dopo — non
serve a niente insistere, la quota si resetta il giorno successivo.

**Quali comuni scegliere**: qualunque comune **non presente** nelle
tabelle sopra. Non serve seguire un criterio particolare — anche una
scelta libera va bene, purché non scarichi due volte lo stesso comune
(anche per errore: il progetto non ha un vincolo di unicità su
`(comune, data)`, un doppio import duplicherebbe silenziosamente le
righe). Se si vuole essere sistematici, si può prendere un comune a
testa per provincia diversa, per continuare a distribuire la copertura
sul territorio invece di concentrarla in una sola zona.

### Formato del file da consegnare

Un CSV con **queste colonne esatte** (stesso ordine non obbligatorio, ma
nomi e contenuto sì):

| Colonna | Contenuto | Note |
|---|---|---|---|
| `date` | data (`YYYY-MM-DD`) | |
| `temp_max` | temperatura massima giornaliera (°C) | |
| `temp_min` | temperatura minima giornaliera (°C) | |
| `temp_mean` | temperatura media giornaliera (°C) | |
| `precipitation` | precipitazione giornaliera (mm) | |
| `province` | **nome del comune** (non della provincia!) | es. `Ceva`, non `Cuneo` |
| `data_source` | `OpenMeteo` | fisso, per tutte le righe |
| `istat_code` | codice ISTAT del comune, **6 cifre** | **fondamentale**: salvarlo come testo/stringa, non come numero — un foglio di calcolo o uno script che lo legge come numero perde gli zeri iniziali (es. `006005` diventa `6005`), rendendo il comune impossibile da abbinare correttamente al database. Se usi Excel: formatta la colonna come "Testo" prima di incollare i codici. Se usi pandas: `pd.read_csv(..., dtype={'istat_code': str})` e mai convertirla in `int`. |
| `province_name` | nome della provincia (es. `Cuneo`) | |

Il codice ISTAT del comune si trova cercando il comune su
`https://www.istat.it` o in qualunque elenco ufficiale dei comuni
italiani — è lo stesso codice usato ovunque nel progetto per collegare
le righe di temperatura al comune giusto nel database.

**Dove consegnare il file**: fuori da Git (i dati grezzi non sono
tracciati nel repository per dimensione, vedi `.gitignore`) — stesso
canale già usato in precedenza (email/drive), non `git push`.

## Nota per chi importa (di solito il titolare o l'IA)

Il file consegnato non ha ancora `municipality_id` (chi scarica da una
macchina senza accesso al DB non può risolverlo). Prima di caricarlo in
`temperature` serve:
1. Pulizia con `DataCleaner.clean_data()` (`src/data_processing/clean_data.py`)
2. Join `istat_code` → `municipality_id` contro la tabella `municipalities`
   (già `UNIQUE` su `istat_code`)
3. Caricamento con `DatabaseLoader.insert_temperature_for_municipalities()`
4. Ricalcolo a valle: `TRUNCATE heatwave_events` + `identify_heatwaves()`,
   `REFRESH MATERIALIZED VIEW` su entrambe le viste KPI, tutti i moduli di
   `src/analysis/`, mappe QGIS

Vedi [Pipeline ETL](etl-pipeline.md#import-dei-35-comuni-extra-dalla-seconda-macchina-2026-07-17)
per un esempio completo di questo stesso identico flusso, eseguito il
2026-07-17 sui 35 comuni della sessione precedente — stessi passi,
stessi bug da evitare (istat_code letto come stringa, non intero).

**Dopo l'import, ricordarsi di aggiornare questa pagina** con i nuovi
comuni coperti, altrimenti il prossimo giro di download rischia di
sovrapporsi.
