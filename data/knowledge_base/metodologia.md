# Metodologia di Heatwave Piemonte

Scheda divulgativa: spiega in parole semplici come il progetto analizza il
clima osservato in Piemonte. Fonti: pagine wiki "Analisi statistica",
"Fonti dati", "Machine Learning", "Glossario".

## Cos'è un'ondata di calore nel progetto

Nel progetto un'ondata di calore è un periodo di **almeno 3 giorni
consecutivi** in cui la temperatura massima giornaliera supera **35 °C**.
La regola è uguale per tutti i comuni ed è facile da verificare sui dati.

Per ogni ondata si calcolano la durata (quanti giorni) e l'intensità, cioè
quanto la massima ha superato la soglia, moltiplicato per la durata:
intensità = (massima − soglia) × durata.

Con questa definizione, nei dati Open-Meteo risultano 2192 ondate in 333
comuni. I comuni con più ondate sono Molino dei Torti e Castellazzo Bormida,
in provincia di Alessandria, con 17 ondate ciascuno.

È una definizione **semplificata**: gli indici usati dalla WMO si basano su
soglie a percentili, cioè su quanto un giorno è caldo rispetto al clima
abituale di quel luogo. Una soglia fissa di 35 °C, invece, in montagna non
viene quasi mai raggiunta.

## Da dove vengono i dati

Le temperature giornaliere (media, massima, minima) e le precipitazioni
vengono dall'archivio storico di **Open-Meteo**, dal 2000-01-01 al
2026-07-23, per 599 comuni piemontesi su 1180. Open-Meteo è una
**rianalisi**: una ricostruzione del clima passato che combina un modello
fisico dell'atmosfera con le osservazioni disponibili.

Per controllare la qualità di questi dati il progetto usa le misure delle
stazioni di **ARPA Piemonte**, disponibili per 218 comuni con una stazione
attiva. Quando un comune ha più stazioni si sceglie quella con la quota più
vicina a quella del comune.

Altre fonti descrivono il territorio: ISTAT per i confini dei comuni e delle
province e per la popolazione, CORINE Land Cover 2018 per la percentuale di
suolo urbano, agricolo e forestale, Copernicus per l'indice di vegetazione
(NDVI) e Open-Meteo Elevation per la quota. Nessuna di queste fonti contiene
dati personali.

## Open-Meteo e ARPA: perché le temperature sono diverse

Open-Meteo e ARPA non misurano la stessa cosa. ARPA registra la temperatura
con un termometro in una stazione reale. Open-Meteo è una rianalisi: stima
la temperatura su una griglia, mescolando un modello fisico e le
osservazioni. Per questo i due valori non coincidono mai del tutto.

Il confronto sui 218 comuni con stazione dice che Open-Meteo segue bene la
variabilità giornaliera (correlazione 0,968 sulla massima) ma **sottostima
le massime di circa 1,5 °C** in media. L'errore cresce nei giorni più
caldi: nei giorni in cui ARPA supera 35 °C la sottostima è di −2,64 °C e
la correlazione scende a 0,375.

La differenza cambia molto da un comune all'altro, da +4,35 °C (Sampeyre) a
−7,69 °C (Cossogno), ed è legata alla quota: in montagna l'errore è
maggiore.

Il riscaldamento però si vede con entrambe le fonti: il segno del trend è lo
stesso in 202 comuni su 218 (92,7%).

## Trend: Mann-Kendall e regressione lineare

Per capire se un comune si sta scaldando il progetto usa due strumenti
complementari sulla serie delle temperature.

Il **test di Mann-Kendall** risponde alla domanda "c'è un trend?". Controlla
se la serie tende a salire (o scendere) in modo costante nel tempo, senza
supporre che i dati seguano una distribuzione normale. Il risultato è
significativo quando il p-value è minore di 0,05.

La **regressione lineare** risponde invece alla domanda "quanto?": la
pendenza della retta si esprime in °C per decennio.

Risultato: 556 comuni su 599 (92,8%) mostrano un riscaldamento
significativo. Le pendenze vanno da −0,62 a +1,51 °C per decennio, con il
valore più alto a Prarostino. Solo due comuni alpini si raffreddano in modo
significativo: Briga Alta (−0,62) e Argentera (−0,40).

Anche la scomposizione STL, che separa trend, stagionalità e residuo della
serie giornaliera, indica una componente di trend in aumento in 589 comuni
su 599 (98,3%).

## Moran's I: i comuni vicini si somigliano?

L'**indice di Moran** (Moran's I) misura l'autocorrelazione spaziale: dice
se i comuni vicini tra loro hanno valori simili più di quanto ci si
aspetterebbe per puro caso. Un valore vicino a zero indica una distribuzione
casuale nello spazio, un valore positivo indica che i valori simili tendono
a stare vicini.

Nel progetto la vicinanza tra comuni è pesata con l'inverso della distanza:
più due comuni sono vicini, più contano l'uno per l'altro. Per capire se il
risultato è dovuto al caso i valori vengono rimescolati a caso 999 volte
(test di permutazione).

Risultato sulla temperatura: I = 0,2115, contro un valore atteso sotto
casualità di −0,0015, con p = 0,001. Significa che le temperature formano
zone omogenee: pianure calde vicine ad altre pianure calde, montagne fresche
vicine ad altre montagne.

Questo ha una conseguenza pratica: i comuni non sono osservazioni del tutto
indipendenti, e i modelli statistici devono tenerne conto.

## K-Means: cosa significano i cluster 0, 1 e 2

Il **K-Means** è un algoritmo di Machine Learning non supervisionato: divide
i comuni in gruppi (cluster) con regimi termici simili, senza sapere in
anticipo quali gruppi esistano. Usa tre caratteristiche, medie 2000–2025:
temperatura media, giorni all'anno sopra 30 °C e giorni all'anno sopra
35 °C, standardizzate prima del calcolo.

Il numero di gruppi è stato scelto con il silhouette score: k = 3 (0,5389)
supera di poco k = 2 (0,5370). I cluster sono ordinati dal più fresco al
più caldo:

- **Cluster 0 — alpino, più fresco**: 152 comuni, temperatura media
  6,17 °C, 0,26 giorni sopra 30 °C all'anno, nessun giorno sopra 35 °C.
- **Cluster 1 — intermedio**: 249 comuni, 11,90 °C, 12,40 giorni sopra
  30 °C, 0,47 sopra 35 °C.
- **Cluster 2 — pianura calda**: 198 comuni, 13,16 °C, 32,23 giorni sopra
  30 °C, 2,54 sopra 35 °C.

È un raggruppamento esplorativo, non una classificazione climatica
ufficiale.

## Perché l'elevazione conta

La quota è il fattore che spiega meglio le differenze di temperatura tra i
comuni piemontesi. Nella regressione spaziale del progetto l'elevazione è
l'**unico predittore robusto**: circa −0,6 °C ogni 100 metri di quota
(−0,0059 °C per metro, p < 0,001): a parità di altre condizioni, più un
comune è in alto, più è fresco.

Altri fattori come la percentuale di suolo urbano e l'indice di vegetazione
(NDVI) hanno cambiato significatività e perfino segno tra analisi fatte su
campioni diversi di comuni: per ora vanno considerati risultati non stabili.

La quota conta anche per la qualità dei dati: la differenza tra Open-Meteo
e le stazioni ARPA è più grande in montagna (correlazione con la quota
r = −0,30). E spiega la mappa dei cluster climatici, con i comuni alpini nel
cluster 0 e quelli di pianura nel cluster 2.
