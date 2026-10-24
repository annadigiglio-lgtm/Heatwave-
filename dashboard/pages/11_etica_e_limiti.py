"""
11_etica_e_limiti.py - Etica, privacy e limiti del progetto.

Trasforma in pagina il testo di riferimento `docs/pages/etica-e-limiti.md`:
cosa il progetto è e non è, limiti dei dati e dei modelli ML, uso
responsabile del chatbot, richiamo prudente ad AI Act e GDPR (lezione 10
del corso). I conteggi dei comuni vengono dallo snapshot
`data/dashboard_export/overview_stats.json`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from components.constants import THEME_COLD, THEME_HOT, THEME_MID
from components.queries import get_arpa_overview_stats, get_overview_stats
from components.styling import inject_custom_css, render_sidebar_branding, render_stats_row

st.set_page_config(page_title='Etica e limiti — Heatwave Piemonte', layout='wide')
inject_custom_css()
render_sidebar_branding()

CHATBOT_NOTICE = (
    "Assistente basato su intelligenza artificiale. Usa solo i dati e i "
    "documenti di Heatwave Piemonte, può sbagliare e non è un servizio di "
    "allerta o di consulenza sanitaria. Non inserire dati personali."
)

try:
    stats = get_overview_stats()
    arpa_stats = get_arpa_overview_stats()
    n_total = stats['n_municipalities']
    n_openmeteo = stats['n_municipalities_with_data']
    n_arpa = arpa_stats['n_arpa_municipalities']
    year_start = stats['date_start'].year
except (FileNotFoundError, OSError, KeyError):
    # Valori di docs/pages/etica-e-limiti.md se lo snapshot non è disponibile
    n_total, n_openmeteo, n_arpa, year_start = 1180, 599, 218, 2000

st.title("⚖️ Etica, privacy e limiti")
st.caption(
    "Cosa può dire questo progetto e cosa no: limiti dei dati e dei modelli, "
    "uso responsabile dell'assistente AI e richiamo alle regole europee."
)

with st.expander("ℹ️ Perché questa pagina"):
    st.markdown(
        "Ogni analisi dati incorpora delle scelte: quali fonti usare, come "
        "definire un fenomeno, quali variabili dare a un modello. Questa pagina "
        "le rende esplicite, così chi legge i risultati sa quanto fidarsi e "
        "dove fermarsi. È il testo di riferimento anche per la sezione "
        "\"Limiti\" del README."
    )

# ---------------------------------------------------------------------------
# Cosa il progetto è e cosa non è
# ---------------------------------------------------------------------------
st.subheader("Cosa il progetto è e cosa non è")
col_is, col_is_not = st.columns(2)
with col_is:
    st.success(
        "**È** uno strumento **dimostrativo e informativo** che descrive il "
        f"clima osservato in Piemonte dal {year_start} a oggi."
    )
with col_is_not:
    st.error(
        "**Non** è un sistema di allerta, **non** fa previsioni meteo, **non** "
        "dà indicazioni sanitarie o di protezione civile e **non** prende "
        "decisioni automatiche su persone."
    )

st.divider()

# ---------------------------------------------------------------------------
# Numeri chiave dei limiti
# ---------------------------------------------------------------------------
st.subheader("I limiti in quattro numeri")
render_stats_row([
    {
        'label': "Comuni con Open-Meteo", 'unit': f"/ {n_total}", 'color': THEME_MID,
        'value': str(n_openmeteo),
        'spark': [0.2, 0.3, 0.35, 0.45, 0.5, 0.5, 0.5, 0.5],
    },
    {
        'label': "Comuni con stazioni ARPA", 'unit': f"/ {n_total}", 'color': THEME_COLD,
        'value': str(n_arpa),
        'spark': [0.1, 0.15, 0.15, 0.2, 0.2, 0.2, 0.2, 0.2],
    },
    {
        'label': "Bias Open-Meteo sulle massime", 'unit': "°C (circa, vs ARPA)", 'color': THEME_HOT,
        'value': "−1,5",
        'spark': [0.6, 0.5, 0.55, 0.4, 0.45, 0.35, 0.4, 0.3],
        'unit_wrap': True,
    },
    {
        'label': "Dati personali nelle fonti climatiche", 'unit': "", 'color': THEME_COLD,
        'value': "0",
        'spark': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    },
])

st.divider()

# ---------------------------------------------------------------------------
# Dettaglio per area
# ---------------------------------------------------------------------------
tab_data, tab_ml, tab_chat, tab_rules = st.tabs([
    "📊 Dati", "🤖 Modelli di Machine Learning", "💬 Assistente (chatbot)", "🇪🇺 AI Act e GDPR",
])

with tab_data:
    st.markdown(
        "- Le fonti climatiche (Open-Meteo, ARPA Piemonte, ISTAT, CORINE, "
        "Copernicus) **non contengono dati personali**.\n"
        f"- **Copertura non uniforme**: {n_openmeteo} comuni su {n_total} con "
        f"Open-Meteo, {n_arpa} con stazioni ARPA. I risultati descrivono questi "
        "comuni, non un censimento completo della regione.\n"
        "- **Open-Meteo è una rianalisi, non una misura**: rispetto alle "
        "stazioni ARPA sottostima le temperature massime di circa 1,5 °C in "
        "media, con differenze maggiori in montagna.\n"
        "- **Definizione semplificata di ondata di calore**: almeno 3 giorni "
        "consecutivi sopra una soglia fissa. È una scelta più semplice degli "
        "indici a percentili usati dalla WMO, quindi i conteggi non sono "
        "direttamente confrontabili con quelli ufficiali."
    )

with tab_ml:
    st.markdown(
        "- I **cluster K-Means** dipendono dalle feature scelte, dalla "
        "standardizzazione e dal numero di cluster: `k=3` supera `k=2` di "
        "pochissimo, quindi i gruppi vanno letti come una semplificazione utile, "
        "non come \"zone climatiche\" ufficiali.\n"
        "- Il **regressore della temperatura spiega** le differenze tra comuni "
        "nel periodo osservato; **non prevede il futuro**.\n"
        "- **I comuni vicini si somigliano** (autocorrelazione spaziale, "
        "Moran's I significativo): le metriche di cross-validation possono "
        "essere ottimistiche. Per questo si riporta anche la **validazione "
        "raggruppata per provincia**, che tiene separati in addestramento e "
        "test i comuni della stessa provincia."
    )
    st.caption("Metriche, confronto tra valori di k e limiti del modello: pagina Machine Learning.")

with tab_chat:
    st.markdown("**Avviso mostrato nella pagina dell'assistente**")
    st.info(f"🤖 {CHATBOT_NOTICE}")
    col_answers, col_privacy = st.columns(2)
    with col_answers:
        st.markdown(
            "##### Da dove vengono le risposte\n"
            "- L'utente parla con un **modello di intelligenza artificiale**: "
            "l'avviso è sempre visibile.\n"
            "- Le risposte **possono contenere errori**.\n"
            "- I **numeri** vengono **solo** dai tool sui dati verificati del "
            "progetto.\n"
            "- Le **spiegazioni** vengono dai documenti del progetto (RAG) e "
            "sono **citate con la fonte**.\n"
            "- La pagina distingue visivamente valori calcolati, fonti citate e "
            "testo generato."
        )
    with col_privacy:
        st.markdown(
            "##### Privacy delle conversazioni\n"
            "- Le domande possono contenere testo personale: la conversazione "
            "resta **solo nella memoria della sessione del browser** "
            "(`st.session_state`) e si cancella con \"Nuova conversazione\" o "
            "chiudendo la pagina.\n"
            "- **Cache delle risposte su disco** (`data/cache_risposte/`, solo "
            "su questo computer e fuori da git): salva domanda e risposta per "
            "rispondere subito a una domanda già posta. Si svuota con il pulsante "
            "\"Svuota cache risposte\" nella pagina dell'assistente, si invalida "
            "da sola quando cambiano dati o prompt e si può disattivare "
            "(`chatbot.cache_risposte.enabled: false`). Nessun altro log delle "
            "conversazioni.\n"
            "- **Ollama (predefinito)**: il modello gira in locale, i testi non "
            "escono dal computer.\n"
            "- **Gemini (API Google, piano gratuito)**: risponde in pochi secondi, "
            "ma la domanda e i dati consultati dai tool vengono inviati a Google. "
            "Nei termini del piano gratuito i contenuti possono essere usati da "
            "Google per migliorare i propri servizi (da verificare nei termini "
            "aggiornati): per questo **non vanno inseriti dati personali**. La "
            "pagina dell'assistente lo ricorda quando questo motore è attivo.\n"
            "- **Anthropic (opzionale)**: le domande vengono inviate a un "
            "servizio esterno, e la pagina lo dichiara.\n"
            "- Gli **embedding** dei documenti (RAG) si calcolano sempre in locale "
            "con Ollama, qualunque sia il motore."
        )

with tab_rules:
    st.caption(
        "Richiamo didattico (lezione 10 del corso), non una valutazione legale."
    )
    col_act, col_gdpr = st.columns(2)
    with col_act:
        st.markdown(
            "##### AI Act (UE)\n"
            "Regola l'intelligenza artificiale **in proporzione al rischio**, su "
            "quattro livelli: vietato, alto rischio, rischio limitato, rischio "
            "minimo.\n\n"
            "Heatwave Piemonte va descritto con prudenza come **applicazione "
            "dimostrativa a basso impatto**: non decide su persone e non fornisce "
            "servizi critici. Non le si attribuisce una classificazione legale "
            "definitiva; in linea con il principio di trasparenza, l'assistente "
            "dichiara sempre di essere un sistema di AI."
        )
    with col_gdpr:
        st.markdown(
            "##### GDPR\n"
            "Si applica quando si trattano **dati personali**. Le fonti "
            "climatiche del progetto non ne contengono; l'unico punto di "
            "attenzione è il testo che l'utente scrive all'assistente, gestito "
            "con **minimizzazione**: memoria di sessione, cache locale "
            "cancellabile e disattivabile, elaborazione locale con Ollama.\n\n"
            "Il progetto **non prende decisioni basate unicamente su trattamento "
            "automatizzato** che riguardino persone (il tema dell'art. 22)."
        )

st.divider()
st.caption(
    "Fonti: docs/pages/etica-e-limiti.md; lezione 10 del corso (Applicazioni AI, "
    "etica e normativa). L'elenco completo delle fonti dati è nella pagina "
    "Citazioni e Fonti."
)
