"""Agente multi-ruolo del chatbot "Assistente climatico" (lezioni 20-03, 20-04, 21-03).

Ciclo scritto a mano, sullo schema ``esegui_agente()`` della lezione 20-03:
formato testuale ``TOOL: nome`` / ``PARAMS: {...}``, ``parse_tool_request()``
con regex, whitelist ``TOOLS``, ``max_iterations`` ed errori dei tool
rimandati all'LLM come osservazione invece che sollevati.

::

    domanda ──► injection? ──sì──► rifiuto fisso (0 chiamate LLM)
                    │no
                    ▼
               Router (parole chiave; LLM breve solo se ambiguo)
       ┌───────────┼─────────────┬──────────────┐
    fuori_ambito  dati          metodo          misto
       │           │             │               │
    rifiuto     Analista     Ricercatore     RAG (solo recupero) +
    fisso       (tool loop)  (RAG + 1 LLM)   Analista con i documenti
                   └─────────────┴───────────────┘
                                 ▼
               Revisore in Python (numeri supportati? fonti presenti?)
                     │ok                     │ko
                     ▼                       ▼
                 risposta        1 passaggio LLM correttivo,
                                 poi eventuale avviso di incertezza

Scelte legate alle prestazioni (qwen2.5:7b su CPU, 6-12 s per chiamata):

- **Router per parole chiave**: i nomi dei comuni (indice di ``tools``) e le
  parole tipiche decidono quasi sempre senza LLM; fuori ambito e injection
  non costano nessuna chiamata.
- **Misto senza sintesi separata**: si recuperano i documenti (embedding,
  < 1 s) e li si passa all'Analista insieme ai tool; la sua risposta finale è
  già la sintesi. Costa 2 chiamate invece di 4 (Analista 2 + Ricercatore 1 +
  sintesi 1) e i numeri restano quelli dei tool.
- **Revisore in Python**: il secondo passaggio LLM parte solo se il
  controllo fallisce; se anche la correzione non basta si aggiunge un avviso.

Privacy (wiki/pages/etica-e-limiti.md): nei log non finisce mai il testo
dell'utente, solo la lunghezza, il percorso e i nomi dei tool.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from src.chatbot import prompts
from src.chatbot import tools as modulo_tools
from src.chatbot.llm_client import ClientLLM, LLMNonDisponibile, crea_client
from src.chatbot.memory import MemoriaConversazione
from src.chatbot.rag import cerca_documenti, formatta_contesto
from src.chatbot.tools import TOOLS, esegui_tool, normalizza_nome
from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

PERCORSI = ('dati', 'metodo', 'misto', 'fuori_ambito')
MAX_ITERAZIONI_PREDEFINITO = 5
NUM_PREDICT_PREDEFINITO = 300
MAX_TOKEN_ROUTER = 8
TOP_K_PREDEFINITO = 4
TOP_K_MISTO = 3
PAROLE_CHUNK_MISTO = 120
MAX_TOOL_PER_RISPOSTA = 2
MAX_CARATTERI_DATI_REVISORE = 6000
PERCORSO_DI_RISERVA = 'metodo'
SEGNAPOSTO_INJECTION = '[richiesta non ammessa, rifiutata]'

# Numeri sempre ammessi nelle risposte: periodo dei dati e soglie del progetto.
NUMERI_SEMPRE_AMMESSI = (2000.0, 2026.0, 35.0, 30.0, 3.0, 0.05, 1.5)


@dataclass
class RispostaAgente:
    """Risultato di ``esegui_agente()``: risposta e traccia del ragionamento."""

    testo: str
    percorso: str
    tool_chiamati: list[dict] = field(default_factory=list)
    fonti: list[dict] = field(default_factory=list)
    avvisi: list[str] = field(default_factory=list)
    chiamate_llm: int = 0
    durata_s: float = 0.0
    prompt_version: str = prompts.VERSIONE_PREDEFINITA


@dataclass
class _Lavoro:
    """Stato interno di una domanda, condiviso tra i ruoli."""

    client: ClientLLM | None
    versione: str
    tool_chiamati: list[dict] = field(default_factory=list)
    chunk: list[dict] = field(default_factory=list)
    avvisi: list[str] = field(default_factory=list)
    chiamate_llm: int = 0


# ---------------------------------------------------------------------------
# Router: injection, fuori ambito, dati / metodo / misto
# ---------------------------------------------------------------------------

_PATTERN_INJECTION = [
    r'\bignora\w*\b.{0,40}\b(istruzion|regol|prompt|indicazion)',
    r'\bdimentica\w*\b.{0,40}\b(istruzion|regol|prompt)',
    r'\bignore\b.{0,30}\binstruction',
    r'\bsystem\s*prompt\b', r'\bprompt di sistema\b',
    r'\b(mostra|rivela|stampa|ripeti|dimmi|scrivi)\w*\b.{0,40}\b(tue|tuoi|il tuo|le tue)\b.{0,15}'
    r'\b(istruzion|regol|prompt)',
    r'\bmodalita (debug|sviluppatore|developer|admin|dio)\b', r'\bjailbreak\b', r'\bdeveloper mode\b',
    r'\bda (ora|adesso) in poi (sei|devi|rispondi)\b', r'\b(fingi|immagina) di essere\b',
    r'\bnuove istruzioni\b', r'\bact as\b',
    r'\b(drop|truncate|alter)\s+table\b', r'\bdelete\s+from\b', r'\binsert\s+into\b',
    r'\bselect\b.{0,80}\bfrom\b', r'\bupdate\s+\w+\s+set\b',
    r'\besegui\w*\b.{0,30}\b(query|sql|codice|comando|script)\b',
    r'\b(import os|subprocess|eval\(|exec\()',
]

_PATTERN_PREVISIONE = [
    r'\bdomani\b', r'\bdopodomani\b', r'\bstasera\b', r'\bstanotte\b', r'\bweekend\b',
    r'\b(prossima|prossime) (settimana|settimane|giorni|estate)\b', r'\bprossimi giorni\b',
    r'\bnei prossimi\b', r'\bche tempo (fa|fara)\b', r'\bprevision\w* (del tempo|meteo)\b',
    r'\bmeteo di (oggi|domani)\b', r'\bpiovera\b', r'\bnevichera\b', r'\bfara caldo\b',
]

_PATTERN_SANITARIO = [
    r'\bmedicin', r'\bfarmac', r'\bsintom', r'\bmedico\b', r'\bcolpo di calore\b', r'\bmalore\b',
    r'\bcurar', r'\bterapi', r'\bpillol', r'\bospedal', r'\bdevo prendere\b', r'\bmalattia\b',
]

_PATTERN_GENERICO = [
    r'\bricett', r'\bcucina', r'\bbagna cauda\b', r'\boroscopo\b', r'\bcalcio\b', r'\bbitcoin\b',
    r'\bbarzellett', r'\bpoesia\b', r'\bcanzone\b', r'\bfilm\b', r'\brisultati elettorali\b',
]

# Indicano con forza una domanda sui dati: comune, anno o richieste quantitative.
_PATTERN_DATI_FORTI = [
    r'\b(19|20)\d{2}\b', r'\bquant[aeio]\b', r'\bconfront', r'\bpiu (cald|fredd|fresc)',
    r'\bprovinc', r'\bclassifica\b', r'\bquadro regionale\b',
]

# Parole dei dati: decidono solo se non c'è alcun segnale di metodo.
_PATTERN_DATI_DEBOLI = [
    r'\btrend\b', r'\bondat', r'\bcluster\b', r'\bgruppo climatico\b', r'\btemperatur', r'\bcald',
    r'\bgradi\b', r'\bgiorni\b', r'\bstazion', r'\bcopertura\b', r'\bdati\b', r'\bpiemonte\b',
    r'\banno\b', r'\bmassim', r'\bminim', r'\bintensit', r'\briscaldament', r'\bclima',
]

# Domande di spiegazione: con un comune o un anno diventano "misto".
_PATTERN_METODO_FORTI = [
    r'\bperche\b', r"\bcos ?' ?e\b", r'\bcosa e\b', r'\bche cos', r'\bcosa (significa|vuol dire|'
    r'indica|rappresenta|misura|vuole dire)\b', r'\bsignificat[oi]\b', r'\bin che senso\b',
    r'\bcome (funziona|funzionano|si calcola|si calcolano|calcolate|avete|definite|si definisce|'
    r'e stato|e stata|sono stati|sono state|viene|vengono|si interpreta|interpret|leggere)',
    r'\ba cosa serv', r'\bspiega', r'\bdefinizion', r'\bmetod',
]

# Termini tecnici: indicano "metodo" quando manca un comune o un anno.
_PATTERN_METODO_DEBOLI = [
    r'\bmoran', r'\bmann ?-? ?kendall\b', r'\bk ?-? ?means\b', r'\bsilhouette\b', r'\bbias\b',
    r'\brianalisi\b', r'\bregression', r'\bautocorrelazion', r'\bsen\b', r'\bp ?-? ?value\b',
    r'\blimit[ie]\b', r'\baffidabil', r'\bincertezz', r'\bfont[ie]\b', r'\bopen ?-? ?meteo\b',
    r'\barpa\b', r'\bera5\b', r'\bcopernicus\b', r'\bndvi\b', r'\bisola di calore\b',
    r'\balgoritm', r'\bmodello\b', r'\bstandardscaler\b', r'\bglossario\b', r'\bprogetto\b',
]

# Nomi di comuni che sono anche parole comuni italiane: non bastano per dire "dati".
PAROLE_COMUNI_AMBIGUE = frozenset({
    'alto', 'bruno', 'canale', 'camino', 'donato', 'grosso', 'none', 'porte', 'ponti', 're',
    'rive', 'sale', 'terzo', 'viale', 'viola', 'front', 'piatto', 'lenta', 'rossa', 'scopa',
    'pila', 'mango', 'manta', 'monta', 'lesa', 'melle', 'bee', 'pray', 'ceres', 'vaie', 'envie',
    'faule', 'perlo', 'bosco', 'valle', 'ameno', 'boca', 'masio', 'nole', 'roure', 'piea',
    'prali', 'rora', 'traves', 'soglio', 'cerano', 'corio', 'pagno', 'curino', 'denice',
    'pisano', 'zimone', 'crova', 'cressa', 'busca', 'pella', 'strona', 'aglie', 'serole',
})


def _testo_per_regole(testo: str) -> str:
    """Normalizza per il confronto: minuscole, senza accenti, punteggiatura → spazi."""
    testo = normalizza_nome(testo).replace("'", "' ")
    testo = re.sub(r"[^\w'°]+", ' ', testo)
    return re.sub(r'\s+', ' ', testo).strip()


def _cerca(pattern: list[str], testo: str) -> bool:
    return any(re.search(p, testo) for p in pattern)


@lru_cache(maxsize=1)
def _comuni_per_router() -> tuple[str, ...]:
    """Nomi normalizzati dei 1180 comuni piemontesi (indice di ``tools``), dal più lungo."""
    try:
        indice, _ = modulo_tools._indice_comuni(str(modulo_tools._data_dir(None)))
    except Exception as errore:  # noqa: BLE001 - senza dati il router usa solo le parole
        logger.warning(f'Router: elenco comuni non disponibile ({type(errore).__name__})')
        return ()
    nomi = {_testo_per_regole(nome) for nome in indice if nome not in PAROLE_COMUNI_AMBIGUE}
    return tuple(sorted((n for n in nomi if n), key=len, reverse=True))


def comuni_citati(domanda: str) -> list[str]:
    """Comuni (normalizzati) citati nella domanda, cercati a parola intera."""
    testo = f' {_testo_per_regole(domanda)} '
    trovati: list[str] = []
    for nome in _comuni_per_router():
        if f' {nome} ' in testo and not any(nome in altro for altro in trovati):
            trovati.append(nome)
    return trovati


def rileva_injection(domanda: str) -> bool:
    """Vero se la domanda tenta di cambiare le regole, leggere il prompt o eseguire SQL/codice."""
    testo = _testo_per_regole(domanda)
    return _cerca(_PATTERN_INJECTION, testo) or _cerca(_PATTERN_INJECTION, domanda.lower())


def _classifica_per_regole(domanda: str) -> tuple[str | None, str | None]:
    """Router per parole chiave: ``(percorso, motivo)``; percorso ``None`` se ambiguo.

    ``motivo`` dice quale rifiuto usare (``injection``, ``previsione``,
    ``sanitario``, ``generico``) quando il percorso è ``fuori_ambito``.
    """
    if rileva_injection(domanda):
        return 'fuori_ambito', 'injection'
    testo = _testo_per_regole(domanda)
    for motivo, pattern in (('previsione', _PATTERN_PREVISIONE),
                            ('sanitario', _PATTERN_SANITARIO),
                            ('generico', _PATTERN_GENERICO)):
        if _cerca(pattern, testo):
            return 'fuori_ambito', motivo

    dati_forti = bool(comuni_citati(domanda)) or _cerca(_PATTERN_DATI_FORTI, testo)
    metodo_forte = _cerca(_PATTERN_METODO_FORTI, testo)
    if dati_forti and metodo_forte:
        return 'misto', None
    if dati_forti:
        return 'dati', None
    if metodo_forte or _cerca(_PATTERN_METODO_DEBOLI, testo):
        return 'metodo', None
    if _cerca(_PATTERN_DATI_DEBOLI, testo):
        return 'dati', None
    return None, None


def _etichetta_router(risposta: str) -> str:
    """Prima etichetta valida nella risposta del router LLM (riserva: ``metodo``)."""
    testo = normalizza_nome(risposta).replace('fuori ambito', 'fuori_ambito')
    posizioni = {p: testo.find(p) for p in PERCORSI if p in testo}
    if not posizioni:
        return PERCORSO_DI_RISERVA
    return min(posizioni, key=posizioni.get)


def _instrada_con_llm(domanda: str, lavoro: _Lavoro) -> str:
    """Router di riserva: una chiamata LLM brevissima (``max_tokens`` 8)."""
    messaggi = [_system(lavoro),
                {'role': 'user', 'content': prompts.PROMPT_ROUTER.format(domanda=domanda)}]
    return _etichetta_router(_chiedi(lavoro, messaggi, max_tokens=MAX_TOKEN_ROUTER))


def instrada(domanda: str, client: ClientLLM | None = None) -> str:
    """Percorso della domanda: ``dati`` | ``metodo`` | ``misto`` | ``fuori_ambito``.

    Prima le regole per parole chiave (injection e fuori ambito per primi);
    solo se non decidono, una chiamata LLM breve al router di riserva.
    """
    percorso, _ = _classifica_per_regole(domanda)
    if percorso is not None:
        return percorso
    lavoro = _Lavoro(client=client, versione=prompts.versione_prompt())
    return _instrada_con_llm(domanda, lavoro)


# ---------------------------------------------------------------------------
# Parsing delle richieste di tool (lezione 20-03, più tollerante)
# ---------------------------------------------------------------------------

_RE_TOOL = re.compile(r'TOOL\s*:\s*[`*"\']*\s*([A-Za-z_][\w.-]*)', re.IGNORECASE)
_RE_PARAMS = re.compile(r'PARAMS?\s*:\s*', re.IGNORECASE)
_RE_TOOL_JSON = re.compile(r'"(?:tool|name|nome)"\s*:\s*"([A-Za-z_]\w*)"')


def _estrai_oggetto(testo: str, inizio: int) -> str | None:
    """Oggetto ``{...}`` che parte da ``inizio``, bilanciando parentesi e apici."""
    if inizio >= len(testo) or testo[inizio] != '{':
        return None
    profondita, apice, escape = 0, '', False
    for posizione in range(inizio, len(testo)):
        carattere = testo[posizione]
        if apice:
            if escape:
                escape = False
            elif carattere == '\\':
                escape = True
            elif carattere == apice:
                apice = ''
        elif carattere in '"\'':
            apice = carattere
        elif carattere == '{':
            profondita += 1
        elif carattere == '}':
            profondita -= 1
            if profondita == 0:
                return testo[inizio:posizione + 1]
    return None


def _carica_parametri(testo: str) -> dict | None:
    """JSON → dict; in riserva accetta apici singoli e True/False/None in stile Python."""
    try:
        valore = json.loads(testo)
    except json.JSONDecodeError:
        try:
            valore = ast.literal_eval(testo)
        except (ValueError, SyntaxError):
            try:
                valore = json.loads(testo.replace("'", '"'))
            except json.JSONDecodeError:
                return None
    return valore if isinstance(valore, dict) else None


def _richieste_formato_testo(testo: str) -> list[tuple[str, dict | None]]:
    """Blocchi ``TOOL: nome`` / ``PARAMS: {...}``; parametri ``None`` se malformati."""
    richieste = []
    trovati = list(_RE_TOOL.finditer(testo))
    for indice, trovato in enumerate(trovati):
        fine = trovati[indice + 1].start() if indice + 1 < len(trovati) else len(testo)
        segmento = testo[trovato.end():fine]
        nome = trovato.group(1).strip('.-')
        params = _RE_PARAMS.search(segmento)
        if params is None:
            graffa = segmento.find('{')
            prima = segmento[:graffa] if graffa >= 0 else ''
            if graffa >= 0 and not prima.strip(' \t\r\n`*:()'):
                oggetto = _estrai_oggetto(segmento, graffa)
                richieste.append((nome, _carica_parametri(oggetto) if oggetto else None))
            else:
                richieste.append((nome, {}))
            continue
        inizio = segmento.find('{', params.end())
        prima = segmento[params.end():inizio] if inizio >= 0 else ''
        if inizio < 0 or prima.strip(' \t\r\n`').lower() not in ('', 'json'):
            richieste.append((nome, None))  # PARAMS presente ma senza un oggetto JSON
            continue
        oggetto = _estrai_oggetto(segmento, inizio)
        richieste.append((nome, _carica_parametri(oggetto) if oggetto else None))
    return richieste


def _richieste_formato_json(testo: str) -> list[tuple[str, dict | None]]:
    """Riserva: ``{"tool"|"name": ..., "params"|"parameters"|"arguments": {...}}``."""
    richieste = []
    for trovato in _RE_TOOL_JSON.finditer(testo):
        inizio = testo.rfind('{', 0, trovato.start())
        oggetto = _estrai_oggetto(testo, inizio) if inizio >= 0 else None
        dati = _carica_parametri(oggetto) if oggetto else None
        if not dati:
            continue
        parametri = next((dati[k] for k in ('params', 'parameters', 'arguments', 'parametri')
                          if k in dati), {})
        if isinstance(parametri, str):
            parametri = _carica_parametri(parametri)
        richieste.append((trovato.group(1), parametri if isinstance(parametri, dict) else None))
    return richieste


def richieste_tool(testo: str) -> list[tuple[str, dict | None]]:
    """Tutte le richieste di tool nella risposta dell'LLM (parametri ``None`` = malformati)."""
    if not testo:
        return []
    richieste = _richieste_formato_testo(testo)
    return richieste or _richieste_formato_json(testo)


def parse_tool_request(testo: str) -> tuple[str, dict] | None:
    """Cerca ``TOOL: nome`` / ``PARAMS: {...}`` e restituisce ``(nome, parametri)``.

    Come nella lezione 20-03, ma tollera spazi e maiuscole, code fence, JSON
    con apici singoli, ``PARAMS`` assente (parametri vuoti) e il formato JSON
    ``{"tool": ..., "params": ...}``. Restituisce ``None`` se la risposta non è
    una richiesta di tool o se i parametri non sono leggibili.
    """
    for nome, parametri in richieste_tool(testo):
        if parametri is not None:
            return nome, parametri
    return None


# ---------------------------------------------------------------------------
# Chiamate all'LLM
# ---------------------------------------------------------------------------

def _num_predict() -> int:
    return int(config.get('chatbot.num_predict', NUM_PREDICT_PREDEFINITO))


@lru_cache(maxsize=16)
def _accetta_max_tokens(tipo: type) -> bool:
    """Vero se ``chiedi()`` del client accetta ``max_tokens`` (client vecchi o finti)."""
    try:
        return 'max_tokens' in inspect.signature(tipo.chiedi).parameters
    except (TypeError, ValueError, AttributeError):
        return False


def _chiedi(lavoro: _Lavoro, messaggi: list[dict], max_tokens: int | None = None) -> str:
    """Una chiamata LLM: crea il client solo se serve e conta le chiamate."""
    if lavoro.client is None:
        lavoro.client = crea_client()
    lavoro.chiamate_llm += 1
    limite = max_tokens if max_tokens is not None else _num_predict()
    if _accetta_max_tokens(type(lavoro.client)):
        risposta = lavoro.client.chiedi(messaggi, max_tokens=limite)
    else:
        risposta = lavoro.client.chiedi(messaggi)
    return (risposta or '').strip()


# ---------------------------------------------------------------------------
# Analista dati: ciclo dei tool
# ---------------------------------------------------------------------------

def _system(lavoro: _Lavoro) -> dict:
    """Messaggio di sistema comune a tutti i ruoli (prefisso identico = cache di Ollama)."""
    return {'role': 'system', 'content': prompts.SYSTEM_PROMPTS[lavoro.versione]}


def riscalda_modello(client: ClientLLM | None = None, prompt_version: str | None = None) -> float:
    """Carica il modello e il system prompt nella cache di Ollama; restituisce i secondi.

    Da chiamare all'apertura della pagina del chatbot (una volta, in
    ``st.cache_resource``): su CPU la prima lettura del system prompt costa
    circa 2 minuti, le domande successive la riusano.
    """
    inizio = time.perf_counter()
    lavoro = _Lavoro(client=client or crea_client(),
                     versione=prompts.versione_prompt(prompt_version))
    _chiedi(lavoro, [_system(lavoro), {'role': 'user', 'content': 'Rispondi solo: pronto'}],
            max_tokens=3)
    durata = time.perf_counter() - inizio
    logger.info(f'Modello riscaldato in {durata:.1f} s (prompt {lavoro.versione})')
    return durata


def _esegui_tool_sicuro(nome: str, parametri: dict | None) -> dict:
    """Whitelist + ``esegui_tool``; non solleva mai (lezione 20-04)."""
    if nome not in TOOLS:
        return {'errore': f"Tool '{nome}' non disponibile. Tool ammessi: {', '.join(TOOLS)}"}
    if parametri is None:
        return {'errore': 'PARAMS non è un oggetto JSON valido: usa PARAMS: {"comune": "Nome"}'}
    try:
        return esegui_tool(nome, parametri)
    except Exception as errore:  # noqa: BLE001 - l'errore diventa un'osservazione
        return {'errore': f'Errore del tool {nome}: {type(errore).__name__}: {errore}'}


def _json(valore: Any) -> str:
    """JSON compatto: su CPU ogni token del prompt costa tempo."""
    return json.dumps(valore, ensure_ascii=False, separators=(',', ':'))


def _messaggio_risultati(osservazioni: list[str]) -> str:
    return ('\n\n'.join(osservazioni)
            + '\n\nOra rispondi all\'utente usando solo questi risultati, oppure chiedi un altro '
              'tool se manca un dato.')


def _analista(domanda: str, lavoro: _Lavoro, storia: list[dict], contesto_misto: str = '') -> str:
    """Ciclo ``for iterazione in range(max_iterations)`` della lezione 20-03."""
    testo_utente = (prompts.ISTRUZIONI_MISTO.format(contesto=contesto_misto, domanda=domanda)
                    if contesto_misto else domanda)
    messaggi = [_system(lavoro), *storia, {'role': 'user', 'content': testo_utente}]
    max_iterazioni = int(config.get('chatbot.max_iterations', MAX_ITERAZIONI_PREDEFINITO))
    gia_eseguiti: dict[str, dict] = {}
    promemoria_inviato = False

    for iterazione in range(max_iterazioni):
        risposta = _chiedi(lavoro, messaggi)
        richieste = richieste_tool(risposta)
        if not richieste:
            if not lavoro.tool_chiamati and not promemoria_inviato and iterazione + 1 < max_iterazioni:
                # Domanda sui dati senza tool: si chiede una volta di consultarli.
                promemoria_inviato = True
                messaggi.append({'role': 'assistant', 'content': risposta})
                messaggi.append({'role': 'user', 'content': (
                    'Non hai chiamato nessun tool: per rispondere servono i dati. Chiama il '
                    'tool adatto con il formato TOOL/PARAMS.')})
                continue
            return risposta

        osservazioni = []
        for nome, parametri in richieste[:MAX_TOOL_PER_RISPOSTA]:
            chiave = f'{nome}:{json.dumps(parametri, sort_keys=True, ensure_ascii=False)}'
            if chiave in gia_eseguiti:
                risultato = gia_eseguiti[chiave]
                osservazioni.append(f'Risultato del tool {nome} (già fornito): '
                                    f'{_json(risultato)}')
                continue
            risultato = _esegui_tool_sicuro(nome, parametri)
            gia_eseguiti[chiave] = risultato
            lavoro.tool_chiamati.append({'nome': nome, 'parametri': parametri or {},
                                         'risultato': risultato})
            logger.info(f'[iterazione {iterazione + 1}] tool {nome} '
                        f'{"errore" if "errore" in risultato else "ok"}')
            osservazioni.append(f'Risultato del tool {nome}: '
                                f'{_json(risultato)}')
        messaggi.append({'role': 'assistant', 'content': risposta})
        messaggi.append({'role': 'user', 'content': _messaggio_risultati(osservazioni)})

    lavoro.avvisi.append(f'Raggiunto il limite di {max_iterazioni} iterazioni dell\'agente.')
    logger.warning(f'Analista fermato a max_iterations={max_iterazioni}')
    return ''


# ---------------------------------------------------------------------------
# Ricercatore: RAG (lezione 21-03)
# ---------------------------------------------------------------------------

def _recupera(domanda: str, lavoro: _Lavoro, k: int) -> list[dict] | None:
    """``cerca_documenti`` senza crash: ``None`` (con avviso) se l'indice non è usabile."""
    try:
        risultati = cerca_documenti(domanda, k=k)
    except FileNotFoundError:
        lavoro.avvisi.append('Indice dei documenti non disponibile: esegui '
                             '`python -m src.chatbot.build_knowledge_base`.')
        return None
    except ValueError as errore:
        lavoro.avvisi.append(f'Ricerca nei documenti non riuscita: {errore}')
        return None
    except LLMNonDisponibile:
        raise
    except Exception as errore:  # noqa: BLE001 - il RAG non deve mai rompere la risposta
        lavoro.avvisi.append(f'Ricerca nei documenti non riuscita ({type(errore).__name__}).')
        return None
    if not risultati:
        lavoro.avvisi.append('Nessun documento pertinente trovato nella knowledge base.')
        return None
    lavoro.chunk.extend(risultati)
    return risultati


def _domanda_per_ricerca(domanda: str, storia: list[dict]) -> str:
    """Per domande brevi di seguito ("perché?") aggiunge la domanda precedente."""
    if len(domanda.split()) >= 5:
        return domanda
    precedenti = [m['content'] for m in storia if m['role'] == 'user']
    return f'{precedenti[-1]} {domanda}' if precedenti else domanda


def _ricercatore(domanda: str, lavoro: _Lavoro, storia: list[dict]) -> str:
    """Recupera i chunk e chiede all'LLM di rispondere solo da quelli, citando le fonti."""
    top_k = int(config.get('chatbot.rag.top_k', TOP_K_PREDEFINITO))
    risultati = _recupera(_domanda_per_ricerca(domanda, storia), lavoro, top_k)
    if risultati is None:
        return prompts.RISPOSTA_INDICE_MANCANTE
    contenuto = prompts.MESSAGGIO_RICERCATORE.format(
        istruzioni=prompts.RICERCATORE_PROMPTS[lavoro.versione],
        contesto=formatta_contesto(_accorcia(risultati)), domanda=domanda)
    messaggi = [_system(lavoro), *storia, {'role': 'user', 'content': contenuto}]
    return _chiedi(lavoro, messaggi)


def _accorcia(risultati: list[dict], parole: int = PAROLE_CHUNK_MISTO) -> list[dict]:
    """Chunk accorciati per il percorso misto: prompt più corto, meno tempo su CPU."""
    accorciati = []
    for r in risultati:
        testo = str(r['testo']).split()
        accorciati.append({**r, 'testo': ' '.join(testo[:parole]) + (' …' if len(testo) > parole else '')})
    return accorciati


def _misto(domanda: str, lavoro: _Lavoro, storia: list[dict]) -> str:
    """Documenti recuperati (senza LLM) + Analista che li usa insieme ai tool."""
    risultati = _recupera(domanda, lavoro, TOP_K_MISTO)
    contesto = formatta_contesto(_accorcia(risultati)) if risultati else ''
    return _analista(domanda, lavoro, storia, contesto_misto=contesto)


# ---------------------------------------------------------------------------
# Revisore in Python
# ---------------------------------------------------------------------------

_RE_NUMERO_RISPOSTA = re.compile(r'(?<![\w.,])[-−]?\d+(?:[.,]\d+)*(?![\w])')
_RE_NUMERO_DATI = re.compile(r'\d+(?:[.,]\d+)*')
_RE_ELENCO_NUMERATO = re.compile(r'^\s*\d+[.)]\s+', re.MULTILINE)


def _valori_possibili(token: str) -> list[tuple[float, int]]:
    """Interpretazioni di un numero scritto (virgola o punto decimale, punto delle migliaia).

    Restituisce coppie ``(valore assoluto, decimali)``.
    """
    token = token.lstrip('-−')
    candidati: list[tuple[float, int]] = []
    if ',' in token and '.' in token:
        intero, _, decimale = token.replace('.', '').partition(',')
        candidati.append((float(f'{intero}.{decimale}'), len(decimale)))
    elif ',' in token:
        parti = token.split(',')
        if len(parti) == 2:
            candidati.append((float('.'.join(parti)), len(parti[1])))
    elif '.' in token:
        parti = token.split('.')
        if len(parti) == 2:
            candidati.append((float(token), len(parti[1])))
        if all(len(p) == 3 for p in parti[1:]):
            candidati.append((float(''.join(parti)), 0))
    else:
        candidati.append((float(token), 0))
    return candidati


def numeri_nel_testo(testo: str) -> list[str]:
    """Numeri scritti in una risposta (esclusi i numeri degli elenchi puntati)."""
    return _RE_NUMERO_RISPOSTA.findall(_RE_ELENCO_NUMERATO.sub('', testo or ''))


def _numeri_di_riferimento(testi: list[str]) -> set[float]:
    numeri = set(NUMERI_SEMPRE_AMMESSI)
    for testo in testi:
        for token in _RE_NUMERO_DATI.findall(testo):
            numeri.update(valore for valore, _ in _valori_possibili(token))
    return numeri


def _supportato(token: str, riferimenti: set[float]) -> bool:
    """Vero se il numero coincide con un riferimento, a meno dell'arrotondamento scritto."""
    for valore, decimali in _valori_possibili(token):
        tolleranza = 0.5 * 10 ** (-decimali) + 1e-9
        if any(abs(valore - r) <= tolleranza for r in riferimenti):
            return True
    return False


def numeri_non_supportati(testo: str, tool_chiamati: list[dict], chunk: list[dict],
                          domanda: str = '') -> list[str]:
    """Numeri della risposta assenti dai risultati dei tool, dai chunk e dalla domanda."""
    testi = [json.dumps(t.get('risultato', {}), ensure_ascii=False) for t in tool_chiamati]
    testi += [str(c.get('testo', '')) for c in chunk]
    testi.append(domanda)
    riferimenti = _numeri_di_riferimento(testi)
    mancanti = []
    for token in numeri_nel_testo(testo):
        if not _supportato(token, riferimenti) and token not in mancanti:
            mancanti.append(token)
    return mancanti


def _dati_per_revisore(lavoro: _Lavoro) -> str:
    righe = [f'Risultato del tool {t["nome"]}: {_json(t["risultato"])}'
             for t in lavoro.tool_chiamati]
    if lavoro.chunk:
        righe.append(formatta_contesto(_accorcia(lavoro.chunk, 200)))
    return '\n\n'.join(righe)[:MAX_CARATTERI_DATI_REVISORE] or '(nessun dato)'


def _revisore(domanda: str, testo: str, percorso: str, lavoro: _Lavoro) -> str:
    """Controllo in Python; al massimo un passaggio LLM correttivo, poi un avviso.

    Scelta: se ci sono numeri non supportati e dei dati con cui confrontarli si
    prova **una** correzione (il modello ha i dati giusti davanti e di solito
    sistema l'errore); se la correzione non basta, si tiene la risposta
    migliore e si aggiunge un avviso di incertezza, così l'utente è avvisato.
    """
    if percorso in ('metodo', 'misto') and not lavoro.chunk:
        lavoro.avvisi.append(prompts.AVVISO_SENZA_FONTI)
    mancanti = numeri_non_supportati(testo, lavoro.tool_chiamati, lavoro.chunk, domanda)
    if not mancanti:
        return testo
    logger.info(f'Revisore: {len(mancanti)} numeri non supportati')
    if lavoro.tool_chiamati or lavoro.chunk:
        contenuto = prompts.MESSAGGIO_REVISORE.format(
            domanda=domanda, dati=_dati_per_revisore(lavoro), risposta=testo,
            numeri=', '.join(mancanti))
        corretta = _chiedi(lavoro, [_system(lavoro),
                                    {'role': 'user',
                                     'content': prompts.PROMPT_REVISORE + '\n\n' + contenuto}])
        if corretta and not richieste_tool(corretta):
            ancora = numeri_non_supportati(corretta, lavoro.tool_chiamati, lavoro.chunk, domanda)
            if len(ancora) <= len(mancanti):
                testo, mancanti = corretta, ancora
    if mancanti:
        lavoro.avvisi.append(prompts.AVVISO_INCERTEZZA.format(numeri=', '.join(mancanti)))
    return testo


# ---------------------------------------------------------------------------
# Funzione principale
# ---------------------------------------------------------------------------

def _fonti(chunk: list[dict]) -> list[dict]:
    fonti, viste = [], set()
    for c in chunk:
        chiave = (c.get('fonte'), c.get('sezione'))
        if chiave in viste:
            continue
        viste.add(chiave)
        fonti.append({'fonte': c.get('fonte'), 'sezione': c.get('sezione'),
                      'similarita': c.get('similarita')})
    return fonti


def esegui_agente(
    domanda: str,
    memoria: MemoriaConversazione | None = None,
    client: ClientLLM | None = None,
    prompt_version: str | None = None,
) -> RispostaAgente:
    """Risponde a una domanda passando per router, ruoli e Revisore.

    Non solleva per errori dei tool o del RAG (diventano osservazioni o
    avvisi); propaga invece ``LLMNonDisponibile``, che la pagina Streamlit
    mostra con le istruzioni per avviare Ollama. Se ``memoria`` è data, la
    domanda e la risposta vengono aggiunte alla storia.
    """
    inizio = time.perf_counter()
    versione = prompts.versione_prompt(prompt_version)
    lavoro = _Lavoro(client=client, versione=versione)
    storia = memoria.messaggi() if memoria is not None else []
    domanda = (domanda or '').strip()
    logger.info(f'Domanda ricevuta ({len(domanda)} caratteri), prompt {versione}')

    verificabile = True
    if not domanda:
        percorso, motivo, testo = 'fuori_ambito', None, prompts.RISPOSTA_DOMANDA_VUOTA
        verificabile = False
    else:
        percorso, motivo = _classifica_per_regole(domanda)
        if percorso is None:
            percorso = _instrada_con_llm(domanda, lavoro)
            motivo = 'generico'
        testo = ''

    if percorso == 'fuori_ambito' and domanda:
        testo = prompts.RIFIUTI.get(motivo or 'generico', prompts.RIFIUTI['generico'])
        verificabile = False
    elif percorso == 'dati':
        testo = _analista(domanda, lavoro, storia)
    elif percorso == 'metodo':
        testo = _ricercatore(domanda, lavoro, storia)
        verificabile = bool(lavoro.chunk)
    elif percorso == 'misto':
        testo = _misto(domanda, lavoro, storia)

    if percorso in ('dati', 'misto') and not testo:
        n = int(config.get('chatbot.max_iterations', MAX_ITERAZIONI_PREDEFINITO))
        testo = prompts.RISPOSTA_MAX_ITERAZIONI.format(n=n)
        verificabile = False
    if verificabile:
        testo = _revisore(domanda, testo, percorso, lavoro)
    elif percorso == 'metodo':
        lavoro.avvisi.append(prompts.AVVISO_SENZA_FONTI)

    if memoria is not None:
        memoria.aggiungi('user', SEGNAPOSTO_INJECTION if motivo == 'injection' else domanda)
        memoria.aggiungi('assistant', testo)

    durata = round(time.perf_counter() - inizio, 2)
    logger.info(f'Percorso {percorso}: {len(lavoro.tool_chiamati)} tool '
                f'({", ".join(t["nome"] for t in lavoro.tool_chiamati) or "nessuno"}), '
                f'{lavoro.chiamate_llm} chiamate LLM, {durata} s')
    return RispostaAgente(
        testo=testo,
        percorso=percorso,
        tool_chiamati=lavoro.tool_chiamati,
        fonti=_fonti(lavoro.chunk),
        avvisi=lavoro.avvisi,
        chiamate_llm=lavoro.chiamate_llm,
        durata_s=durata,
        prompt_version=versione,
    )
