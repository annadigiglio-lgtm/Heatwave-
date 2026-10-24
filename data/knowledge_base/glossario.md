# Glossario divulgativo

Le parole tecniche usate da Heatwave Piemonte spiegate in modo semplice.
Fonti: pagine wiki "Glossario", "Analisi statistica", "Fonti dati",
"Machine Learning".

## Rianalisi, misura di stazione e bias

**Rianalisi**: ricostruzione del clima passato che combina un modello
fisico dell'atmosfera con le osservazioni disponibili. Le temperature di
Open-Meteo usate dal progetto sono una rianalisi: sono stime, non misure
fatte da un termometro in quel comune.

**Misura di stazione**: valore registrato da una stazione meteorologica
reale, come quelle di ARPA Piemonte. Nel progetto le stazioni ARPA servono
a controllare la qualità della rianalisi.

**Bias**: differenza media tra due fonti, calcolata come Open-Meteo meno
ARPA. Un bias negativo vuol dire che Open-Meteo dà valori più bassi delle
stazioni. Per la temperatura massima il bias è di circa −1,5 °C in media, e
diventa più negativo nei giorni più caldi.

**Correlazione (r)**: misura da −1 a 1 di quanto due serie salgono e
scendono insieme. Open-Meteo e ARPA hanno una correlazione alta sulla
temperatura massima (0,968 in media sui 218 comuni), quindi seguono lo
stesso andamento giorno per giorno anche se i valori assoluti differiscono.

## Ondata di calore, durata e intensità

**Ondata di calore**: nel progetto, almeno 3 giorni consecutivi con
temperatura massima sopra 35 °C. È una definizione più semplice degli
indici a percentili usati dalla WMO, che confrontano ogni giorno con il
clima abituale del luogo.

**Durata**: numero di giorni consecutivi dell'ondata.

**Intensità**: quanto l'ondata è stata forte, calcolata come
(temperatura massima − soglia) × durata. Un'ondata lunga e molto sopra i
35 °C ha un'intensità alta.

**Giorni sopra 30 °C e sopra 35 °C**: numero medio di giorni all'anno in cui
la massima supera queste soglie. Sono due delle tre caratteristiche usate
per formare i cluster climatici.

**Stima per difetto**: un valore probabilmente più basso di quello reale.
Il numero di ondate calcolato con Open-Meteo lo è, perché la rianalisi
sottostima le massime.

## Trend, Mann-Kendall, regressione e STL

**Trend**: tendenza di lungo periodo di una serie di dati, per esempio la
temperatura che sale anno dopo anno.

**Test di Mann-Kendall**: test statistico non parametrico che verifica se
una serie ha un trend monotono, cioè se tende a salire o a scendere in modo
costante, senza assumere che i dati abbiano una distribuzione normale.

**Regressione lineare del trend**: retta che descrive l'andamento della
temperatura nel tempo; la pendenza si esprime in °C per decennio.

**p-value**: probabilità di osservare un risultato così forte se in realtà
non ci fosse alcun effetto. Nel progetto un risultato è significativo se il
p-value è minore di 0,05.

**STL**: tecnica che scompone una serie in tre parti: trend, stagionalità
(il ciclo estate-inverno che si ripete ogni anno) e residuo (le variazioni
che restano).

## Moran's I e autocorrelazione spaziale

**Autocorrelazione spaziale**: tendenza dei luoghi vicini ad avere valori
simili. In Piemonte i comuni di pianura vicini tra loro sono caldi, quelli
alpini vicini tra loro sono freschi.

**Moran's I (indice di Moran)**: numero che misura l'autocorrelazione
spaziale. Vicino a zero indica una distribuzione casuale, positivo indica
che valori simili stanno vicini. Nel progetto, sulla temperatura, vale
0,2115, molto sopra il valore atteso per caso (−0,0015).

**Pesi inverso-distanza**: modo di dire quanto due comuni sono "vicini":
più è piccola la distanza, più è grande il peso.

**Test di permutazione**: per capire se un risultato è dovuto al caso si
rimescolano i valori tra i comuni molte volte (999 nel progetto) e si
guarda quanto spesso il caso produce un risultato altrettanto forte.

**Regressione a errore spaziale**: regressione in cui l'errore di un comune
dipende da quello dei comuni vicini; serve quando i comuni non sono
indipendenti.

## K-Means, cluster e silhouette

**Machine Learning non supervisionato**: famiglia di metodi che cercano
gruppi o strutture nei dati senza una risposta "giusta" da imparare.

**K-Means**: algoritmo che divide i dati in k gruppi (cluster), mettendo
ogni comune nel gruppo con il centro (centroide) più vicino. Nel progetto
k = 3.

**Cluster climatico**: gruppo di comuni con un regime termico simile. Il
cluster 0 è alpino e più fresco, il cluster 1 intermedio, il cluster 2 di
pianura calda. Il numero indica l'ordine dal più fresco al più caldo.

**Standardizzazione (StandardScaler)**: porta ogni caratteristica a media 0
e deviazione standard 1, così temperature e numeri di giorni pesano allo
stesso modo nel calcolo delle distanze.

**Silhouette score**: punteggio da −1 a 1 che dice quanto ogni comune è più
vicino al proprio cluster che agli altri. Serve a scegliere k: nel progetto
k = 3 (0,5389) supera di poco k = 2 (0,5370).

## Elevazione e regressione spaziale

**Elevazione (quota)**: altezza del comune sul livello del mare, presa dal
centroide del comune con Open-Meteo Elevation.

**Predittore**: caratteristica usata in un modello per spiegare un'altra
grandezza, qui la temperatura media del comune.

**Predittore robusto**: predittore che resta significativo e con lo stesso
segno anche cambiando campione o metodo. Nel progetto l'elevazione è l'unico
predittore robusto: circa −0,6 °C ogni 100 metri.

**OLS**: la regressione lineare classica. Nel progetto spiega molto bene la
temperatura media (R² = 0,973), ma i suoi residui sono ancora correlati
nello spazio (Moran's I sui residui = 0,209), quindi non basta per
l'inferenza ed è stato usato un modello a errore spaziale.

**NDVI**: indice di vegetazione da satellite (Copernicus); più è alto, più
c'è vegetazione verde. Insieme alla percentuale di suolo urbano ha dato
risultati non ancora stabili.

## RAG, embedding e assistente AI

**LLM**: modello linguistico di grandi dimensioni, il "motore" che scrive le
risposte dell'assistente. Nel progetto gira in locale con Ollama.

**RAG (Retrieval-Augmented Generation)**: prima si cercano i documenti del
progetto più pertinenti alla domanda, poi il modello scrive la risposta
usando quei documenti come contesto e cita le fonti.

**Embedding**: vettore di numeri che rappresenta il significato di un testo;
testi simili hanno vettori vicini. Lo calcola una rete neurale
pre-addestrata, `bge-m3`.

**Similarità del coseno**: misura di quanto due vettori puntano nella stessa
direzione; vale 1 quando i due testi hanno lo stesso significato.

**Chunking**: suddivisione dei documenti in pezzi di circa 300 parole, con
una piccola sovrapposizione, da indicizzare.

**Allucinazione**: risposta plausibile ma non supportata dai dati. Per
evitarla l'assistente usa solo i dati e i documenti del progetto.
