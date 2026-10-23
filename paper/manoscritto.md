# [Titolo di lavoro] Pattern spazio-temporali delle ondate di calore in Piemonte (2000-2025): ruolo della quota e dell'uso del suolo

*Working title in inglese (per la sottomissione finale): "Spatiotemporal patterns
of heatwaves in Piedmont, Italy (2000-2025): the role of elevation and land
cover"*

**Stato di questo documento**: bozza scheletro, in italiano per facilitare la
scrittura collaborativa. Andrà tradotto in inglese prima di qualunque
sottomissione reale (vedi target di pubblicazione in
`paper/PIANO-ARTICOLO.md`). Le sezioni marcate **[FATTO]** si basano
su risultati reali già calcolati nel progetto; quelle marcate **[DA FARE]**
dipendono da lavoro non ancora completato (estensione a 300 comuni, uso del
suolo, popolazione, modello a errore spaziale — vedi lo stato dettagliato in
`paper/PIANO-ARTICOLO.md`). La validazione ARPA (§2.1, §3.6, §4.3)
è **[FATTO]** dal 2026-07-18. Non cancellare i marcatori finché il
lavoro sottostante non è davvero concluso: servono a non perdere traccia di
cosa è verificato e cosa no.

---

## Abstract

*[DA SCRIVERE PER ULTIMO, dopo Risultati e Discussione — bozza di
struttura]*

- Una frase di contesto (ondate di calore in aumento in Nord Italia/Arco
  Alpino).
- Gap: mancano analisi sistematiche a grana comunale per il Piemonte oltre
  ai singoli studi su Torino.
- Cosa abbiamo fatto: 44→300 comuni (**[DA FARE]**: aggiornare il numero
  finale), 2000-2025, trend + autocorrelazione spaziale + (**[DA FARE]**)
  fattori esplicativi.
- Risultato principale 1: trend di riscaldamento diffuso e significativo
  (38/44 comuni, +0.3/+1.4 °C/decade).
- Risultato principale 2: pattern spaziale non casuale (Moran's I
  significativo), tre regimi climatici distinti legati alla quota.
- Risultato principale 3 (**[DA FARE]**): ruolo dell'uso del suolo/densità
  demografica nello spiegare la varianza residua dopo aver controllato per
  la quota.

---

## 1. Introduzione

**[FATTO — contesto generale, letteratura raccolta il 2026-07-16, fonti
esatte verificate il 2026-07-19]**

1.1. Le ondate di calore in Italia sono aumentate di circa 7.5 giorni/decade
a livello nazionale (Settanta et al. 2024, oltre 250 stazioni, 1991-2020).
Negli Appennini, nel trentennio 1991-2020, gli eventi di caldo estremo
estivo sono aumentati del 134% rispetto al periodo di riferimento
1961-1990 (Capozzi et al. 2025) — **correzione il 2026-07-19**: la
raccolta del 16/7 attribuiva questo dato genericamente a "Nord
Italia/Arco Alpino", ma la fonte reale (ora scaricata, vedi Bibliografia)
riguarda specificamente gli Appennini, non le Alpi.

1.2. Il Piemonte, e in particolare Torino, ha una letteratura consolidata
sull'isola di calore urbana (Garzena et al. 2019; studi su UHI/UDI
nell'area metropolitana torinese) — ma quasi tutta concentrata sul
capoluogo, con confronto urbano/rurale su poche stazioni. Manca un'analisi
sistematica che copra l'intero territorio regionale a grana comunale.

1.3. **Domande di ricerca**:
   - (a) Come si distribuiscono nello spazio e nel tempo le ondate di
     calore in Piemonte tra il 2000 e il 2025? **[FATTO]**
   - (b) Il pattern spaziale osservato è spiegabile (anche) da fattori
     locali come l'uso del suolo e la densità di popolazione, oltre alla
     quota? **[DA FARE]**

1.4. Contributo: prima caratterizzazione a questa grana comunale (N=44→300,
**[DA FARE]** aggiornare) per il Piemonte, con autocorrelazione spaziale
testata esplicitamente (a differenza di molti studi locali su singola
città).

---

## 2. Dati e Metodi

### 2.1 Fonte dati e copertura **[FATTO, parzialmente in aggiornamento]**

- Temperatura giornaliera (max/min/media) da Open-Meteo Historical Weather
  API, 2000-2025 (26 anni), per **44 comuni** (in estensione a **300**,
  vedi `paper/PIANO-ARTICOLO.md` per lo stato). Selezione spaziale
  via campionamento "farthest-point" per provincia (non i comuni più
  vicini al capoluogo, ma quelli che massimizzano la copertura geografica).
- Confini amministrativi e geometrie: tutti i 1180 comuni piemontesi
  (ISTAT, shapefile confini amministrativi generalizzati).
- Elevazione: Open-Meteo Elevation API, centroide comunale (solo per i
  comuni con temperatura).
- **Limite dichiarato esplicitamente, ora validato empiricamente — [FATTO]
  il 2026-07-18**: le temperature sono derivate da reanalisi/modello
  (Open-Meteo), non da osservazioni dirette di stazione. Validate contro
  la rete di stazioni reali di ARPA Piemonte (API REST pubblica,
  `utility.arpa.piemonte.it/meteoidro/`, trovata via ricerca web dopo che
  l'URL originariamente configurato nel progetto si è rivelato un
  placeholder mai funzionante) per i **51 comuni** (su 44 di questa
  sezione, in estensione — vedi sopra) dove esiste una stazione ARPA
  attiva con sensore di temperatura corrispondente. Risultati completi in
  §3.6.

### 2.2 Definizione di ondata di calore **[FATTO]**

- Definizione primaria: ≥3 giorni consecutivi con T_max > 35°C (soglia
  fissa, uguale per tutti i comuni).
- Definizione di confronto (solo discussione metodologica, non usata per i
  risultati principali): soglia al 90° percentile calendariale specifico
  per comune (Perkins & Alexander, 2013), per discutere il limite della
  soglia fissa nei comuni alpini (quasi mai raggiunta anche in estati
  eccezionali per lo standard locale).
- Intensità: `(T_max - soglia) × durata_giorni`.

### 2.3 Analisi statistica **[FATTO, per la parte descrittiva]**

- **Trend**: test di Mann-Kendall (non parametrico, non assume normalità)
  + regressione lineare (stima in °C/decade), per comune, su
  `temp_mean_annual`.
- **Stagionalità**: scomposizione STL (`period=365`, `robust=True`) sulla
  serie giornaliera continua per comune.
- **Autocorrelazione spaziale**: indice di Moran calcolato su matrice pesi
  spaziali a distanza inversa (haversine tra centroidi), significatività
  via test di permutazione (999 permutazioni) — scelto invece
  dell'approssimazione normale asintotica per maggiore robustezza con
  campione ridotto.
- **Clustering climatico**: K-means (k=3) su temperatura media, giorni
  >30°C, giorni >35°C standardizzati.

### 2.4 Fattori esplicativi **[PARZIALMENTE FATTO]**

- **Popolazione residente — [FATTO] il 2026-07-16**: `municipalities.population`
  popolata per tutti i 1180 comuni piemontesi (fonte `demo.istat.it`, stima
  1° gennaio 2026; script `src/data_acquisition/download_population.py`).
  Densità demografica calcolabile subito (`population / area_km2`, entrambe
  le colonne già presenti). Vedi [Fonti dati](data-sources.md) per il
  percorso di acquisizione (due vicoli ciechi prima di trovare la fonte
  giusta: SDMX ISTAT nuovo senza dati esposti, portale legacy dismesso).
- **Uso del suolo — [FATTO] il 2026-07-16**: CORINE Land Cover 2018
  (Copernicus), overlay geopandas su geometrie comunali di tutti i 1180
  comuni → tabella `municipality_land_cover` con % urbano/agricolo/
  forestale-seminaturale/zone umide/acqua per comune. Nota temporale da
  dichiarare: CLC2018 è uno scatto statico usato contro temperature
  2000-2025 e popolazione stimata 2026 — accettabile (l'uso del suolo
  cambia lentamente) ma va detto esplicitamente, non nascosto.
- **Sotto-classi urbane — [FATTO] lo stesso giorno**: scomposizione di
  `pct_urban` in residenziale/industriale-commerciale/trasporti/verde
  urbano/estrattivo-cantieri — risponde direttamente all'ipotesi originale
  del paper su città **e industria**. Verificato: Grugliasco (34%
  industriale, 64% urbano) e Beinasco (33%, 67% urbano) sono le zone a
  maggiore componente industriale, coerente con la nota geografia
  industriale della cintura torinese — un segnale che `pct_urban`
  aggregato da solo non avrebbe potuto mostrare.
- Modello: dato che Moran's I è risultato significativo (§3.4), un OLS
  classico violerebbe l'indipendenza dei residui — pianificato un modello
  a errore/lag spaziale, con controllo VIF per multicollinearità
  (elevazione, densità demografica e % uso urbano del suolo sono
  probabilmente correlate tra loro). **[DA FARE]** — tutti gli
  ingredienti (temperatura, elevazione, popolazione, uso del suolo) sono
  ora disponibili per i comuni con temperatura; il modello vero e proprio
  non è ancora stato costruito.

---

## 3. Risultati

### 3.1 Trend termici **[FATTO — numeri reali, 44 comuni, 2000-2025]**

38 comuni su 44 mostrano un trend di riscaldamento statisticamente
significativo (Mann-Kendall, p<0.05), con pendenze tra +0.3 e +1.4
°C/decade (Bagnolo Piemonte il valore più alto). Il segnale è diffuso su
tutto il territorio, non limitato ai capoluoghi (che da soli davano 7/8
comuni significativi, +0.4/+1.0 °C/decade).

*[DA FARE]*: tabella/figura con la distribuzione spaziale delle pendenze
(mappa già generata in QGIS, `qgis_projects/temperature_heatmap.qgz` —
verificare se il render PNG esistente è già pubblicabile o va rifatto in
stile per una figura di paper).

### 3.2 Ondate di calore **[FATTO]**

145 eventi identificati (soglia 35°C/3gg) sul periodo 2000-2025, 44 comuni.
Alessandria il comune con più eventi (14), seguito da Casalnoceto (13) e
Asti (11). Diversi comuni alpini (Formazza, Macugnaga, Acceglio, Alagna
Valsesia, Bardonecchia, Ceresole Reale, Rorà, Aisone) non hanno mai
raggiunto la soglia nel periodo — coerente con clima/quota, non un
artefatto di copertura dati. 2003 e 2019 gli anni con più eventi a livello
regionale (11 e 9 sugli 8 capoluoghi), coerente con le ondate di calore
europee note di quegli anni.

### 3.3 Stagionalità **[FATTO]**

Ampiezza stagionale (STL) tra 27°C e 34°C. Massima nei comuni alpini/alta
quota (Bardonecchia 34.3°C, Macugnaga 33.4°C, Formazza 32.6°C — inverni più
rigidi), minima nei comuni di pianura vicino a laghi (Verbania 27.8°C,
Ghemme 27.9°C — effetto mitigante dell'acqua, da discutere in §4 come
possibile fattore protettivo, non solo l'uso del suolo urbano può
mitigare/amplificare).

### 3.4 Pattern spaziale e regimi climatici **[FATTO]**

Indice di Moran = 0.101 (atteso sotto casualità: -0.024), p=0.002 su 999
permutazioni — statisticamente significativo con N=44 (non lo era con
N=8: I=-0.096, p=0.732). I comuni geograficamente vicini hanno temperature
più simili tra loro di quanto atteso per caso.

Tre cluster K-means, ordinati per temperatura crescente:
- **Cluster 0, alpino** (3.8°C medi): comuni di alta quota ai margini
  montani nord e sud-ovest.
- **Cluster 1, intermedio** (11.1°C medi): comuni pedemontani/collinari.
- **Cluster 2, pianura calda** (12.9°C medi): Alessandria, Asti, Torino,
  Vercelli e altri comuni della pianura centro-orientale.

### 3.5 Fattori esplicativi oltre la quota **[DA FARE]**

*Sezione vuota fino al completamento di §2.4 (uso del suolo, popolazione,
modello spaziale).* Domanda a cui questa sezione dovrà rispondere: a parità
di quota (es. dentro il solo Cluster 2, pianura calda), la variazione
residua tra comuni si spiega con % superficie urbana o densità
demografica? Questo è il cuore esplicativo del paper, non ancora
disponibile.

### 3.6 Validazione contro osservazioni di stazione (ARPA Piemonte) **[FATTO — 2026-07-18]**

Confronto diretto, sullo stesso `(comune, data)`, tra le temperature
Open-Meteo usate in tutto questo lavoro e le osservazioni reali della rete
ARPA Piemonte, per i 51 comuni (su quelli con temperatura Open-Meteo) dove
esiste una stazione ARPA attiva con sensore di temperatura corrispondente
(inclusi tutti gli 8 capoluoghi di provincia). 451.502 coppie di
osservazioni giornaliere, 2000–2026.

**Accuratezza giornaliera**: correlazione di Pearson molto alta (r medio
0.966 su temp_max), ma un bias sistematico negativo — Open-Meteo sottostima
le temperature massime reali di -1.71°C in media (range per comune:
+3.27°C / -7.05°C). Il bias correla in modo statisticamente significativo
con l'elevazione del comune (r=-0.348, p=0.012): più alto il comune, più
Open-Meteo sottostima — coerente con un prodotto di rianalisi che
rappresenta una cella di griglia, non un punto, e in rilievo alpino
complesso media quote/esposizioni diverse.

**Il problema si aggrava sui giorni estremi**: ristretto ai giorni con
temperatura ARPA (verità di terra) sopra 35°C, il bias resta simile
(-2.21°C) ma la correlazione crolla da 0.956 a 0.400 — Open-Meteo perde
quasi del tutto la capacità di distinguere quali giorni estremi lo sono di
più, proprio nella fascia che definisce un'ondata di calore.

**Confronto a livello di evento (il test più diretto per questo lavoro)**:
riapplicando la stessa definizione di ondata di calore (§2.2) ai dati ARPA
per i 51 comuni e confrontando con le ondate già identificate su Open-Meteo
per gli stessi comuni (sovrapposizione temporale, non richiede date
identiche): **ARPA mostra 322 ondate di calore realmente accadute, contro
le 150 rilevate su Open-Meteo per gli stessi comuni — recall 31.4%**
(Open-Meteo cattura meno di un terzo delle ondate reali), **precision
62.0%** (delle ondate rilevate da Open-Meteo, oltre un terzo non trova
riscontro in un evento ARPA sovrapposto).

**Il trend di riscaldamento, invece, è robusto alla fonte dati**:
Mann-Kendall + regressione lineare ricalcolati sulla media annuale ARPA
per gli stessi 51 comuni concordano in segno con Open-Meteo nell'88.2% dei
casi (45/51); i 6 casi discordi sono tutti situazioni in cui almeno una
delle due fonti non raggiunge la significatività statistica — nessun caso
di due trend opposti *entrambi* significativi. Differenza media di
pendenza piccola (-0.095 °C/decade) rispetto alla dispersione dei trend
nel campione (+0.3/+1.4 °C/decade).

**Sintesi**: il risultato descrittivo principale di questo lavoro (§3.1,
riscaldamento diffuso e significativo) non è un artefatto della fonte
dati. Il conteggio delle ondate di calore (§3.2) invece sì — è quasi
certamente un sottoconteggio sostanziale del fenomeno reale, non un
numero prudente. Discusso come limite quantificato in §4.3.

---

## 4. Discussione

**[PARZIALMENTE FATTO — impalcatura, contenuto da espandere quando §3.5
sarà completa]**

4.1. Confronto con la letteratura su Torino (Garzena et al. 2019: UHI fino
a 4-5°C in condizioni notturne su 147 anni di dati) — il nostro pattern di
pianura calda (Cluster 2, che include Torino) è consistente in direzione,
ma il nostro disegno non isola l'effetto urbano da quello di quota/latitudine
finché §3.5 non è completa: **da riformulare con cautela, non sovra-
interpretare finché manca il controllo per uso del suolo**.

4.2. Il ruolo dell'acqua come fattore mitigante (Verbania, ampiezza
stagionale minima) — spunto di discussione indipendente da uso del
suolo/popolazione, già disponibile dai dati attuali.

4.3. Limiti:
   - Copertura: anche a 300 comuni, restano una minoranza dei 1180 comuni
     piemontesi — dichiarare esplicitamente il criterio di selezione
     (farthest-point sampling) e le sue implicazioni per la
     rappresentatività.
   - **Dati da reanalisi, non da stazione — validato quantitativamente
     (§3.6), non solo dichiarato**: contro le osservazioni reali ARPA
     Piemonte, Open-Meteo mostra un bias di -1.71°C in media
     (peggiore in quota) e, soprattutto, **rileva solo il 31.4% delle
     ondate di calore effettivamente accadute** nei 51 comuni con
     riscontro reale. Implicazione da scrivere esplicitamente: **i
     conteggi di ondate di calore riportati in questo lavoro (§3.2) sono
     con ogni probabilità un sottoconteggio sostanziale del fenomeno
     reale**, non un dato prudente/conservativo — un revisore attento
     individuerebbe questo limite comunque; meglio quantificarlo che
     lasciarlo implicito. Il trend di riscaldamento (§3.1), invece, è
     risultato robusto alla fonte dati (§3.6) e non condivide questo
     limite.
   - La stazione ARPA scelta per ciascun comune (§3.6) è la più vicina per
     quota al centroide comunale, non necessariamente rappresentativa
     dell'intero territorio — specie nei comuni alpini estesi, dove può
     essere un rifugio a un'altitudine molto diversa dal fondovalle
     abitato.
   - Definizione di ondata di calore a soglia fissa penalizza
     sistematicamente i comuni di montagna (discusso anche in dashboard,
     §2.2) — la soglia percentile come alternativa resta solo illustrativa
     in questo lavoro. Questo limite si somma, non si sostituisce, al
     sottoconteggio dovuto alla fonte dati appena descritto.

4.4. Implicazioni pratiche (pianificazione urbana, aree verdi, gestione del
rischio) — da scrivere dopo aver completato §3.5, altrimenti il collegamento
con l'uso del suolo resta speculativo.

---

## 5. Conclusioni

*[DA SCRIVERE PER ULTIMO]*

---

## Bibliografia

*Lista raccolta il 2026-07-16, completata il 2026-07-19: ogni voce
verificata con l'API pubblica di Crossref (autori/rivista/volume/DOI),
nessuna lasciata a un titolo raccolto a memoria. Dettaglio completo di
ogni verifica e dei PDF scaricati in `paper/references/README.md`.*

- Garzena, D. et al. (2019). Analysis of the long-time climate data series
  for Turin and assessment of the city's urban heat island. *Weather*
  (Wiley/RMetS).
- Perkins, S.E. & Alexander, L.V. (2013). On the Measurement of Heat Waves.
  *Journal of Climate*, 26(13).
- Nairn, J. & Fawcett, R. (2014). The Excess Heat Factor: A Metric for
  Heatwave Intensity and Its Use in Classifying Heatwave Severity.
  *International Journal of Environmental Research and Public Health*,
  12(1), 227-253. DOI: 10.3390/ijerph120100227. **Correzione il
  2026-07-19**: il coautore non è "Fenwick" (come raccolto a orecchio il
  16/7) ma **Fawcett** — verificato via Crossref. Open access (MDPI), ma
  download bloccato da protezione anti-bot del sito (403); link diretto
  disponibile.
- Morabito, M., Crisci, A., Guerri, G., Messeri, A., Congedo, L., Munafò,
  M. (2021). Surface urban heat islands in Italian metropolitan cities:
  Tree cover and impervious surface influences. *Science of The Total
  Environment*, 751, 142334. DOI: 10.1016/j.scitotenv.2020.142334 — era il
  "Studio SUHI/impervious surface" senza autori, ora completo.
- Bassani, F., Garbero, V., Poggi, D., Ridolfi, L., von Hardenberg, J.,
  Milelli, M. (2022). An innovative approach to select urban-rural sites
  for Urban Heat Island analysis: the case of Turin (Italy). *Urban
  Climate*, 42, 101099. DOI: 10.1016/j.uclim.2022.101099.
- Milelli, M., Bassani, F., Garbero, V., Poggi, D., von Hardenberg, J.,
  Ridolfi, L. (2023). Characterization of the Urban Heat and Dry Island
  effects in the Turin metropolitan area. *Urban Climate*, 47, 101397.
  DOI: 10.1016/j.uclim.2022.101397.
- Pauly, L., Canonico, M., Ferrero, E. (2024). Numerical investigation of
  thermal patterns and local wind circulations to characterize Urban Heat
  Island during a heatwave in Turin. *Urban Climate*, 54, 101847. DOI:
  10.1016/j.uclim.2024.101847 — era lo "studio numerico su UHI a Torino
  2019" senza titolo verificato: simulazione WRF/MLUCM dell'ondata di
  calore di giugno 2019, incluso l'effetto Foehn.
- De Razza, S., Zanetti, C., De Marchi, M., Pappalardo, S.E. (2024).
  Mapping urban heatwaves and islands: the reverse effect of Salento's
  "white cities". *Frontiers in Earth Science*, 12. DOI:
  10.3389/feart.2024.1375827 — open access, scaricato per intero in
  `paper/references/DeRazza_2024_Salento_white_cities.pdf`.
- Settanta, G., Fraschetti, P., Lena, F., Perconti, W., Piervitali, E.
  (2024). Recent tendencies of extreme heat events in Italy. *Theoretical
  and Applied Climatology*, 155, 7335–7348. DOI: 10.1007/s00704-024-05063-w
  — fonte esatta del dato "+7.5 giorni/decade" citato in Introduzione
  (250+ stazioni, 1991-2020, 77% delle stazioni +3gg/decade). Preprint ad
  accesso aperto scaricato in
  `paper/references/Settanta_2024_extreme_heat_events_Italy_PREPRINT.pdf`
  (DOI preprint 10.21203/rs.3.rs-4004015/v1).
- Capozzi, V., Di Bernardino, A., Budillon, G. (2025). Changes in
  large-scale circulation behind the increase in extreme heat events in
  the Apennines (Italy). *Atmospheric Research*, 319, 108013. DOI:
  10.1016/j.atmosres.2025.108013 — completa il titolo già presente dal
  2026-07-16. **Procurato dall'utente il 2026-07-19** e scaricato per
  intero in `paper/references/Capozzi_2025_Apennines_extreme_heat_circulation.pdf`
  — open access nativo (licenza CC BY), non paywall come inizialmente
  pensato. **Questa è la fonte esatta** del dato "+134%" già citato senza
  riferimento preciso dal 2026-07-16: Appennini, 1991-2020 vs 1961-1990,
  eventi estremi di caldo **+134% in estate, +102% in primavera** (+53%
  inverno, +27% autunno, questi ultimi due non sempre significativi in
  durata/severità).
- Petkov, B.H. (2015). Temperature Variability over the Po Valley, Italy,
  according to Radiosounding Data. *Advances in Meteorology*, 2015. DOI:
  10.1155/2015/383614 — rivista open access (Hindawi), scaricato per
  intero in `paper/references/Petkov_2015_Po_Valley_radiosounding.pdf`
  (anche su arXiv, 1410.8081). Era il riferimento "Po Valley da
  radiosondaggi" senza titolo verificato.

### Report istituzionali di confronto (aggiunti il 2026-07-19)

PDF completi in `paper/references/` (vedi `paper/references/README.md` per
dettagli e link):

- SNPA (2026). *Il clima in Italia nel 2025*. Report Ambientali SNPA n.
  48/2026, ISBN 978-88-448-0375-9.
- ARPA Piemonte (2026). *Il clima in Piemonte — Anno 2025*. — confronto
  diretto più rilevante: 2025 quinto anno più caldo dal 1958 in Piemonte
  (media annua ~10.8°C, +quasi 1°C sopra il trentennio 1991-2020 —
  confrontabile con il trend Mann-Kendall di questo lavoro, §3.1).
- ISTAT (2024). *Misure statistiche per l'adattamento ai cambiamenti
  climatici*. Statistica Focus, METEOCLIMA, anno 2022.
- ISPRA. *Qualità dell'ambiente urbano — Focus: Le città, la sfida dei
  cambiamenti climatici*.

### Riferimenti metodologici (aggiunti il 2026-07-19)

- Mann, H.B. (1945). Nonparametric Tests Against Trend. *Econometrica*,
  13, 245. DOI: 10.2307/1907187.
- Kendall, M.G. (1975). Rank Correlation Methods. Griffin, Londra.
- Moran, P.A.P. (1950). Notes on Continuous Stochastic Phenomena.
  *Biometrika*, 37, 17-23. DOI: 10.1093/biomet/37.1-2.17.
- Cleveland, R.B., Cleveland, W.S., McRae, J.E., Terpenning, I. (1990).
  STL: A Seasonal-Trend Decomposition Procedure Based on Loess. *Journal
  of Official Statistics*, 6(1), 3-73.
- MacQueen, J. (1967). Some Methods for Classification and Analysis of
  Multivariate Observations. Proc. 5th Berkeley Symposium on Mathematical
  Statistics and Probability, 1, 281-297.
- Anselin, L. (1988). Spatial Econometrics: Methods and Models. Kluwer
  Academic Publishers.

---

## Appendice A — Tracciabilità dei risultati

*Per onestà scientifica e per facilitare la revisione: ogni numero citato
in questo documento deve essere rintracciabile a un file `output/*.csv` o a
una pagina wiki. Tabella da completare mano a mano che si scrive.*

| Risultato citato | File/fonte | Verificato il |
|---|---|---|
| 38/44 comuni trend significativo | `output/trend_analysis.csv` | 2026-07-15 |
| 145 ondate di calore | `output/heatwave_stats_by_municipality.csv` | 2026-07-15 |
| Moran's I = 0.101, p=0.002 | `output/morans_i_summary.csv` | 2026-07-15 |
| Cluster K-means (3.8/11.1/12.9°C) | `output/spatial_analysis.csv` | 2026-07-16 (rietichettatura) |
| Ampiezza stagionale STL 27-34°C | `output/seasonal_trend_summary.csv` | 2026-07-15 |
| Bias ARPA -1.71°C, r=0.966 (temp_max) | `output/arpa_validation.csv` | 2026-07-18 |
| Bias vs elevazione r=-0.348, p=0.012 | `output/arpa_validation.csv` + `municipalities.elevation_m` | 2026-07-18 |
| Bias su giorni caldi (r crolla a 0.400 sopra 35°C) | `output/arpa_hot_day_bias.csv` | 2026-07-18 |
| 322 ondate ARPA vs 150 Open-Meteo (recall 31.4%, precision 62.0%) | `output/arpa_heatwave_events.csv`, `output/arpa_event_comparison_summary.csv` | 2026-07-18 |
| Trend ARPA/Open-Meteo concordi nell'88.2% dei casi | `output/arpa_trend_comparison.csv` | 2026-07-18 |
