"""Configurazione comune dei test."""

import pytest


@pytest.fixture(autouse=True)
def _senza_cache_risposte(monkeypatch):
    """Nessun test legge o scrive la cache su disco delle risposte del chatbot.

    I test dedicati (``tests/chatbot/test_cache_risposte.py``) la riattivano su
    una cartella temporanea.
    """
    monkeypatch.setenv('HEATWAVE_CACHE_RISPOSTE', '0')
