"""Test della cache su disco delle risposte (``src/chatbot/cache_risposte.py``)."""

import pytest

from src.chatbot import agent, cache_risposte
from src.chatbot.agent import esegui_agente
from src.chatbot.llm_client import FakeLLM
from src.chatbot.memory import MemoriaConversazione

DOMANDA = "Com'è cambiata la temperatura a Alessandria?"
RISPOSTA = 'Ad Alessandria la temperatura cresce di 0.45 °C/decennio. Fonte: Open-Meteo.'


@pytest.fixture
def cache_temporanea(tmp_path, monkeypatch):
    monkeypatch.setenv('HEATWAVE_CACHE_RISPOSTE', '1')
    monkeypatch.setattr(cache_risposte, 'cartella_cache', lambda: tmp_path)
    monkeypatch.setattr(agent, '_preselezione_attiva', lambda: True)
    return tmp_path


def test_seconda_domanda_uguale_servita_dalla_cache(cache_temporanea):
    prima = esegui_agente(DOMANDA, client=FakeLLM([RISPOSTA]))
    assert not prima.dalla_cache and prima.chiamate_llm == 1
    assert cache_risposte.conta() == 1

    llm = FakeLLM(['non dovrebbe essere usata'])
    seconda = esegui_agente('com e cambiata la temperatura a alessandria', client=llm)
    assert seconda.dalla_cache
    assert seconda.testo == prima.testo
    assert seconda.chiamate_llm == 0 and llm.chiamate == []
    assert [t['nome'] for t in seconda.tool_chiamati] == ['get_temperature_trend']


def test_cache_streamma_e_aggiorna_la_memoria(cache_temporanea):
    esegui_agente(DOMANDA, client=FakeLLM([RISPOSTA]))
    pezzi, eventi = [], []
    memoria = MemoriaConversazione(finestra=6)
    risposta = esegui_agente(DOMANDA, client=FakeLLM(['x']), on_token=pezzi.append,
                             on_evento=eventi.append, memoria=memoria)
    assert risposta.dalla_cache and ''.join(pezzi) == RISPOSTA
    assert any('cache' in e for e in eventi)
    assert [m['role'] for m in memoria.messaggi()] == ['user', 'assistant']


@pytest.mark.parametrize('variante', ['versione', 'storia', 'modello', 'dati'])
def test_chiave_cambia_se_cambia_il_contesto(variante):
    base = dict(domanda=DOMANDA, storia=[], versione='v2', modello='qwen2.5:7b',
                system_prompt='S', firma='f1')
    altra = dict(base)
    if variante == 'versione':
        altra['versione'] = 'v1'
    elif variante == 'storia':
        altra['storia'] = [{'role': 'user', 'content': 'E a Cuneo?'}]
    elif variante == 'modello':
        altra['modello'] = 'qwen2.5:3b'
    else:
        altra['firma'] = 'f2'
    assert cache_risposte.chiave(**base) != cache_risposte.chiave(**altra)


def test_rifiuti_non_salvati_e_cache_disattivabile(cache_temporanea, monkeypatch):
    esegui_agente("Domani ci sarà un'ondata di calore a Torino?", client=FakeLLM(['x']))
    assert cache_risposte.conta() == 0
    esegui_agente(DOMANDA, client=FakeLLM([RISPOSTA]), usa_cache=False)
    assert cache_risposte.conta() == 0
    monkeypatch.setenv('HEATWAVE_CACHE_RISPOSTE', '0')
    assert not cache_risposte.cache_attiva()


def test_svuota_e_file_illeggibile(cache_temporanea):
    esegui_agente(DOMANDA, client=FakeLLM([RISPOSTA]))
    (cache_temporanea / 'rotto.json').write_text('{non json', encoding='utf-8')
    assert cache_risposte.leggi('rotto') is None
    assert cache_risposte.svuota() == 2
    assert cache_risposte.conta() == 0


def test_firma_dati_cambia_con_i_file(tmp_path):
    (tmp_path / 'data' / 'dashboard_export').mkdir(parents=True)
    file = tmp_path / 'data' / 'dashboard_export' / 'overview_stats.json'
    file.write_text('{}', encoding='utf-8')
    prima = cache_risposte.firma_dati(tmp_path)
    file.write_text('{"n": 1}', encoding='utf-8')
    assert cache_risposte.firma_dati(tmp_path) != prima
