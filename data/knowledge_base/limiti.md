# Limiti del progetto e del chatbot

Scheda divulgativa su cosa Heatwave Piemonte e il suo assistente non fanno e
su quanto fidarsi dei risultati. Fonti: pagine wiki "Etica e limiti",
"Fonti dati", "Analisi statistica", "Machine Learning".

## Cosa il chatbot non fa: allerte, previsioni, salute

L'assistente climatico descrive il **clima osservato** in Piemonte dal 2000
a oggi. Non guarda al futuro.

- **Non è un sistema di allerta**: non avvisa di ondate di calore in arrivo
  e non dà indicazioni di protezione civile.
- **Non fa previsioni meteo**: non può dire che tempo farà domani o la
  settimana prossima, né se ci sarà un'ondata di calore.
- **Non dà indicazioni sanitarie**: non è un servizio di consulenza
  sanitaria e non dice come proteggersi dal caldo.
- **Non prende decisioni automatiche** sulle persone.

È uno strumento dimostrativo e informativo. È un modello di intelligenza
artificiale e può sbagliare: i numeri che riporta vengono solo dai dati
verificati del progetto e le spiegazioni dai documenti del progetto, con la
fonte citata.

## Copertura dei comuni

I dati non coprono tutto il Piemonte in modo uniforme. Su 1180 comuni:

- **599 comuni** hanno le serie di temperatura di Open-Meteo (2000-01-01 →
  2026-07-23), scelti per coprire tutte le province;
- **218 comuni** hanno una stazione ARPA Piemonte attiva, e tutti sono
  compresi tra i 599 Open-Meteo, così la validazione è completa (218 su 218).

I dati sul territorio (confini, popolazione ISTAT, uso del suolo CORINE,
vegetazione NDVI) sono invece disponibili per tutti i 1180 comuni.

Se un comune non è tra i 599, l'assistente non ha le sue temperature e lo
dice chiaramente, senza inventare valori. Si può guardare un comune vicino
con caratteristiche simili, ricordando che la quota cambia molto la
temperatura.

## Limiti dei dati di temperatura

Open-Meteo è una **rianalisi**, cioè una ricostruzione del clima che unisce
un modello fisico e le osservazioni, non una misura diretta. Rispetto alle
stazioni ARPA sottostima le massime di circa 1,5 °C in media, con
differenze maggiori in montagna e nei giorni più caldi.

Per questo il numero di ondate di calore calcolato con Open-Meteo è una
**stima per difetto**. Nei comuni con stazione, ARPA registra 1185 ondate e
Open-Meteo 459. Solo il 25,2% delle ondate registrate da ARPA viene
catturato da Open-Meteo (recall), mentre il 63,6% delle ondate trovate da
Open-Meteo è confermato da ARPA (precisione).

Il trend di riscaldamento, invece, è confermato dalle stazioni: il segno
coincide in 202 comuni su 218.

## Limiti della definizione di ondata di calore

Il progetto definisce ondata di calore almeno 3 giorni consecutivi con
temperatura massima sopra 35 °C. È una scelta semplice e trasparente, ma ha
dei limiti.

La soglia è fissa e uguale per tutti: un comune di pianura la supera più
volte, un comune alpino quasi mai, anche quando vive giorni eccezionalmente
caldi per la sua quota. Gli indici usati dalla WMO usano invece soglie a
percentili, cioè confrontano ogni giorno con il clima abituale del luogo.

Infine, poiché Open-Meteo sottostima le massime nei giorni più
caldi, alcune ondate reali restano sotto soglia nei dati.

## Limiti dei modelli di Machine Learning

I modelli del progetto **descrivono il periodo osservato** e non fanno
previsioni sul futuro.

I cluster climatici del K-Means dipendono dalle scelte fatte: le
caratteristiche usate, la standardizzazione e il numero di cluster. La
scelta di tre cluster supera quella di due di pochissimo nel silhouette
score (circa 0,002), e le tre caratteristiche sono correlate tra loro,
perché descrivono lo stesso regime termico. I cluster vanno quindi letti
come un raggruppamento esplorativo, non come una classificazione climatica
ufficiale.

I comuni vicini si somigliano (Moran's I significativo): per questo le
metriche di validazione possono risultare ottimistiche, e il progetto
riporta anche una validazione raggruppata per provincia. Nella regressione
spaziale solo l'elevazione è un predittore stabile; urbanizzazione e
vegetazione hanno dato risultati non ancora stabili.

## Privacy della conversazione

Le fonti climatiche del progetto non contengono dati personali. Le domande
scritte nel chatbot, però, potrebbero contenerne: per questo è meglio non
inserire dati personali.

La conversazione resta solo nella memoria della sessione del browser e si
cancella con il pulsante "Nuova conversazione" o chiudendo la pagina. Non
c'è alcun salvataggio delle conversazioni su disco.

Con Ollama il modello di intelligenza artificiale gira sul computer locale
e i testi non escono dal computer. Se si usa il provider Anthropic,
facoltativo, le domande vengono inviate a un servizio esterno, e la pagina
lo dichiara.
