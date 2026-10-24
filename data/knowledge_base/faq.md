# Domande frequenti sull'assistente climatico

Risposte brevi alle domande che un cittadino può fare su Heatwave Piemonte.
Fonti: pagine wiki "Analisi statistica", "Fonti dati", "Machine Learning",
"Glossario", "Etica e limiti".

## Cos'è un'ondata di calore?

**Domanda:** cosa intende il progetto per ondata di calore?

**Risposta:** un periodo di almeno 3 giorni consecutivi in cui la
temperatura massima supera 35 °C. Per ogni ondata si misurano la durata e
l'intensità, che combina di quanto la massima ha superato la soglia e
quanti giorni è durata l'ondata: intensità = (massima − soglia) × durata.

Con questa regola i dati Open-Meteo contano 2192 ondate in 333 comuni; i
comuni con più ondate sono Molino dei Torti e Castellazzo Bormida
(Alessandria), con 17 ciascuno.

La definizione è volutamente semplice. Gli indici della WMO usano soglie a
percentili, cioè confrontano ogni giorno con il clima tipico del luogo:
per questo nei comuni di montagna, dove 35 °C non si raggiungono quasi mai,
il progetto non trova ondate.

## Perché Open-Meteo e ARPA danno temperature diverse?

**Domanda:** per lo stesso comune e lo stesso giorno, perché Open-Meteo e la
stazione ARPA non danno la stessa temperatura?

**Risposta:** perché sono due cose diverse. La stazione ARPA è un
termometro vero, in un punto preciso. Open-Meteo è una **rianalisi**: una
ricostruzione del clima che combina un modello fisico con le osservazioni,
quindi una stima, non una misura.

Sui 218 comuni con stazione, Open-Meteo segue bene l'andamento dei giorni
(correlazione 0,968) ma in media **sottostima la temperatura massima di
circa 1,5 °C**. La differenza aumenta nei giorni più caldi (−2,64 °C quando
ARPA supera 35 °C) ed è maggiore in montagna.

Le tendenze però concordano: il riscaldamento si vede in tutte e due le
fonti, con trend dello stesso segno in 202 comuni su 218.

## Il Piemonte si sta scaldando?

**Domanda:** i dati mostrano un aumento delle temperature?

**Risposta:** sì. Con il test di Mann-Kendall, che verifica se una serie
tende a salire nel tempo, 556 comuni su 599 (92,8%) hanno un riscaldamento
statisticamente significativo. La regressione lineare dice di quanto: le
pendenze vanno da −0,62 a +1,51 °C per decennio, con il valore più alto a
Prarostino.

Solo due comuni alpini si raffreddano in modo significativo, Briga Alta e
Argentera.

Il risultato non dipende solo da Open-Meteo: nei 218 comuni con stazione
ARPA il segno del trend coincide in 202 casi (92,7%). Anche la scomposizione
STL della serie giornaliera mostra una componente di trend in aumento in 589
comuni su 599.

## Cosa significa che il mio comune è nel cluster 0, 1 o 2?

**Domanda:** l'assistente dice che un comune è nel cluster 2. Cosa vuol
dire?

**Risposta:** i cluster sono gruppi di comuni con un clima simile, trovati
dall'algoritmo K-Means a partire da temperatura media e giorni all'anno
sopra 30 °C e sopra 35 °C (medie 2000–2025). Sono numerati dal più fresco al
più caldo:

- **cluster 0, alpino e più fresco** (152 comuni): temperatura media
  6,17 °C, praticamente nessun giorno sopra 30 °C;
- **cluster 1, intermedio** (249 comuni): 11,90 °C, 12,40 giorni all'anno
  sopra 30 °C;
- **cluster 2, pianura calda** (198 comuni): 13,16 °C, 32,23 giorni sopra
  30 °C e 2,54 sopra 35 °C all'anno.

Essere nel cluster 2 significa quindi avere estati calde tipiche della
pianura. È un raggruppamento esplorativo, non una classificazione climatica
ufficiale.

## Cos'è l'indice di Moran e perché lo usate?

**Domanda:** cosa misura il Moran's I citato nelle analisi?

**Risposta:** l'indice di Moran misura se i comuni vicini hanno temperature
simili più di quanto succederebbe per caso (autocorrelazione spaziale).
Vicino a zero vuol dire distribuzione casuale; positivo vuol dire che valori
simili stanno vicini.

Nel progetto vale I = 0,2115 con p = 0,001, contro un valore atteso per
puro caso di −0,0015: le temperature del Piemonte formano zone omogenee. La
significatività è stata verificata rimescolando a caso i valori 999 volte.

Serve perché, se i comuni vicini si somigliano, non sono osservazioni
indipendenti: i modelli statistici e le loro metriche vanno letti con più
prudenza.

## Perché in montagna fa più fresco e quanto conta la quota?

**Domanda:** la quota del comune cambia davvero la temperatura?

**Risposta:** sì, ed è il fattore più importante. Nella regressione
spaziale del progetto l'elevazione è l'unico predittore robusto della
temperatura media: circa −0,6 °C ogni 100 metri di quota. Altri fattori,
come la percentuale di suolo urbano o la vegetazione, hanno dato risultati
non ancora stabili.

La quota spiega anche la mappa dei cluster climatici, con i comuni alpini
nel cluster 0 e quelli di pianura nel cluster 2, e la qualità dei dati: in
montagna la differenza tra Open-Meteo e le stazioni ARPA è maggiore.

## Quanti comuni sono coperti dai dati?

**Domanda:** posso trovare i dati del mio comune?

**Risposta:** dipende dal comune. Il Piemonte ha 1180 comuni:

- 599 hanno le temperature giornaliere di Open-Meteo, dal 2000-01-01 al
  2026-07-23;
- 218 hanno anche una stazione ARPA Piemonte attiva, usata per controllare i
  dati Open-Meteo;
- confini, popolazione, uso del suolo e vegetazione sono disponibili per
  tutti i 1180 comuni.

I 599 comuni Open-Meteo sono stati scelti per coprire tutte le province e
per includere tutti i comuni con stazione ARPA. Se un comune non ha dati,
l'assistente lo dice e non inventa valori.

## Il chatbot può dirmi se domani farà caldo?

**Domanda:** l'assistente può prevedere il caldo di domani o avvisarmi di
un'ondata di calore in arrivo?

**Risposta:** no. L'assistente descrive solo il clima **già osservato** in
Piemonte dal 2000 a oggi. Non fa previsioni meteo, non è un sistema di
allerta e non dà indicazioni di protezione civile. Anche i modelli di
Machine Learning del progetto descrivono il periodo osservato e non
prevedono il futuro.

Per sapere che tempo farà bisogna usare i servizi meteo e di allerta
ufficiali. L'assistente può invece dire, per esempio, quante ondate di
calore ha avuto un comune negli anni passati o com'è cambiata la sua
temperatura.

## Posso chiedere consigli sulla salute?

**Domanda:** l'assistente può dirmi come proteggermi dal caldo o se il
caldo è pericoloso per me?

**Risposta:** no. Heatwave Piemonte è uno strumento dimostrativo e
informativo sul clima: non dà indicazioni sanitarie e non prende decisioni
sulle persone.

L'assistente è un modello di intelligenza artificiale e può sbagliare. Usa
solo i dati e i documenti del progetto: i numeri vengono dai dati verificati
e le spiegazioni dai documenti, sempre con la fonte citata. Non inserire
dati personali nelle domande: la conversazione resta solo nella sessione del
browser e si cancella con "Nuova conversazione" o chiudendo la pagina.

## Le ondate di calore contate sono tutte quelle avvenute?

**Domanda:** il numero di ondate di calore del mio comune è completo?

**Risposta:** probabilmente no: è una **stima per difetto**. Open-Meteo
sottostima le temperature massime, soprattutto nei giorni più caldi, quindi
alcune ondate reali restano sotto la soglia di 35 °C nei dati.

Nei comuni con stazione ARPA il confronto lo mostra bene: ARPA registra
1185 ondate, Open-Meteo 459. Solo il 25,2% delle ondate reali viene
catturato da Open-Meteo, mentre il 63,6% delle ondate trovate da Open-Meteo
è confermato dalle stazioni. I numeri vanno quindi letti come un minimo.
