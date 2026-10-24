"""
10_assistente_climatico.py - Chatbot "Assistente climatico" (T7.1).

Interfaccia chat (lezioni 13-06…08: `st.chat_input`, `st.chat_message`,
storia in `st.session_state`) sopra l'agente di `src/chatbot/agent.py`.
Su questo PC Ollama gira su CPU (circa 3 token/s), quindi la pagina:

1. riscalda il modello una sola volta per processo server
   (`st.cache_resource` attorno a `riscalda_modello()`);
2. mostra i passi dell'agente man mano in uno `st.status`;
3. mostra la risposta finale in streaming (lezione 14-05) e alla fine la
   sostituisce con il testo verificato dal Revisore.

La conversazione vive solo in `st.session_state` (mai su disco): vedi
`wiki/pages/etica-e-limiti.md`. Per i test: `HEATWAVE_FAKE_LLM=1`.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from components import PROJECT_ROOT
from components.styling import inject_custom_css, render_sidebar_branding
from src.chatbot import cache_risposte
from src.chatbot.agent import PREFISSO_EVENTO_TOOL, esegui_agente, riscalda_modello
from src.chatbot.llm_client import LLMNonDisponibile, crea_client, stato_llm
from src.chatbot.memory import FINESTRA_PREDEFINITA, MemoriaConversazione
from src.chatbot.prompts import SYSTEM_PROMPTS, VERSIONE_PREDEFINITA
from src.utils.config import config

st.set_page_config(page_title='Assistente climatico — Heatwave Piemonte', layout='wide')
inject_custom_css()
render_sidebar_branding()

AVVISO_AI = (
    "Assistente basato su intelligenza artificiale. Usa solo i dati e i "
    "documenti di Heatwave Piemonte, può sbagliare e non è un servizio di "
    "allerta o di consulenza sanitaria. Non inserire dati personali."
)
# Quattro domande della demo (wiki/pages/chatbot.md): un percorso ciascuna.
DOMANDE_ESEMPIO = [
    "Com'è cambiata la temperatura a Alessandria dal 2000?",          # dati (tool trend)
    "Perché Open-Meteo e ARPA danno valori diversi?",                  # metodo (RAG)
    "In che cluster climatico è Biella e cosa significa?",             # misto (tool + RAG)
    "Domani ci sarà un'ondata di calore a Torino?",                    # rifiuto motivato
]
BENCHMARK_CSV = PROJECT_ROOT / 'output' / 'chatbot_benchmark.csv'
MAX_CARATTERI_ESTRATTO = 400
ETICHETTE_PERCORSO = {
    'dati': 'dati (tool sui dati verificati)',
    'metodo': 'metodo (documenti del progetto, RAG)',
    'misto': 'misto (tool + documenti)',
    'fuori_ambito': 'fuori ambito (rifiuto, nessun modello usato)',
}

# Chiavi di st.session_state (lezione 14-07)
CHIAVE_MESSAGGI = 'chat_messaggi'       # messaggi visualizzati, con i dettagli del ragionamento
CHIAVE_STORIA = 'chat_history'          # MemoriaConversazione.to_list(): ciò che vede l'LLM
CHIAVE_IN_ATTESA = 'chat_domanda_esempio'

for chiave in (CHIAVE_MESSAGGI, CHIAVE_STORIA):
    st.session_state.setdefault(chiave, [])


# ---------------------------------------------------------------------------
# Risorse in cache
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30, show_spinner=False)
def stato_llm_in_cache(motore: str) -> tuple[bool, str]:
    """`stato_llm()` interroga Ollama: al massimo una volta ogni 30 s per motore."""
    return stato_llm(motore)


@st.cache_resource(show_spinner=False)
def client_per(motore: str):
    """Un client per motore e processo server (con `HEATWAVE_FAKE_LLM=1` è un FakeLLM)."""
    return crea_client(motore)


@st.cache_resource(show_spinner=False)
def modello_riscaldato(motore: str, versione: str) -> float:
    """Una sola lettura lenta del system prompt per processo server e versione.

    Serve solo a Ollama su CPU (circa 2 minuti la prima volta); le API cloud
    rispondono subito. Le eccezioni (es. `LLMNonDisponibile`) non vengono
    messe in cache: al rerun successivo si riprova.
    """
    if motore != 'ollama':
        return 0.0
    return riscalda_modello(client=client_per(motore), prompt_version=versione)


# ---------------------------------------------------------------------------
# Funzioni di supporto
# ---------------------------------------------------------------------------

def nuova_conversazione() -> None:
    """Svuota storia visualizzata e memoria dell'LLM (callback del pulsante)."""
    st.session_state[CHIAVE_MESSAGGI] = []
    st.session_state[CHIAVE_STORIA] = []
    st.session_state.pop(CHIAVE_IN_ATTESA, None)


def scegli_esempio(domanda: str) -> None:
    """Callback dei pulsanti d'esempio: la domanda parte al rerun."""
    st.session_state[CHIAVE_IN_ATTESA] = domanda


def _estratto(risultato) -> str:
    testo = json.dumps(risultato, ensure_ascii=False)
    return testo if len(testo) <= MAX_CARATTERI_ESTRATTO else testo[:MAX_CARATTERI_ESTRATTO] + ' …'


def dettagli_risposta(risposta) -> dict:
    """Traccia serializzabile di `RispostaAgente` da tenere in `session_state`."""
    return {
        'percorso': risposta.percorso,
        'tool': [{'nome': t['nome'], 'parametri': t.get('parametri') or {},
                  'estratto': _estratto(t.get('risultato', {})),
                  'errore': 'errore' in (t.get('risultato') or {})}
                 for t in risposta.tool_chiamati],
        'fonti': list(risposta.fonti),
        'avvisi': list(risposta.avvisi),
        'chiamate_llm': risposta.chiamate_llm,
        'durata_s': risposta.durata_s,
        'prompt_version': risposta.prompt_version,
        'dalla_cache': getattr(risposta, 'dalla_cache', False),
    }


def mostra_ragionamento(dettagli: dict) -> None:
    """Expander "Come ho ragionato": valori calcolati, fonti e avvisi separati dal testo."""
    for avviso in dettagli['avvisi']:
        st.warning(avviso, icon='⚠️')
    if dettagli.get('dalla_cache'):
        st.caption('⚡ Risposta dalla cache: la stessa domanda era già stata posta con gli '
                   'stessi dati, lo stesso modello e lo stesso prompt.')
    with st.expander('Come ho ragionato'):
        st.markdown(
            f"**Percorso:** {ETICHETTE_PERCORSO.get(dettagli['percorso'], dettagli['percorso'])}  \n"
            f"**Chiamate al modello:** {dettagli['chiamate_llm']} · "
            f"**Durata:** {dettagli['durata_s']:.1f} s · **Prompt:** {dettagli['prompt_version']}"
        )
        st.markdown('**Tool chiamati (valori calcolati sui dati verificati)**')
        if dettagli['tool']:
            for tool in dettagli['tool']:
                parametri = ', '.join(f'{k}={v}' for k, v in tool['parametri'].items())
                esito = ' — ❌ errore' if tool['errore'] else ''
                st.markdown(f"- `{tool['nome']}({parametri})`{esito}")
                st.code(tool['estratto'], language='json')
        else:
            st.caption('Nessun tool chiamato.')
        st.markdown('**Fonti dai documenti del progetto (RAG)**')
        if dettagli['fonti']:
            for fonte in dettagli['fonti']:
                similarita = fonte.get('similarita')
                valore = f' (similarità {similarita:.2f})' if isinstance(similarita, (int, float)) else ''
                st.markdown(f"- `{fonte.get('fonte')}` — {fonte.get('sezione')}{valore}")
        else:
            st.caption('Nessun documento usato.')


def rispondi(domanda: str, versione: str, motore: str) -> None:
    """Esegue l'agente mostrando passi e streaming; salva il risultato nella storia."""
    st.session_state[CHIAVE_MESSAGGI].append({'role': 'user', 'content': domanda})
    with st.chat_message('user'):
        st.markdown(domanda)

    finestra = int(config.get('chatbot.memory_window', FINESTRA_PREDEFINITA))
    memoria = MemoriaConversazione.from_list(st.session_state[CHIAVE_STORIA], finestra=finestra)

    with st.chat_message('assistant'):
        attesa = ' (su questo PC può richiedere 1–3 minuti)' if motore == 'ollama' else ''
        stato = st.status(f'Sto ragionando…{attesa}', expanded=True)
        area_testo = st.empty()
        pezzi: list[str] = []

        def on_evento(messaggio: str) -> None:
            # Una risposta già streammata che poi chiede un tool non era quella finale.
            if messaggio.startswith(PREFISSO_EVENTO_TOOL) and pezzi:
                pezzi.clear()
                area_testo.empty()
            stato.write(messaggio)

        def on_token(pezzo: str) -> None:
            pezzi.append(pezzo)
            area_testo.markdown(''.join(pezzi) + '▌')

        try:
            risposta = esegui_agente(domanda, memoria=memoria, client=client_per(motore),
                                     prompt_version=versione, on_evento=on_evento,
                                     on_token=on_token)
        except LLMNonDisponibile as errore:
            stato.update(label='Il modello non è disponibile', state='error', expanded=False)
            area_testo.empty()
            messaggio = f'**Il modello non è disponibile.** {errore}'
            st.error(messaggio)
            st.session_state[CHIAVE_MESSAGGI].append(
                {'role': 'assistant', 'content': messaggio, 'errore': True})
            return
        except ValueError as errore:
            stato.update(label='Configurazione non valida', state='error', expanded=False)
            area_testo.empty()
            messaggio = (f'**Configurazione del chatbot non valida:** {errore}. '
                         'Controlla la sezione `chatbot` di `config.yaml`.')
            st.error(messaggio)
            st.session_state[CHIAVE_MESSAGGI].append(
                {'role': 'assistant', 'content': messaggio, 'errore': True})
            return

        stato.update(label=f'Risposta pronta in {risposta.durata_s:.0f} s', state='complete',
                     expanded=False)
        # Il Revisore può aver corretto il testo streammato: si mostra quello finale.
        area_testo.markdown(risposta.testo)
        dettagli = dettagli_risposta(risposta)
        mostra_ragionamento(dettagli)

    st.session_state[CHIAVE_STORIA] = memoria.to_list()
    st.session_state[CHIAVE_MESSAGGI].append(
        {'role': 'assistant', 'content': risposta.testo, 'dettagli': dettagli})


def mostra_valutazione() -> None:
    """Tab "Valutazione": risultati del benchmark prompt v1 vs v2 (T8.2)."""
    st.subheader('Valutazione del chatbot')
    st.caption(
        'Benchmark sulle 28 domande di `tests/chatbot/test_set.csv`: tool corretti, numeri '
        'supportati dai dati, rifiuti corretti, fonti presenti e tempo medio, per ogni '
        'versione del prompt.'
    )
    if not BENCHMARK_CSV.exists():
        st.info('Benchmark non ancora eseguito (T8.2). Comando: '
                '`python -m tests.chatbot.benchmark --prompt v1 v2`.')
        return
    try:
        tabella = pd.read_csv(BENCHMARK_CSV)
    except (OSError, ValueError, pd.errors.ParserError) as errore:
        st.error(f'Impossibile leggere `{BENCHMARK_CSV.name}`: {errore}')
        return
    st.dataframe(tabella, hide_index=True, width='stretch')


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

MOTORI = {
    'gemini': '☁️ Gemini — veloce (API Google, piano gratuito)',
    'ollama': '💻 Ollama — locale e privato (lento su questo PC)',
}
MODELLO_PER_MOTORE = {'gemini': 'chatbot.gemini_model', 'ollama': 'chatbot.model',
                      'anthropic': 'chatbot.anthropic_model'}
provider_config = str(config.get('chatbot.provider', 'ollama')).strip().lower()
if provider_config not in MOTORI:
    MOTORI[provider_config] = provider_config
motori = list(MOTORI)
versioni = list(SYSTEM_PROMPTS)
versione_config = str(config.get('chatbot.prompt_version', VERSIONE_PREDEFINITA))
indice_versione = versioni.index(versione_config) if versione_config in versioni else 0

with st.sidebar:
    st.markdown('### 💬 Assistente climatico')
    motore = st.selectbox(
        'Motore del modello', motori, index=motori.index(provider_config),
        format_func=MOTORI.get,
        help='Gemini risponde in pochi secondi ma invia le domande a Google; Ollama gira '
             'su questo computer (nessun dato esce) ma su CPU richiede 1–3 minuti.',
    )
    llm_ok, llm_messaggio = stato_llm_in_cache(motore)
    if llm_ok:
        st.success(llm_messaggio, icon='✅')
    else:
        st.error(llm_messaggio, icon='❌')
    modello = str(config.get(MODELLO_PER_MOTORE.get(motore, 'chatbot.model'), ''))
    st.caption(f'Modello: **{modello or "non configurato"}** · embedding RAG: '
               f'**{config.get("chatbot.rag.embedding_model", "bge-m3")}** (Ollama, locale)')
    if motore != 'ollama':
        st.caption('🔒 Con questo motore le domande e i dati consultati vengono inviati al '
                   'servizio esterno: non inserire dati personali.')
    versione = st.selectbox(
        'Versione del prompt', versioni, index=indice_versione,
        help='v1: solo regole; v2: ruolo, esempi di chiamata tool e formato della risposta.',
    )
    st.button('🔄 Nuova conversazione', on_click=nuova_conversazione, width='stretch')
    st.markdown('**Domande d\'esempio**')
    for numero, esempio in enumerate(DOMANDE_ESEMPIO):
        st.button(esempio, key=f'esempio_{numero}', on_click=scegli_esempio, args=(esempio,),
                  disabled=not llm_ok, width='stretch')
    if motore == 'ollama':
        st.caption('⏱️ Su questo PC Ollama gira su CPU: una risposta richiede 1–3 minuti; '
                   'i rifiuti sono immediati e le domande già poste arrivano dalla cache.')
    else:
        st.caption('⏱️ Risposte in pochi secondi; i rifiuti sono immediati e le domande già '
                   'poste arrivano dalla cache.')
    if cache_risposte.cache_attiva():
        salvate = cache_risposte.conta()
        if st.button(f'🧹 Svuota cache risposte ({salvate})', disabled=not salvate,
                     width='stretch',
                     help='Le risposte salvate si invalidano da sole se cambiano dati, '
                          'indice dei documenti o prompt.'):
            cache_risposte.svuota()
            st.rerun()


# ---------------------------------------------------------------------------
# Corpo della pagina
# ---------------------------------------------------------------------------

st.title('💬 Assistente climatico')
st.caption(
    'Domande in italiano su temperature, ondate di calore, trend, cluster climatici, '
    'confronto Open-Meteo/ARPA, metodi e limiti del progetto. I numeri vengono dai tool '
    'sui dati verificati, le spiegazioni dai documenti del progetto.'
)
st.info(AVVISO_AI, icon='🤖')

tab_chat, tab_valutazione = st.tabs(['💬 Chat', '📊 Valutazione'])

# La tab Valutazione si riempie per prima: il riscaldamento del modello
# (fino a 2 minuti) non deve ritardarla.
with tab_valutazione:
    mostra_valutazione()

with tab_chat:
    # Dentro una tab `st.chat_input` è in linea: la conversazione sta in un
    # contenitore creato prima, così le nuove risposte compaiono sopra l'input.
    zona_chat = st.container()
    for messaggio in st.session_state[CHIAVE_MESSAGGI]:
        with zona_chat, st.chat_message(messaggio['role']):
            if messaggio.get('errore'):
                st.error(messaggio['content'])
            else:
                st.markdown(messaggio['content'])
            if messaggio.get('dettagli'):
                mostra_ragionamento(messaggio['dettagli'])

    pronto = llm_ok
    if llm_ok:
        try:
            with st.spinner('Preparo il modello: la prima volta richiede circa 2 minuti…'):
                modello_riscaldato(motore, versione)
        except LLMNonDisponibile as errore:
            pronto = False
            st.error(f'**Il modello non è disponibile.** {errore}')
        except ValueError as errore:
            pronto = False
            st.error(f'**Configurazione del chatbot non valida:** {errore}. '
                     'Controlla la sezione `chatbot` di `config.yaml`.')
    else:
        st.warning(
            f'La chat è disattivata perché il motore scelto non è pronto: {llm_messaggio} '
            'Puoi anche scegliere un altro motore nella barra laterale. Ollama serve '
            'comunque per gli embedding dei documenti (`ollama pull '
            f'{config.get("chatbot.rag.embedding_model", "bge-m3")}`).'
        )

    scritta = st.chat_input('Scrivi una domanda sul clima del Piemonte…', disabled=not pronto)
    domanda = scritta or st.session_state.pop(CHIAVE_IN_ATTESA, None)
    if domanda and pronto:
        with zona_chat:
            rispondi(domanda, versione, motore)
