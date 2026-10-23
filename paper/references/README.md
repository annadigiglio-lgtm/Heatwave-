# Materiale di confronto — report istituzionali e articoli peer-reviewed

Raccolto il 2026-07-19 su richiesta esplicita dell'utente: confrontare i
risultati del progetto con report scientifici/istituzionali di ISTAT, ARPA,
ISPRA e altri, oltre alla letteratura già raccolta il 2026-07-16 (vedi
`paper/PIANO-ARTICOLO.md`). I PDF sono scaricati per intero in
questa cartella (l'utente ha chiesto esplicitamente di poterli leggere,
non solo il link) — questo file resta comunque la fonte di verità con
link diretto, utile per ri-scaricarli se i binari venissero rimossi in
futuro.

## Report istituzionali (open access, scaricati)

| File locale | Ente | Titolo | Pubblicazione | Link diretto |
|---|---|---|---|---|
| `SNPA_clima_italia_2025.pdf` (11.3 MB) | SNPA (coordinato da ISPRA, con dati di tutte le ARPA regionali) | *Il clima in Italia nel 2025* — Report Ambientali SNPA n. 48/2026, ISBN 978-88-448-0375-9 | 2026-07-01 | https://www.snpambiente.it/wp-content/uploads/2026/07/Rapporto-SNPA-clima-2025.pdf |
| `ARPA_piemonte_clima_2025.pdf` (2.0 MB, 21 pag.) | ARPA Piemonte | *Il clima in Piemonte — Anno 2025* | 2026-02-18 | https://www.arpa.piemonte.it/sites/default/files/media/2026-02/anno_2025_solare_0.pdf |
| `ISTAT_meteoclima_2022.pdf` (2.5 MB, 29 pag.) | ISTAT | *Misure statistiche per l'adattamento ai cambiamenti climatici* — Statistica Focus, METEOCLIMA, anno 2022 | 2024-10 | https://www.istat.it/wp-content/uploads/2024/10/Statistica-focus-METEOCLIMA_Anno-2022.pdf |
| `ISPRA_focus_citta_cambiamenti_climatici.pdf` (18.8 MB) | ISPRA | *Qualità dell'ambiente urbano — Focus: Le città, la sfida dei cambiamenti climatici* | non datato nel file, pubblicazione ISPRA serie "Stato dell'Ambiente" | https://www.isprambiente.gov.it/files/pubblicazioni/statoambiente/FocussuLecittelasfidadeicambiamenticlimatici.pdf |

**Perché questi quattro**: coprono i tre livelli di confronto richiesti
dall'utente — nazionale (SNPA/ISPRA), regionale diretto (ARPA Piemonte,
stessa regione dei dati del progetto) e la stessa fonte statistica
nazionale di riferimento per l'indice di ondata di calore (ISTAT
METEOCLIMA, un indice a percentile per capoluogo di provincia — confrontabile
in metodo, anche se non nella soglia, con la definizione a soglia fissa
usata nel progetto, vedi `dashboard/components/heatwave_definitions.py`) più
un approfondimento specifico sull'isola di calore urbana (ISPRA, rilevante
per il Cluster 2 "pianura calda" di `statistical-analysis.md`).

**Numero utile per il confronto diretto già verificato**: ARPA Piemonte
riporta il 2025 come **quinto anno più caldo dal 1958** in Piemonte
(temperatura media annua ~10.8°C, +quasi 1°C sopra il trentennio di
riferimento 1991-2020) — confrontabile con il trend Mann-Kendall
2000-2025 già calcolato dal progetto (+0.3/+1.4 °C/decade su 44 comuni,
vedi `paper/manoscritto.md` §3.1).

## Articoli peer-reviewed

Tutte le voci di bibliografia che il 2026-07-16 erano titoli informali o
parziali sono state completate il 2026-07-19 con dettagli verificati via
l'API pubblica di Crossref (autori/rivista/volume/pagine/DOI) — mai
inventati. Scaricati per intero quelli con una versione ad accesso
aperto legittima (l'utente ha chiesto esplicitamente di poterli leggere).

### Scaricati (accesso aperto)

| File locale | Citazione | Nota accesso |
|---|---|---|
| `Settanta_2024_extreme_heat_events_Italy_PREPRINT.pdf` (2.4 MB, 23 pag.) | Settanta, G., Fraschetti, P., Lena, F., Perconti, W., Piervitali, E. (2024). *Recent tendencies of extreme heat events in Italy*. **Theoretical and Applied Climatology**, 155, 7335–7348. DOI: [10.1007/s00704-024-05063-w](https://doi.org/10.1007/s00704-024-05063-w) | Versione pubblicata a pagamento (Springer); scaricato il preprint pre-peer-review reso pubblico dagli stessi autori su Research Square (DOI preprint 10.21203/rs.3.rs-4004015/v1). **Fonte esatta** del dato "+7.5 giorni/decade" già citato in Introduzione senza riferimento preciso (250+ stazioni, 1991-2020, 77% delle stazioni +3gg/decade). |
| `DeRazza_2024_Salento_white_cities.pdf` (80.6 MB, 17 pag.) | De Razza, S., Zanetti, C., De Marchi, M., Pappalardo, S.E. (2024). *Mapping urban heatwaves and islands: the reverse effect of Salento's "white cities"*. **Frontiers in Earth Science**, 12. DOI: [10.3389/feart.2024.1375827](https://doi.org/10.3389/feart.2024.1375827) | Open access nativo (Frontiers). File pesante per le immagini satellitari Landsat-8 ad alta risoluzione incluse. |
| `Petkov_2015_Po_Valley_radiosounding.pdf` (0.3 MB, 16 pag.) | Petkov, B.H. (2015). *Temperature Variability over the Po Valley, Italy, according to Radiosounding Data*. **Advances in Meteorology**, 2015. DOI: [10.1155/2015/383614](https://doi.org/10.1155/2015/383614) | Open access nativo (Hindawi); scaricato via il mirror arXiv (1410.8081). Era il riferimento "Po Valley da radiosondaggi" senza titolo verificato. |
| `Capozzi_2025_Apennines_extreme_heat_circulation.pdf` (22.7 MB) | Capozzi, V., Di Bernardino, A., Budillon, G. (2025). *Changes in large-scale circulation behind the increase in extreme heat events in the Apennines (Italy)*. **Atmospheric Research**, 319, 108013. DOI: [10.1016/j.atmosres.2025.108013](https://doi.org/10.1016/j.atmosres.2025.108013) | **Procurato dall'utente il 2026-07-19** (non trovato da noi: il primo tentativo di ScienceDirect era paywalled). In realtà è **open access nativo** (licenza CC BY, verificato leggendo il testo scaricato) — trovato il vero DOI/pagina corretti dopo che l'utente aveva scaricato per errore 3 file dallo stesso fascicolo di rivista (editoriale + due articoli non pertinenti, poi eliminati). **Contiene la fonte esatta del dato "+134%"** già citato senza riferimento preciso dal 2026-07-16: nel testo, "in the last 30-year reference period (1991-2020), the number of regional extreme heat events increased by 134% in summer and 102% in spring compared to the 1961-1990 period" (Appennini; inverno +53%, autunno +27%, quest'ultime due non sempre significative). |

### Non scaricati (solo link/DOI)

| Citazione | Perché non scaricato |
|---|---|
| Nairn, J. & Fawcett, R. (2014). *The Excess Heat Factor: A Metric for Heatwave Intensity and Its Use in Classifying Heatwave Severity*. **International Journal of Environmental Research and Public Health**, 12(1), 227-253. DOI: [10.3390/ijerph120100227](https://doi.org/10.3390/ijerph120100227) | Open access nativo (MDPI), ma il download diretto è bloccato da una protezione anti-bot del sito (HTTP 403) — leggibile dal link diretto in un browser normale. **Correzione il 2026-07-19**: il coautore non è "Fenwick" (raccolto a orecchio il 16/7) ma **Fawcett**, verificato via Crossref. |
| Morabito, M., Crisci, A., Guerri, G., Messeri, A., Congedo, L., Munafò, M. (2021). *Surface urban heat islands in Italian metropolitan cities: Tree cover and impervious surface influences*. **Science of The Total Environment**, 751, 142334. DOI: [10.1016/j.scitotenv.2020.142334](https://doi.org/10.1016/j.scitotenv.2020.142334) | Paywall Elsevier, nessuna versione aperta trovata. |
| Bassani, F., Garbero, V., Poggi, D., Ridolfi, L., von Hardenberg, J., Milelli, M. (2022). *An innovative approach to select urban-rural sites for Urban Heat Island analysis: the case of Turin (Italy)*. **Urban Climate**, 42, 101099. DOI: [10.1016/j.uclim.2022.101099](https://doi.org/10.1016/j.uclim.2022.101099) | Paywall Elsevier. |
| Milelli, M., Bassani, F., Garbero, V., Poggi, D., von Hardenberg, J., Ridolfi, L. (2023). *Characterization of the Urban Heat and Dry Island effects in the Turin metropolitan area*. **Urban Climate**, 47, 101397. DOI: [10.1016/j.uclim.2022.101397](https://doi.org/10.1016/j.uclim.2022.101397) | Paywall Elsevier. |
| Pauly, L., Canonico, M., Ferrero, E. (2024). *Numerical investigation of thermal patterns and local wind circulations to characterize Urban Heat Island during a heatwave in Turin*. **Urban Climate**, 54, 101847. DOI: [10.1016/j.uclim.2024.101847](https://doi.org/10.1016/j.uclim.2024.101847) | Paywall Elsevier. Era lo "studio numerico su UHI a Torino 2019" senza titolo verificato — simulazione WRF/MLUCM dell'ondata di calore di giugno 2019, incluso l'effetto Foehn. |

## Citazioni metodologiche classiche (aggiunte su richiesta esplicita dell'utente)

Nessuna di queste richiede download: sono i riferimenti standard dei
metodi statistici già usati nel progetto (`src/analysis/`), da citare
perché la pagina dashboard "Sintesi della Ricerca" (in preparazione,
07, vedi `paper/PIANO-ARTICOLO.md`) cita ogni affermazione, non
solo i risultati.

- Mann, H.B. (1945). *Nonparametric Tests Against Trend*. **Econometrica**,
  13, 245. DOI: [10.2307/1907187](https://doi.org/10.2307/1907187). —
  base del test di Mann-Kendall usato per il trend di riscaldamento.
- Kendall, M.G. (1975). *Rank Correlation Methods*. Griffin, Londra. —
  formalizzazione del coefficiente usata insieme a Mann (1945); libro,
  nessun DOI assegnato.
- Moran, P.A.P. (1950). *Notes on Continuous Stochastic Phenomena*.
  **Biometrika**, 37, 17-23.
  DOI: [10.1093/biomet/37.1-2.17](https://doi.org/10.1093/biomet/37.1-2.17).
  — indice di autocorrelazione spaziale usato in `statistical-analysis.md`.
- Cleveland, R.B., Cleveland, W.S., McRae, J.E., Terpenning, I. (1990).
  *STL: A Seasonal-Trend Decomposition Procedure Based on Loess*.
  **Journal of Official Statistics**, 6(1), 3-73. — base della
  scomposizione stagionale usata nel progetto; nessun DOI verificato per
  la versione digitalizzata (rivista storica, DOI non sempre retro-assegnato).
- MacQueen, J. (1967). *Some Methods for Classification and Analysis of
  Multivariate Observations*. In: Proceedings of the 5th Berkeley
  Symposium on Mathematical Statistics and Probability, 1, 281-297. —
  algoritmo K-means usato per il clustering climatico. Atti di convegno,
  nessun DOI.
- Anselin, L. (1988). *Spatial Econometrics: Methods and Models*. Kluwer
  Academic Publishers. — base del modello a errore spaziale usato in
  `src/analysis/spatial_regression.py`. Libro, nessun DOI.

## Nota metodologica

Tutte le citazioni sopra sono state verificate (non inventate): i report
istituzionali via richiesta HTTP diretta (200 OK, `Content-Type:
application/pdf`, dimensione reale confermata), gli articoli
peer-reviewed via l'API pubblica di Crossref (`api.crossref.org`) per
autori/rivista/volume/DOI. Dove un dettaglio non era verificabile (es. DOI
di libri/atti di convegno pre-DOI), è dichiarato esplicitamente invece di
essere inventato.
