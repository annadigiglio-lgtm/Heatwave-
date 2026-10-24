# Glossario

**Sorgenti**: `src/analysis/`, `src/machine_learning/`, [Chatbot](chatbot.md),
lezioni 16–21 del corso. Utile per rispondere alle domande dell'orale.

## Clima e statistica

- **Ondata di calore (definizione del progetto)**: almeno 3 giorni
  consecutivi con temperatura massima sopra 35 °C. È più semplice degli
  indici a percentili locali usati dalla WMO.
- **Rianalisi**: ricostruzione del clima passato che combina un modello
  fisico con le osservazioni (Open-Meteo). Non è una misura di stazione.
- **Bias**: differenza media tra due fonti (Open-Meteo − ARPA).
- **Mann-Kendall**: test non parametrico che verifica se una serie ha un
  trend monotono, senza assumere dati normali.
- **Regressione lineare del trend**: pendenza in °C per decennio.
- **STL**: scompone una serie in trend + stagionalità + residuo.
- **IQR**: un valore è anomalo se cade fuori da [Q1 − 1,5·IQR, Q3 + 1,5·IQR].
- **Moran's I**: misura quanto valori simili stanno vicini nello spazio;
  la significatività si stima permutando i valori a caso.
- **Regressione a errore spaziale**: regressione in cui l'errore di un
  comune dipende da quello dei vicini (parametro λ).
- **VIF**: indica quanto una variabile è ridondante rispetto alle altre
  (oltre 5 è da tenere d'occhio).

## Machine Learning

- **Supervisionato / non supervisionato**: con o senza variabile target da
  imparare (regressione vs K-Means).
- **Pipeline**: sequenza preprocessing + modello trattata come un oggetto
  unico; evita la fuga di informazioni tra train e test.
- **StandardScaler**: porta ogni feature a media 0 e deviazione standard 1.
- **K-Means**: divide i dati in k gruppi minimizzando la distanza dai centroidi.
- **Silhouette score**: da −1 a 1, quanto ogni punto è più vicino al
  proprio cluster che agli altri.
- **PCA**: riduce le feature a poche componenti che conservano la massima varianza.
- **Random Forest**: media di molti alberi di decisione addestrati su
  campioni diversi; robusto e interpretabile con l'importanza delle feature.
- **MLP**: rete neurale a strati completamente connessi; è il caso più
  semplice di deep learning.
- **Cross-validation (KFold)**: addestra e valuta k volte su parti diverse dei dati.
- **GroupKFold**: come KFold, ma un gruppo intero (qui una provincia) sta
  sempre tutto nello stesso fold; misura quanto il modello generalizza a zone nuove.
- **GridSearchCV**: prova combinazioni di iperparametri con cross-validation.
- **MAE / RMSE / R²**: errore medio assoluto, errore quadratico medio
  (penalizza di più gli errori grandi), quota di varianza spiegata.
- **Permutation importance**: quanto peggiora il modello mescolando una feature.

## LLM, agenti e RAG

- **LLM**: modello linguistico di grandi dimensioni. Nel progetto gira in
  locale con **Ollama**.
- **System prompt**: istruzioni fisse che definiscono ruolo e regole del chatbot.
- **Few-shot**: esempi inseriti nel prompt per mostrare il formato atteso.
- **Agente**: LLM in un ciclo ragiona → sceglie un tool → legge il
  risultato → decide se continuare.
- **Tool / function calling**: funzione Python che l'LLM può chiedere di
  eseguire; il codice la esegue solo se è nella whitelist.
- **Prompt injection**: testo che cerca di far ignorare al modello le sue regole.
- **RAG**: prima si recuperano i documenti pertinenti, poi si genera la
  risposta usando quei documenti come contesto.
- **Embedding**: vettore numerico che rappresenta il significato di un
  testo; testi simili hanno vettori vicini. Lo produce una rete neurale
  pre-addestrata (qui `bge-m3`, servita da Ollama).
- **Vector database / indice vettoriale**: archivio di embedding con ricerca
  per similarità. Nel corso si usa ChromaDB; nel progetto c'è un indice numpy
  con similarità del coseno, perché Windows blocca le librerie di ChromaDB.
- **Similarità del coseno**: coseno dell'angolo tra due vettori; vale 1
  quando i due testi hanno lo stesso significato.
- **Chunking**: suddivisione dei documenti in pezzi (circa 300 parole con
  sovrapposizione) da indicizzare.
- **Memoria a finestra scorrevole**: si passano all'LLM solo gli ultimi N
  scambi della conversazione.
- **Allucinazione**: risposta plausibile ma non supportata dai dati.
