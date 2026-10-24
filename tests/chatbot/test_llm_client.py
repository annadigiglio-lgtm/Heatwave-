"""Test del client LLM: solo mock, nessuna rete e nessun Ollama reale."""

import json
import math
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import ollama
import pytest

from src.chatbot import llm_client
from src.chatbot.llm_client import (
    AnthropicClient,
    FakeLLM,
    LLMNonDisponibile,
    OllamaClient,
    chiedi_llm,
    crea_client,
    stato_llm,
)

MESSAGGI = [
    {'role': 'system', 'content': 'Sei un assistente climatico.'},
    {'role': 'user', 'content': 'Quante ondate di calore a Torino?'},
]


@pytest.fixture(autouse=True)
def senza_fake(monkeypatch):
    """Ogni test parte senza HEATWAVE_FAKE_LLM e senza chiave Anthropic reale."""
    monkeypatch.delenv('HEATWAVE_FAKE_LLM', raising=False)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)


def _client_ollama_finto(contenuto='Ciao!'):
    finto = MagicMock()
    finto.chat.return_value = ollama.ChatResponse(
        message=ollama.Message(role='assistant', content=contenuto)
    )
    return finto


# --- Ollama -----------------------------------------------------------------

def test_ollama_risposta_normale():
    finto = _client_ollama_finto('Ciao!')
    client = OllamaClient(model='qwen2.5:7b', embedding_model='bge-m3', client=finto)

    assert client.chiedi(MESSAGGI) == 'Ciao!'
    kwargs = finto.chat.call_args.kwargs
    assert kwargs['model'] == 'qwen2.5:7b'
    assert kwargs['messages'] == MESSAGGI


def test_ollama_temperatura_in_options():
    finto = _client_ollama_finto()
    client = OllamaClient(model='m', client=finto)

    client.chiedi(MESSAGGI, temperature=0.7)
    assert finto.chat.call_args.kwargs['options'] == {'temperature': 0.7}


def test_ollama_temperatura_predefinita_da_config():
    finto = _client_ollama_finto()
    OllamaClient(model='m', client=finto).chiedi(MESSAGGI)
    assert finto.chat.call_args.kwargs['options']['temperature'] == pytest.approx(0.2)


@pytest.mark.parametrize('errore', [
    ConnectionError('Failed to connect to Ollama'),
    httpx.ConnectTimeout('timeout'),
])
def test_ollama_server_spento(errore):
    finto = MagicMock()
    finto.chat.side_effect = errore
    client = OllamaClient(model='m', host='http://localhost:11434', client=finto)

    with pytest.raises(LLMNonDisponibile, match='Avvia Ollama'):
        client.chiedi(MESSAGGI)


def test_ollama_timeout_in_lettura_non_e_server_spento():
    """Una generazione troppo lenta su CPU dà un messaggio dedicato, non "avvia Ollama"."""
    finto = MagicMock()
    finto.chat.side_effect = httpx.ReadTimeout('timed out')
    client = OllamaClient(model='qwen2.5:7b', client=finto, timeout=7)

    with pytest.raises(LLMNonDisponibile, match='non ha risposto entro 7 secondi') as info:
        client.chiedi(MESSAGGI)
    assert 'Avvia Ollama' not in str(info.value)


def test_ollama_client_reale_ha_timeout():
    client = OllamaClient(model='m', host='http://localhost:11434', timeout=12)
    assert client.timeout == 12
    assert client._client._client.timeout.read == 12


def test_ollama_modello_mancante_suggerisce_pull():
    finto = MagicMock()
    finto.chat.side_effect = ollama.ResponseError(
        'model "qwen2.5:7b" not found, try pulling it first', 404
    )
    client = OllamaClient(model='qwen2.5:7b', client=finto)

    with pytest.raises(LLMNonDisponibile, match=r'ollama pull qwen2\.5:7b'):
        client.chiedi(MESSAGGI)


def test_ollama_404_con_client_reale_e_trasporto_finto():
    """Percorso reale di ``ollama.Client`` con un trasporto httpx simulato."""
    def risposta_404(request):
        return httpx.Response(404, text=json.dumps({'error': 'model "bge-m3" not found'}))

    reale = ollama.Client(host='http://ollama.test', transport=httpx.MockTransport(risposta_404))
    client = OllamaClient(model='m', embedding_model='bge-m3', client=reale)

    with pytest.raises(LLMNonDisponibile, match='ollama pull bge-m3'):
        client.embed(['ciao'])


def test_ollama_embed_a_blocchi():
    finto = MagicMock()
    finto.embed.side_effect = lambda model, input: ollama.EmbedResponse(
        embeddings=[[1, 0] for _ in input]
    )
    client = OllamaClient(model='m', embedding_model='bge-m3', client=finto)

    vettori = client.embed([f't{i}' for i in range(70)])
    assert len(vettori) == 70
    blocco = llm_client.BLOCCO_EMBEDDING
    attesi = [blocco] * (70 // blocco) + ([70 % blocco] if 70 % blocco else [])
    assert [len(c.kwargs['input']) for c in finto.embed.call_args_list] == attesi
    assert finto.embed.call_args.kwargs['model'] == 'bge-m3'
    assert all(isinstance(x, float) for x in vettori[0])


def test_messaggi_non_validi():
    client = OllamaClient(model='m', client=_client_ollama_finto())
    with pytest.raises(ValueError):
        client.chiedi([])
    with pytest.raises(ValueError):
        client.chiedi([{'testo': 'manca role'}])


# --- Anthropic --------------------------------------------------------------

def test_anthropic_senza_chiave():
    with pytest.raises(LLMNonDisponibile, match='ANTHROPIC_API_KEY'):
        AnthropicClient(model='claude-modello-test')


def test_anthropic_modello_non_configurato(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'chiave-finta')
    monkeypatch.setattr(llm_client.config, 'get', lambda chiave, default=None: '')
    with pytest.raises(LLMNonDisponibile, match='anthropic_model'):
        AnthropicClient()


def test_anthropic_system_separato():
    finto = MagicMock()
    finto.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type='text', text='Risposta')]
    )
    client = AnthropicClient(model='claude-modello-test', client=finto)

    assert client.chiedi(MESSAGGI, temperature=0.0) == 'Risposta'
    kwargs = finto.messages.create.call_args.kwargs
    assert kwargs['system'] == 'Sei un assistente climatico.'
    assert kwargs['messages'] == [MESSAGGI[1]]
    assert all(m['role'] != 'system' for m in kwargs['messages'])
    assert kwargs['model'] == 'claude-modello-test'
    assert kwargs['temperature'] == 0.0
    assert kwargs['max_tokens'] > 0


def test_anthropic_embed_non_supportato():
    client = AnthropicClient(model='claude-modello-test', client=MagicMock())
    with pytest.raises(LLMNonDisponibile, match='Ollama'):
        client.embed(['ciao'])


# --- FakeLLM ----------------------------------------------------------------

def test_fake_sequenza_e_chiamate():
    fake = FakeLLM(['prima', 'seconda'])

    assert fake.chiedi([{'role': 'user', 'content': 'a'}]) == 'prima'
    assert fake.chiedi([{'role': 'user', 'content': 'b'}], temperature=0.5) == 'seconda'
    assert fake.chiedi([{'role': 'user', 'content': 'c'}]) == 'seconda'  # ripete l'ultima
    assert [c[0]['content'] for c in fake.chiamate] == ['a', 'b', 'c']
    assert fake.temperature == [None, 0.5, None]


def test_fake_embed_deterministico_e_normalizzato():
    fake = FakeLLM(['x'])
    a, b, c = fake.embed(['ondata di calore Torino', 'ondata di calore Torino', 'neve'])

    assert a == b
    assert math.isclose(sum(x * x for x in a), 1.0)
    assert len(a) == len(c) == llm_client.DIMENSIONE_EMBEDDING_FAKE
    assert FakeLLM(['y']).embed(['ondata di calore Torino'])[0] == a


def test_fake_embedding_fn_personalizzata():
    fake = FakeLLM(['x'], embedding_fn=lambda testi: [[1.0] for _ in testi])
    assert fake.embed(['a', 'b']) == [[1.0], [1.0]]


# --- Factory, wrapper e stato -----------------------------------------------

def test_crea_client_fake(monkeypatch):
    monkeypatch.setenv('HEATWAVE_FAKE_LLM', '1')
    client = crea_client()
    assert isinstance(client, FakeLLM)
    assert chiedi_llm([{'role': 'user', 'content': 'ciao'}]) == llm_client.RISPOSTA_FAKE_PREDEFINITA


def test_crea_client_ollama_e_provider_sconosciuto():
    assert isinstance(crea_client('ollama'), OllamaClient)
    with pytest.raises(ValueError, match='non riconosciuto'):
        crea_client('mistral')


def test_stato_llm_server_spento(monkeypatch):
    def spento(host):
        raise ConnectionError('Failed to connect to Ollama')

    monkeypatch.setattr(llm_client, '_modelli_ollama_scaricati', spento)
    ok, messaggio = stato_llm('ollama')
    assert ok is False
    assert 'Avvia Ollama' in messaggio


def test_stato_llm_modelli_mancanti(monkeypatch):
    monkeypatch.setattr(llm_client, '_modelli_ollama_scaricati', lambda host: {'llama3.2:latest'})
    ok, messaggio = stato_llm('ollama')
    assert ok is False
    assert 'ollama pull qwen2.5:7b' in messaggio
    assert 'ollama pull bge-m3' in messaggio


def test_stato_llm_pronto(monkeypatch):
    monkeypatch.setattr(
        llm_client, '_modelli_ollama_scaricati', lambda host: {'qwen2.5:7b', 'bge-m3:latest'}
    )
    ok, messaggio = stato_llm('ollama')
    assert ok is True
    assert 'qwen2.5:7b' in messaggio


def test_stato_llm_non_solleva_mai(monkeypatch):
    def esplode(host):
        raise RuntimeError('guasto imprevisto')

    monkeypatch.setattr(llm_client, '_modelli_ollama_scaricati', esplode)
    ok, messaggio = stato_llm()
    assert ok is False
    assert 'guasto imprevisto' in messaggio


def test_stato_llm_fake(monkeypatch):
    monkeypatch.setenv('HEATWAVE_FAKE_LLM', '1')
    assert stato_llm()[0] is True


# --- Streaming (T7.1, lezione 14-05) ------------------------------------------

def _parti_stream(*pezzi):
    return [ollama.ChatResponse(message=ollama.Message(role='assistant', content=p)) for p in pezzi]


def test_ollama_streaming_chiama_on_token_e_restituisce_il_testo_completo():
    finto = MagicMock()
    finto.chat.return_value = iter(_parti_stream('Ad ', 'Alessandria ', '', 'fa caldo.'))
    client = OllamaClient(model='m', client=finto)
    ricevuti = []

    assert client.chiedi(MESSAGGI, on_token=ricevuti.append) == 'Ad Alessandria fa caldo.'
    assert ricevuti == ['Ad ', 'Alessandria ', 'fa caldo.']  # i pezzi vuoti non arrivano
    kwargs = finto.chat.call_args.kwargs
    assert kwargs['stream'] is True
    assert kwargs['messages'] == MESSAGGI and kwargs['model'] == 'm'


def test_ollama_senza_on_token_non_usa_lo_stream():
    finto = _client_ollama_finto('Ciao!')
    assert OllamaClient(model='m', client=finto).chiedi(MESSAGGI) == 'Ciao!'
    assert 'stream' not in finto.chat.call_args.kwargs


def test_ollama_errore_durante_lo_stream_diventa_llm_non_disponibile():
    def stream_interrotto():
        yield from _parti_stream('Inizio ')
        raise httpx.ReadTimeout('lento')

    finto = MagicMock()
    finto.chat.return_value = stream_interrotto()
    ricevuti = []
    with pytest.raises(LLMNonDisponibile, match='non ha risposto'):
        OllamaClient(model='m', client=finto, timeout=180).chiedi(MESSAGGI, on_token=ricevuti.append)
    assert ricevuti == ['Inizio ']


def test_fake_streamma_a_pezzi():
    testo = 'Cresce di 0,45 °C per decennio.\nFonte: Open-Meteo.'
    fake = FakeLLM([testo])
    ricevuti = []

    assert fake.chiedi([{'role': 'user', 'content': 'a'}], on_token=ricevuti.append) == testo
    assert len(ricevuti) > 1 and ''.join(ricevuti) == testo


def test_anthropic_on_token_riceve_il_testo_intero():
    finto = MagicMock()
    finto.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type='text', text='Risposta')]
    )
    ricevuti = []
    client = AnthropicClient(model='claude-modello-test', client=finto)
    assert client.chiedi(MESSAGGI, on_token=ricevuti.append) == 'Risposta'
    assert ricevuti == ['Risposta']


# --- Gemini (lezione 13-02) -----------------------------------------------------

from src.chatbot.llm_client import GeminiClient  # noqa: E402

CONVERSAZIONE = [
    {'role': 'system', 'content': 'Regole'},
    {'role': 'user', 'content': 'Domanda'},
    {'role': 'assistant', 'content': 'TOOL: x'},
    {'role': 'user', 'content': 'Risultato'},
]


def _gemini_finto(testo='ok', pezzi=None, errore=None):
    finto = MagicMock()
    if errore is not None:
        finto.models.generate_content.side_effect = errore
        finto.models.generate_content_stream.side_effect = errore
    finto.models.generate_content.return_value = SimpleNamespace(text=testo)
    finto.models.generate_content_stream.return_value = [SimpleNamespace(text=p) for p in (pezzi or [])]
    return finto


def test_gemini_system_separato_e_ruoli():
    finto = _gemini_finto('Risposta')
    client = GeminiClient(model='gemini-test', client=finto, thinking_budget=0)
    assert client.chiedi(CONVERSAZIONE, temperature=0.1, max_tokens=50) == 'Risposta'
    argomenti = finto.models.generate_content.call_args.kwargs
    assert argomenti['model'] == 'gemini-test'
    assert [c['role'] for c in argomenti['contents']] == ['user', 'model', 'user']
    configurazione = argomenti['config']
    assert configurazione.system_instruction == 'Regole'
    assert configurazione.temperature == pytest.approx(0.1)
    assert configurazione.max_output_tokens == 50
    assert configurazione.thinking_config.thinking_budget == 0


def test_gemini_streaming():
    finto = _gemini_finto(pezzi=['Cia', 'o ', 'mondo'])
    ricevuti = []
    testo = GeminiClient(model='g', client=finto).chiedi(MESSAGGI, on_token=ricevuti.append)
    assert testo == 'Ciao mondo' and ricevuti == ['Cia', 'o ', 'mondo']
    finto.models.generate_content.assert_not_called()


def test_gemini_senza_chiave(monkeypatch):
    monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    with pytest.raises(LLMNonDisponibile, match='aistudio.google.com'):
        GeminiClient(model='g')


@pytest.mark.parametrize('codice, attesa', [
    (429, 'piano gratuito'), (404, 'non trovato'), (403, 'non valida'), (503, 'non disponibile'),
])
def test_gemini_errori_tradotti(codice, attesa):
    errore = Exception('errore API')
    errore.code = codice
    client = GeminiClient(model='g', client=_gemini_finto(errore=errore))
    with pytest.raises(LLMNonDisponibile, match=attesa):
        client.chiedi(MESSAGGI)


def test_gemini_timeout():
    client = GeminiClient(model='g', client=_gemini_finto(errore=httpx.ReadTimeout('lento')), timeout=9)
    with pytest.raises(LLMNonDisponibile, match='entro 9 secondi'):
        client.chiedi(MESSAGGI)


def test_crea_client_e_stato_gemini(monkeypatch):
    monkeypatch.delenv('HEATWAVE_FAKE_LLM', raising=False)
    monkeypatch.setenv('GOOGLE_API_KEY', 'chiave-finta')
    assert isinstance(llm_client.crea_client('gemini', con_riserva=False), GeminiClient)
    monkeypatch.setattr(llm_client, '_modelli_ollama_scaricati', lambda host: {'bge-m3:latest'})
    ok, messaggio = llm_client.stato_llm('gemini')
    assert ok and 'gemini' in messaggio
    monkeypatch.delenv('GOOGLE_API_KEY')
    ok, messaggio = llm_client.stato_llm('gemini')
    assert not ok and 'GOOGLE_API_KEY' in messaggio


# --- Riserva automatica (Gemini -> Ollama) -------------------------------------

from src.chatbot.llm_client import ClientConRiserva  # noqa: E402


class _Principale:
    model = 'gemini-test'

    def __init__(self, errore=None):
        self.errore, self.chiamate = errore, 0

    def chiedi(self, messaggi, temperature=None, max_tokens=None, on_token=None):
        self.chiamate += 1
        if self.errore:
            raise self.errore
        return 'dal principale'


def test_riserva_non_usata_se_il_principale_risponde():
    riserva = FakeLLM(['dalla riserva'])
    client = ClientConRiserva(_Principale(), lambda: riserva)
    assert client.chiedi(MESSAGGI) == 'dal principale'
    assert riserva.chiamate == [] and client.preleva_avvisi() == []
    assert client.model == 'gemini-test'


def test_riserva_su_quota_esaurita_e_riposo_del_principale():
    principale = _Principale(LLMNonDisponibile('Quota giornaliera gratuita di Gemini esaurita'))
    riserva = FakeLLM(['dalla riserva'])
    client = ClientConRiserva(principale, lambda: riserva)
    assert client.chiedi(MESSAGGI) == 'dalla riserva'
    avvisi = client.preleva_avvisi()
    assert len(avvisi) == 1 and 'riserva' in avvisi[0]
    assert client.preleva_avvisi() == []          # l'avviso si legge una volta sola
    assert client.chiedi(MESSAGGI) == 'dalla riserva'
    assert principale.chiamate == 1               # a riposo: non viene richiamato
    assert client.in_riserva() and client.model == 'FakeLLM'


def test_errore_anche_della_riserva_viene_propagato():
    riserva = MagicMock()
    riserva.chiedi.side_effect = LLMNonDisponibile('Ollama spento')
    client = ClientConRiserva(_Principale(LLMNonDisponibile('504')), lambda: riserva)
    with pytest.raises(LLMNonDisponibile, match='Ollama spento'):
        client.chiedi(MESSAGGI)


def test_gemini_quota_giornaliera_messaggio_dedicato():
    errore = Exception('429 RESOURCE_EXHAUSTED ... Generate content requests per day limit exceeded')
    errore.code = 429
    client = GeminiClient(model='g', client=_gemini_finto(errore=errore))
    with pytest.raises(LLMNonDisponibile, match='giornaliera'):
        client.chiedi(MESSAGGI)


def test_crea_client_gemini_con_riserva(monkeypatch):
    monkeypatch.delenv('HEATWAVE_FAKE_LLM', raising=False)
    monkeypatch.setenv('GOOGLE_API_KEY', 'chiave-finta')
    valori = {'chatbot.riserva': 'ollama'}
    originale = llm_client.config.get
    monkeypatch.setattr(llm_client.config, 'get', lambda k, d=None: valori.get(k, originale(k, d)))
    assert isinstance(llm_client.crea_client('gemini'), ClientConRiserva)
    assert isinstance(llm_client.crea_client('gemini', con_riserva=False), GeminiClient)

