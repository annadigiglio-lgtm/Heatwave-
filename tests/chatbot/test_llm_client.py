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
    assert [len(c.kwargs['input']) for c in finto.embed.call_args_list] == [32, 32, 6]
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
        crea_client('gemini')


def test_stato_llm_server_spento(monkeypatch):
    def spento(host):
        raise ConnectionError('Failed to connect to Ollama')

    monkeypatch.setattr(llm_client, '_modelli_ollama_scaricati', spento)
    ok, messaggio = stato_llm()
    assert ok is False
    assert 'Avvia Ollama' in messaggio


def test_stato_llm_modelli_mancanti(monkeypatch):
    monkeypatch.setattr(llm_client, '_modelli_ollama_scaricati', lambda host: {'llama3.2:latest'})
    ok, messaggio = stato_llm()
    assert ok is False
    assert 'ollama pull qwen2.5:7b' in messaggio
    assert 'ollama pull bge-m3' in messaggio


def test_stato_llm_pronto(monkeypatch):
    monkeypatch.setattr(
        llm_client, '_modelli_ollama_scaricati', lambda host: {'qwen2.5:7b', 'bge-m3:latest'}
    )
    ok, messaggio = stato_llm()
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
