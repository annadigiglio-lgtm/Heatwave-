# Etica, privacy e limiti

**Sorgenti**: lezione 10 del corso (etica, AI Act, GDPR), risultati in
[Analisi statistica](statistical-analysis.md), [Machine Learning](machine-learning.md),
[Chatbot](chatbot.md).

Questa pagina è il **testo di riferimento** per la pagina Streamlit
`11_etica_e_limiti.py`, per la sezione "Limiti" del README e per la slide
finale. Va riportato con parole semplici, senza tecnicismi inutili.

## Cosa il progetto è e cosa non è

- È uno strumento **dimostrativo e informativo** che descrive il clima
  osservato in Piemonte dal 2000 a oggi.
- **Non** è un sistema di allerta, **non** fa previsioni meteo e **non** dà
  indicazioni sanitarie o di protezione civile.
- **Non** prende decisioni automatiche su persone.
- Rispetto all'AI Act va descritto con prudenza come applicazione
  dimostrativa a basso impatto, senza attribuirle una classificazione legale
  definitiva.

## Dati

- Le fonti climatiche (Open-Meteo, ARPA Piemonte, ISTAT, CORINE, Copernicus)
  **non contengono dati personali**.
- Copertura non uniforme: 599 comuni su 1180 con Open-Meteo, 218 con
  stazioni ARPA.
- Open-Meteo è una rianalisi, non una misura: rispetto ad ARPA sottostima le
  massime di circa 1,5 °C in media, con differenze maggiori in montagna.
- La definizione di ondata di calore (almeno 3 giorni sopra soglia fissa) è
  una scelta semplificata, diversa dagli indici a percentili usati da WMO.

## Modelli di Machine Learning

- I cluster K-Means dipendono dalle feature scelte, dalla standardizzazione
  e dal numero di cluster; `k=3` supera `k=2` di pochissimo.
- Il regressore della temperatura **spiega** le differenze tra comuni nel
  periodo osservato; non prevede il futuro.
- I comuni vicini si somigliano (Moran's I significativo): le metriche di
  cross-validation possono essere ottimistiche; per questo si riporta anche
  la validazione raggruppata per provincia.

## Chatbot (LLM)

- L'utente parla con un **modello di intelligenza artificiale**: l'avviso è
  sempre visibile nella pagina.
- Le risposte possono contenere errori. I numeri vengono **solo** dai tool
  sui dati verificati; le spiegazioni vengono dai documenti del progetto
  (RAG) e sono citate con la fonte.
- La pagina distingue visivamente valori calcolati, fonti citate e testo
  generato.
- Le domande dell'utente possono contenere testo personale: la conversazione
  resta solo in `st.session_state` (memoria della sessione del browser) e si
  cancella con il pulsante "Nuova conversazione" o chiudendo la pagina.
- **Cache delle risposte su disco** (`data/cache_risposte/`, solo su questo
  computer e fuori da git): salva domanda e risposta per servire subito una
  domanda già posta. È l'unico salvataggio delle conversazioni. Si svuota dal
  pulsante "Svuota cache risposte", si invalida da sola se cambiano dati o
  prompt, si disattiva con `chatbot.cache_risposte.enabled: false`. Prima di
  consegnare il PC o il repository va svuotata.
- Con Ollama il modello gira in locale e i testi non escono dal computer;
  con il provider Anthropic opzionale le domande vengono inviate a un
  servizio esterno, e la pagina lo dichiara.

## Testo breve da mostrare nella pagina del chatbot

> Assistente basato su intelligenza artificiale. Usa solo i dati e i
> documenti di Heatwave Piemonte, può sbagliare e non è un servizio di
> allerta o di consulenza sanitaria. Non inserire dati personali.
