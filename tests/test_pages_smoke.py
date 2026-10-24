"""Smoke test AppTest della pagina 10 "Assistente climatico" con FakeLLM (T7.1).

Nessun Ollama: ``HEATWAVE_FAKE_LLM=1`` fa usare ``FakeLLM`` a tutta la catena
(stato, riscaldamento, agente). Si usa una domanda di rifiuto, che non
richiede né dati né indice RAG.
"""

from pathlib import Path

import pytest

pytest.importorskip('streamlit.testing.v1')
from streamlit.testing.v1 import AppTest  # noqa: E402

PAGINA_10 = Path(__file__).resolve().parents[1] / 'dashboard' / 'pages' / '10_assistente_climatico.py'


@pytest.fixture
def pagina_10(monkeypatch):
    monkeypatch.setenv('HEATWAVE_FAKE_LLM', '1')
    return AppTest.from_file(str(PAGINA_10), default_timeout=120)


def test_pagina_10_si_apre_con_avviso_ai(pagina_10):
    at = pagina_10.run()
    assert not at.exception
    assert at.title[0].value == '💬 Assistente climatico'
    assert any('intelligenza artificiale' in i.value for i in at.info)
    assert not at.chat_input[0].disabled


def test_pagina_10_domanda_e_nuova_conversazione(pagina_10):
    at = pagina_10.run()
    at.chat_input[0].set_value('Mi dai la ricetta della bagna cauda?').run()
    assert not at.exception
    assert [m.name for m in at.chat_message] == ['user', 'assistant']
    assert [e.label for e in at.expander] == ['Come ho ragionato']
    assert len(at.session_state['chat_history']) == 2

    at.sidebar.button[0].click().run()  # "Nuova conversazione"
    assert len(at.chat_message) == 0
    assert at.session_state['chat_history'] == []


PAGINE = Path(__file__).resolve().parents[1] / 'dashboard' / 'pages'


@pytest.mark.parametrize('file, titolo', [
    ('09_machine_learning.py', 'Machine Learning'),
    ('11_etica_e_limiti.py', 'Etica'),
])
def test_pagine_ml_ed_etica_si_aprono_senza_database(monkeypatch, file, titolo):
    """Le pagine leggono solo Parquet e modelli: con un DB irraggiungibile devono aprirsi."""
    monkeypatch.setenv('DB_HOST', '127.0.0.1')
    monkeypatch.setenv('DB_PORT', '1')
    at = AppTest.from_file(str(PAGINE / file), default_timeout=180).run()
    assert not at.exception
    assert titolo in at.title[0].value
