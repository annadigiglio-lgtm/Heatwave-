"""Client LLM unico del chatbot "Assistente climatico".

Tutti gli altri moduli del chatbot (agente, RAG, pagina Streamlit) parlano con
il modello **solo** attraverso questo file, come nel "wrapper universale"
della lezione 13-05: il provider (Ollama in locale oppure Anthropic) resta
nascosto dietro la stessa interfaccia ``chiedi()`` / ``embed()``.

Regole di sicurezza (lezione 13-03): nessuna chiave nel codice. La chiave
Anthropic si legge solo dall'ambiente (``.env``, caricato da
``src/utils/config.py``); i nomi dei modelli stanno in ``config.yaml``.

Per i test e gli smoke test delle pagine c'è ``FakeLLM``, che non usa la rete;
``crea_client()`` lo restituisce se ``HEATWAVE_FAKE_LLM=1``.

Streaming (lezione 14-05): ``chiedi(..., on_token=f)`` chiama ``f(pezzo)`` per
ogni pezzo di testo appena generato e restituisce comunque il testo completo.
Senza ``on_token`` il comportamento è quello di sempre (una sola risposta).
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Callable, Protocol, runtime_checkable

import httpx
import ollama

from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

OLLAMA_HOST_PREDEFINITO = 'http://localhost:11434'
TIMEOUT_STATO_SECONDI = 5.0
BLOCCO_EMBEDDING = 32
DIMENSIONE_EMBEDDING_FAKE = 256
MAX_TOKENS_ANTHROPIC = 1024
TEMPERATURA_PREDEFINITA = 0.2
KEEP_ALIVE_PREDEFINITO = '30m'
TIMEOUT_RISPOSTA_PREDEFINITO = 180.0  # secondi; su CPU una risposta lunga può superare il minuto
TENTATIVI_GEMINI = 2  # tentativi totali per richiesta (1 + 1 ripetizione)
VARIABILE_FAKE = 'HEATWAVE_FAKE_LLM'
PROVIDER = ('ollama', 'gemini', 'anthropic')
RISPOSTA_FAKE_PREDEFINITA = 'Risposta di prova del FakeLLM.'

Messaggi = list[dict]
FunzioneEmbedding = Callable[[list[str]], list[list[float]]]
CallbackToken = Callable[[str], None]


class LLMNonDisponibile(Exception):
    """Il modello non può rispondere; il messaggio dice all'utente cosa fare."""


@runtime_checkable
class ClientLLM(Protocol):
    """Interfaccia comune a tutti i client LLM del progetto."""

    def chiedi(
        self,
        messaggi: Messaggi,
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_token: CallbackToken | None = None,
    ) -> str:
        """Invia una conversazione e restituisce il testo della risposta.

        ``max_tokens`` (facoltativo) limita la lunghezza della risposta;
        ``on_token`` (facoltativo) riceve i pezzi del testo man mano.
        """
        ...

    def embed(self, testi: list[str]) -> list[list[float]]:
        """Restituisce un vettore di embedding per ogni testo."""
        ...


# ---------------------------------------------------------------------------
# Funzioni di supporto
# ---------------------------------------------------------------------------

def _ollama_host() -> str:
    """Indirizzo del server Ollama: ``OLLAMA_HOST`` oppure il default locale."""
    return os.getenv('OLLAMA_HOST') or OLLAMA_HOST_PREDEFINITO


def _modello_chat() -> str:
    """Modello di chat Ollama configurato in ``chatbot.model``."""
    return str(config.get('chatbot.model', 'qwen2.5:7b'))


def _modello_embedding() -> str:
    """Modello di embedding configurato in ``chatbot.rag.embedding_model``."""
    return str(config.get('chatbot.rag.embedding_model', 'bge-m3'))


def _temperatura(temperature: float | None) -> float:
    """Usa la temperatura richiesta oppure quella di ``chatbot.temperature``."""
    if temperature is not None:
        return float(temperature)
    return float(config.get('chatbot.temperature', TEMPERATURA_PREDEFINITA))


def _valida_messaggi(messaggi: Messaggi) -> None:
    """Controlla che i messaggi abbiano il formato ``{"role", "content"}``."""
    if not messaggi:
        raise ValueError('La lista dei messaggi è vuota')
    for indice, messaggio in enumerate(messaggi):
        if not isinstance(messaggio, dict) or 'role' not in messaggio or 'content' not in messaggio:
            raise ValueError(
                f'Messaggio {indice} non valido: servono le chiavi "role" e "content"'
            )


def _a_blocchi(testi: list[str], dimensione: int = BLOCCO_EMBEDDING) -> list[list[str]]:
    """Divide i testi in blocchi di ``dimensione`` elementi."""
    return [testi[i:i + dimensione] for i in range(0, len(testi), dimensione)]


def _modello_presente(nome: str, disponibili: set[str]) -> bool:
    """Vero se ``nome`` è tra i modelli scaricati (``bge-m3`` = ``bge-m3:latest``)."""
    if nome in disponibili:
        return True
    return ':' not in nome and f'{nome}:latest' in disponibili


def _errore_server_ollama(host: str) -> LLMNonDisponibile:
    """Errore per server Ollama spento o non raggiungibile."""
    return LLMNonDisponibile(
        f'Il server Ollama non risponde su {host}. Avvia Ollama '
        "(apri l'app Ollama oppure esegui `ollama serve`) e riprova."
    )


def _timeout_risposta() -> float:
    """Secondi massimi di attesa di una risposta (``chatbot.request_timeout``)."""
    return float(config.get('chatbot.request_timeout', TIMEOUT_RISPOSTA_PREDEFINITO))


def _errore_timeout(modello: str, secondi: float | None) -> LLMNonDisponibile:
    """Errore per una risposta che non arriva entro il tempo massimo."""
    attesa = f' entro {secondi:.0f} secondi' if secondi else ''
    return LLMNonDisponibile(
        f'Il modello "{modello}" non ha risposto{attesa}. Su CPU le risposte lunghe '
        'sono lente: riprova con una domanda più breve, aumenta chatbot.request_timeout '
        'in config.yaml oppure usa un modello più leggero (es. llama3.2).'
    )


def _errore_modello_mancante(modello: str) -> LLMNonDisponibile:
    """Errore per modello non ancora scaricato in Ollama."""
    return LLMNonDisponibile(
        f'Il modello "{modello}" non è scaricato in Ollama. '
        f'Esegui `ollama pull {modello}` e riprova.'
    )


def _traduci_errore_ollama(
    errore: Exception, modello: str, host: str, timeout: float | None = None
) -> LLMNonDisponibile:
    """Converte le eccezioni di Ollama/httpx in un ``LLMNonDisponibile`` chiaro.

    - timeout in lettura/scrittura di httpx → il modello è troppo lento
      (``ConnectTimeout`` invece vuol dire che il server non c'è);
    - ``ConnectionError`` (sollevata da ``ollama`` su ``httpx.ConnectError``) o
      altri errori di trasporto httpx → server spento;
    - ``ResponseError`` con codice 404 o testo "not found" → modello mancante;
    - qualunque altra ``ResponseError`` → errore generico con il dettaglio.
    """
    if isinstance(errore, httpx.TimeoutException) and not isinstance(errore, httpx.ConnectTimeout):
        return _errore_timeout(modello, timeout)
    if isinstance(errore, (ConnectionError, httpx.TransportError)):
        return _errore_server_ollama(host)
    if isinstance(errore, ollama.ResponseError):
        if errore.status_code == 404 or 'not found' in str(errore.error).lower():
            return _errore_modello_mancante(modello)
        return LLMNonDisponibile(f'Ollama ha restituito un errore: {errore}')
    return LLMNonDisponibile(f'Errore inatteso con Ollama: {errore}')


# ---------------------------------------------------------------------------
# Client Ollama (provider predefinito)
# ---------------------------------------------------------------------------

class OllamaClient:
    """Client per il server Ollama locale (chat ed embedding)."""

    def __init__(
        self,
        model: str | None = None,
        embedding_model: str | None = None,
        host: str | None = None,
        client: ollama.Client | None = None,
        keep_alive: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """Prepara il client; ``client`` permette di iniettare un mock nei test.

        ``timeout`` (default ``chatbot.request_timeout``, 180 s) è l'attesa
        massima di una risposta: senza, una generazione lenta su CPU bloccherebbe
        l'app senza limite.

        ``keep_alive`` (default ``chatbot.keep_alive`` o ``"30m"``) tiene il
        modello in RAM tra una domanda e l'altra: su CPU il primo caricamento
        costa circa 44 s.
        """
        self.model = model or _modello_chat()
        self.keep_alive = keep_alive or str(config.get('chatbot.keep_alive', KEEP_ALIVE_PREDEFINITO))
        self.embedding_model = embedding_model or _modello_embedding()
        self.host = host or _ollama_host()
        self.timeout = float(timeout) if timeout is not None else _timeout_risposta()
        self._client = client or ollama.Client(host=self.host, timeout=self.timeout)

    def chiedi(
        self,
        messaggi: Messaggi,
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_token: CallbackToken | None = None,
    ) -> str:
        """Invia i messaggi a ``ollama.chat`` e restituisce il testo.

        ``max_tokens`` diventa l'opzione Ollama ``num_predict``. Con
        ``on_token`` la chiamata usa ``stream=True`` (lezione 14-05): ogni
        pezzo generato va subito a ``on_token`` e alla fine si restituisce
        il testo completo, identico a quello senza streaming.
        """
        _valida_messaggi(messaggi)
        opzioni: dict = {'temperature': _temperatura(temperature)}
        if max_tokens is not None:
            opzioni['num_predict'] = int(max_tokens)
        parametri = {
            'model': self.model,
            'messages': messaggi,
            'options': opzioni,
            'keep_alive': self.keep_alive,
        }
        try:
            if on_token is None:
                risposta = self._client.chat(**parametri)
                return risposta.message.content or ''
            pezzi: list[str] = []
            # Lo stream è un generatore: gli errori di rete possono arrivare
            # anche durante la lettura, quindi il ciclo sta dentro il try.
            for parte in self._client.chat(**parametri, stream=True):
                messaggio = getattr(parte, 'message', None)
                pezzo = (getattr(messaggio, 'content', '') if messaggio is not None else '') or ''
                if pezzo:
                    pezzi.append(pezzo)
                    on_token(pezzo)
            return ''.join(pezzi)
        except (ConnectionError, httpx.TransportError, ollama.ResponseError) as errore:
            logger.warning(f'Chat Ollama fallita: {errore}')
            raise _traduci_errore_ollama(errore, self.model, self.host, self.timeout) from errore

    def embed(self, testi: list[str]) -> list[list[float]]:
        """Calcola gli embedding con ``ollama.embed``, a blocchi di 32 testi."""
        vettori: list[list[float]] = []
        for blocco in _a_blocchi(list(testi)):
            try:
                risposta = self._client.embed(model=self.embedding_model, input=blocco)
            except (ConnectionError, httpx.TransportError, ollama.ResponseError) as errore:
                logger.warning(f'Embedding Ollama fallito: {errore}')
                raise _traduci_errore_ollama(
                    errore, self.embedding_model, self.host, self.timeout
                ) from errore
            vettori.extend([float(x) for x in vettore] for vettore in risposta.embeddings)
        return vettori


# ---------------------------------------------------------------------------
# Client Anthropic (facoltativo)
# ---------------------------------------------------------------------------

def _separa_system(messaggi: Messaggi) -> tuple[str, Messaggi]:
    """Separa i messaggi ``system`` dagli altri: Anthropic li vuole a parte."""
    system = [str(m['content']) for m in messaggi if m['role'] == 'system']
    conversazione = [
        {'role': m['role'], 'content': m['content']} for m in messaggi if m['role'] != 'system'
    ]
    return '\n\n'.join(system), conversazione


class AnthropicClient:
    """Client per l'API Anthropic; la chiave arriva solo da ``.env``."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        max_tokens: int = MAX_TOKENS_ANTHROPIC,
        client: object | None = None,
    ) -> None:
        """Controlla modello e chiave; ``client`` permette di iniettare un mock."""
        self.model = model or str(config.get('chatbot.anthropic_model', '') or '')
        if not self.model:
            raise LLMNonDisponibile(
                'Modello Anthropic non configurato: imposta chatbot.anthropic_model '
                'in config.yaml.'
            )
        self.max_tokens = max_tokens
        if client is not None:
            self._client = client
            return
        chiave = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not chiave:
            raise LLMNonDisponibile(
                'Chiave Anthropic assente: imposta ANTHROPIC_API_KEY nel file .env '
                '(mai nel codice).'
            )
        import anthropic  # import locale: serve solo a chi usa questo provider

        self._client = anthropic.Anthropic(api_key=chiave)

    def chiedi(
        self,
        messaggi: Messaggi,
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_token: CallbackToken | None = None,
    ) -> str:
        """Invia i messaggi a ``messages.create`` con il system prompt separato.

        Nessuno streaming vero (provider facoltativo): se c'è ``on_token``
        riceve il testo intero in un solo pezzo.
        """
        _valida_messaggi(messaggi)
        system, conversazione = _separa_system(messaggi)
        parametri = {
            'model': self.model,
            'max_tokens': int(max_tokens) if max_tokens is not None else self.max_tokens,
            'messages': conversazione,
            'temperature': _temperatura(temperature),
        }
        if system:
            parametri['system'] = system
        try:
            risposta = self._client.messages.create(**parametri)
        except Exception as errore:
            logger.warning(f'Chiamata Anthropic fallita: {errore}')
            raise _traduci_errore_anthropic(errore, self.model) from errore
        testo = ''.join(
            blocco.text for blocco in risposta.content if getattr(blocco, 'type', '') == 'text'
        )
        if on_token is not None and testo:
            on_token(testo)
        return testo

    def embed(self, testi: list[str]) -> list[list[float]]:
        """Non supportato: gli embedding del progetto usano sempre Ollama."""
        raise LLMNonDisponibile(
            'Il provider Anthropic non calcola embedding: nel progetto gli embedding '
            f'usano sempre Ollama ({_modello_embedding()}). Usa OllamaClient().embed().'
        )


def _traduci_errore_anthropic(errore: Exception, modello: str) -> LLMNonDisponibile:
    """Converte le eccezioni dell'SDK Anthropic in messaggi chiari."""
    import anthropic

    if isinstance(errore, anthropic.AuthenticationError):
        return LLMNonDisponibile('Chiave Anthropic non valida: controlla ANTHROPIC_API_KEY in .env.')
    if isinstance(errore, anthropic.NotFoundError):
        return LLMNonDisponibile(
            f'Modello Anthropic "{modello}" non trovato: controlla chatbot.anthropic_model.'
        )
    if isinstance(errore, anthropic.APIConnectionError):
        return LLMNonDisponibile("Impossibile raggiungere l'API Anthropic: controlla la connessione.")
    return LLMNonDisponibile(f"Errore dell'API Anthropic: {errore}")


# ---------------------------------------------------------------------------
# Client Gemini (API Google, piano gratuito, lezione 13-02)
# ---------------------------------------------------------------------------

def _chiave_gemini() -> str | None:
    """Chiave da ``GOOGLE_API_KEY`` (come nel corso) o ``GEMINI_API_KEY``."""
    return os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')


def _modello_gemini() -> str:
    return str(config.get('chatbot.gemini_model', '') or '')


def _contenuti_gemini(messaggi: Messaggi) -> tuple[str, list[dict]]:
    """System prompt separato e ruoli Gemini: ``assistant`` diventa ``model``."""
    system, conversazione = _separa_system(messaggi)
    contenuti = [
        {'role': 'model' if m['role'] == 'assistant' else 'user', 'parts': [{'text': str(m['content'])}]}
        for m in conversazione
    ]
    return system, contenuti


class GeminiClient:
    """Client per l'API Gemini di Google; la chiave arriva solo da ``.env``.

    Le risposte arrivano in pochi secondi invece dei minuti di Ollama su CPU.
    Il "ragionamento" interno dei modelli Gemini recenti consuma il limite di
    token in uscita: ``chatbot.gemini_thinking_budget`` (default 0) lo
    disattiva, così le risposte brevi non arrivano vuote. Gli embedding del
    RAG restano su Ollama (``bge-m3``), lo stesso modello con cui è costruito
    l'indice.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        client: object | None = None,
        thinking_budget: int | None = None,
        timeout: float | None = None,
    ) -> None:
        """Controlla modello e chiave; ``client`` permette di iniettare un mock."""
        self.model = model or _modello_gemini()
        if not self.model:
            raise LLMNonDisponibile(
                'Modello Gemini non configurato: imposta chatbot.gemini_model in config.yaml.'
            )
        budget = thinking_budget if thinking_budget is not None else config.get(
            'chatbot.gemini_thinking_budget', 0)
        self.thinking_budget = None if budget is None or str(budget) == '' else int(budget)
        self.timeout = float(timeout) if timeout is not None else _timeout_risposta()
        if client is not None:
            self._client = client
            return
        chiave = api_key or _chiave_gemini()
        if not chiave:
            raise LLMNonDisponibile(
                'Chiave Gemini assente: crea una chiave gratuita su aistudio.google.com e '
                'imposta GOOGLE_API_KEY nel file .env (mai nel codice).'
            )
        from google import genai  # import locale: serve solo a chi usa questo provider
        from google.genai import types
        self._client = genai.Client(
            api_key=chiave,
            http_options=types.HttpOptions(
                timeout=int(self.timeout * 1000),
                # Senza limite la libreria ritenta in silenzio i 429/5xx anche per
                # minuti (visto con un modello sovraccarico): meglio un errore chiaro.
                retry_options=types.HttpRetryOptions(attempts=TENTATIVI_GEMINI),
            ))

    def _configurazione(self, system: str, temperature: float | None, max_tokens: int | None):
        from google.genai import types
        parametri: dict = {'temperature': _temperatura(temperature)}
        if system:
            parametri['system_instruction'] = system
        if max_tokens is not None:
            parametri['max_output_tokens'] = int(max_tokens)
        if self.thinking_budget is not None:
            parametri['thinking_config'] = types.ThinkingConfig(thinking_budget=self.thinking_budget)
        return types.GenerateContentConfig(**parametri)

    def chiedi(
        self,
        messaggi: Messaggi,
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_token: CallbackToken | None = None,
    ) -> str:
        """``generate_content`` (o ``generate_content_stream`` con ``on_token``)."""
        _valida_messaggi(messaggi)
        system, contenuti = _contenuti_gemini(messaggi)
        configurazione = self._configurazione(system, temperature, max_tokens)
        try:
            if on_token is None:
                risposta = self._client.models.generate_content(
                    model=self.model, contents=contenuti, config=configurazione)
                return risposta.text or ''
            pezzi = []
            for parte in self._client.models.generate_content_stream(
                    model=self.model, contents=contenuti, config=configurazione):
                testo = getattr(parte, 'text', None) or ''
                if testo:
                    pezzi.append(testo)
                    on_token(testo)
            return ''.join(pezzi)
        except LLMNonDisponibile:
            raise
        except Exception as errore:
            logger.warning(f'Chiamata Gemini fallita: {type(errore).__name__}')
            raise _traduci_errore_gemini(errore, self.model, self.timeout) from errore

    def embed(self, testi: list[str]) -> list[list[float]]:
        """Non usato: gli embedding del progetto usano sempre Ollama."""
        raise LLMNonDisponibile(
            'Nel progetto gli embedding usano sempre Ollama '
            f'({_modello_embedding()}), lo stesso modello con cui è costruito l\'indice RAG.'
        )


def _traduci_errore_gemini(errore: Exception, modello: str, timeout: float) -> LLMNonDisponibile:
    """Converte le eccezioni dell'SDK Gemini in messaggi chiari."""
    if isinstance(errore, (httpx.TimeoutException,)):
        return _errore_timeout(modello, timeout)
    if isinstance(errore, (httpx.TransportError, ConnectionError)):
        return LLMNonDisponibile("Impossibile raggiungere l'API Gemini: controlla la connessione a internet.")
    codice = getattr(errore, 'code', None)
    testo = str(errore)
    if codice == 429:
        return LLMNonDisponibile(
            'Limite del piano gratuito Gemini raggiunto (troppe richieste): attendi circa un minuto '
            'e riprova, oppure passa al modello locale Ollama nella barra laterale.')
    if codice in (401, 403) or 'API key not valid' in testo or 'API_KEY_INVALID' in testo:
        return LLMNonDisponibile('Chiave Gemini non valida: controlla GOOGLE_API_KEY nel file .env.')
    if codice == 404:
        return LLMNonDisponibile(
            f'Modello Gemini "{modello}" non trovato: controlla chatbot.gemini_model in config.yaml.')
    if codice is not None and codice >= 500:
        return LLMNonDisponibile('Servizio Gemini momentaneamente non disponibile: riprova tra poco.')
    return LLMNonDisponibile(f"Errore dell'API Gemini: {testo}")


# ---------------------------------------------------------------------------
# FakeLLM per i test
# ---------------------------------------------------------------------------

def embedding_bag_of_words(
    testi: list[str], dimensione: int = DIMENSIONE_EMBEDDING_FAKE
) -> list[list[float]]:
    """Embedding finto e deterministico: bag-of-words con hashing, norma L2 = 1.

    Ogni parola (minuscola) viene assegnata a una posizione del vettore con
    MD5 (stabile tra esecuzioni, a differenza di ``hash()``). Testi con parole
    in comune hanno quindi similarità coseno maggiore. Un testo senza parole
    produce il vettore nullo.
    """
    vettori = []
    for testo in testi:
        vettore = [0.0] * dimensione
        for parola in re.findall(r'\w+', testo.lower()):
            indice = int(hashlib.md5(parola.encode('utf-8')).hexdigest(), 16) % dimensione
            vettore[indice] += 1.0
        norma = math.sqrt(sum(x * x for x in vettore))
        vettori.append([x / norma for x in vettore] if norma else vettore)
    return vettori


def pezzi_di_testo(testo: str) -> list[str]:
    """Divide un testo in pezzi "parola + spazi"; unendoli si riottiene il testo."""
    return re.findall(r'\s+|\S+\s*', testo or '')


class FakeLLM:
    """LLM finto: risposte predefinite in sequenza, nessuna rete.

    Registra in ``.chiamate`` una copia dei messaggi di ogni chiamata. Finite
    le risposte, ripete l'ultima (utile negli smoke test con più turni).
    """

    def __init__(
        self,
        risposte: list[str],
        embedding_fn: FunzioneEmbedding | None = None,
    ) -> None:
        """Salva le risposte e l'eventuale funzione di embedding personalizzata."""
        if not risposte:
            raise ValueError('FakeLLM richiede almeno una risposta predefinita')
        self.risposte = list(risposte)
        self.embedding_fn = embedding_fn or embedding_bag_of_words
        self.chiamate: list[Messaggi] = []
        self.temperature: list[float | None] = []
        self.max_tokens: list[int | None] = []
        self._indice = 0

    def chiedi(
        self,
        messaggi: Messaggi,
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_token: CallbackToken | None = None,
    ) -> str:
        """Restituisce la prossima risposta e registra i messaggi ricevuti.

        Con ``on_token`` "streamma" la risposta a pezzi (una parola con gli
        spazi che la seguono), come farebbe Ollama.
        """
        _valida_messaggi(messaggi)
        self.chiamate.append([dict(m) for m in messaggi])
        self.temperature.append(temperature)
        self.max_tokens.append(max_tokens)
        risposta = self.risposte[min(self._indice, len(self.risposte) - 1)]
        self._indice += 1
        if on_token is not None:
            for pezzo in pezzi_di_testo(risposta):
                on_token(pezzo)
        return risposta

    def embed(self, testi: list[str]) -> list[list[float]]:
        """Embedding deterministico (di default bag-of-words con hashing)."""
        return self.embedding_fn(list(testi))


# ---------------------------------------------------------------------------
# Factory e funzioni di comodo
# ---------------------------------------------------------------------------

def _fake_attivo() -> bool:
    """Vero se la variabile ``HEATWAVE_FAKE_LLM`` vale ``1``."""
    return os.getenv(VARIABILE_FAKE, '').strip() == '1'


def crea_client(provider: str | None = None) -> ClientLLM:
    """Crea il client per il provider indicato o per ``chatbot.provider``.

    Con ``HEATWAVE_FAKE_LLM=1`` restituisce sempre un ``FakeLLM``.

    Raises:
        ValueError: provider sconosciuto.
        LLMNonDisponibile: configurazione Anthropic incompleta.
    """
    if _fake_attivo():
        logger.info('HEATWAVE_FAKE_LLM=1: uso FakeLLM')
        return FakeLLM([RISPOSTA_FAKE_PREDEFINITA])
    scelto = (provider or str(config.get('chatbot.provider', 'ollama'))).strip().lower()
    if scelto == 'ollama':
        return OllamaClient()
    if scelto == 'anthropic':
        return AnthropicClient()
    if scelto == 'gemini':
        return GeminiClient()
    raise ValueError(f'Provider LLM non riconosciuto: "{scelto}" (usa {", ".join(PROVIDER)})')


def chiedi_llm(
    messaggi: Messaggi, temperature: float | None = None, max_tokens: int | None = None
) -> str:
    """Wrapper universale (lezione 13-05): una domanda, il provider configurato."""
    return crea_client().chiedi(messaggi, temperature=temperature, max_tokens=max_tokens)


def _modelli_ollama_scaricati(host: str) -> set[str]:
    """Nomi dei modelli scaricati nel server Ollama (solleva se non risponde)."""
    client = ollama.Client(host=host, timeout=TIMEOUT_STATO_SECONDI)
    return {m.model for m in client.list().models if m.model}


def _stato_gemini() -> tuple[bool, str]:
    """Controlla chiave e modello Gemini senza chiamare l'API."""
    try:
        client = GeminiClient()
    except LLMNonDisponibile as errore:
        return False, str(errore)
    return True, f'Gemini configurato ({client.model})'


def _stato_anthropic() -> tuple[bool, str]:
    """Controlla chiave e modello Anthropic senza chiamare l'API."""
    try:
        client = AnthropicClient()
    except LLMNonDisponibile as errore:
        return False, str(errore)
    return True, f'Anthropic configurato ({client.model})'


def stato_llm(provider: str | None = None) -> tuple[bool, str]:
    """Stato del chatbot per la sidebar: ``(ok, messaggio)``. Non solleva mai.

    Controlla che il server Ollama risponda e che i modelli di chat e di
    embedding configurati risultino scaricati. Con provider Anthropic
    controlla chiave e modello e, per gli embedding, comunque Ollama.
    """
    try:
        if _fake_attivo():
            return True, 'FakeLLM attivo (HEATWAVE_FAKE_LLM=1): nessun modello reale'
        provider = (provider or str(config.get('chatbot.provider', 'ollama'))).strip().lower()
        richiesti = [_modello_embedding()]
        if provider in ('anthropic', 'gemini'):
            ok, messaggio = _stato_anthropic() if provider == 'anthropic' else _stato_gemini()
            if not ok:
                return False, messaggio
        elif provider == 'ollama':
            richiesti.insert(0, _modello_chat())
        else:
            return False, f'Provider LLM non riconosciuto: "{provider}"'

        host = _ollama_host()
        try:
            disponibili = _modelli_ollama_scaricati(host)
        except (ConnectionError, httpx.HTTPError, ollama.ResponseError) as errore:
            return False, str(_traduci_errore_ollama(errore, richiesti[0], host))

        mancanti = [m for m in richiesti if not _modello_presente(m, disponibili)]
        if mancanti:
            comandi = ' e '.join(f'`ollama pull {m}`' for m in mancanti)
            return False, f'Modelli non scaricati: {", ".join(mancanti)}. Esegui {comandi}.'
        return True, f'LLM pronto: {provider}, modelli {", ".join(richiesti)} disponibili'
    except Exception as errore:  # la sidebar non deve mai rompersi
        logger.warning(f'stato_llm: errore inatteso {errore}')
        return False, f'Stato LLM non verificabile: {errore}'
