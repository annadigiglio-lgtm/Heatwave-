"""Criteri del benchmark del chatbot (``tests/chatbot/benchmark.py``), senza LLM."""

from types import SimpleNamespace

import pandas as pd

from tests.chatbot.benchmark import (
    numeri_nel_testo,
    riepilogo,
    tool_corretti,
    valore_presente,
    valuta,
)


def _risposta(testo='', percorso='dati', tool=(), fonti=(), avvisi=(), chiamate=1):
    return SimpleNamespace(testo=testo, percorso=percorso, chiamate_llm=chiamate,
                           tool_chiamati=[{'nome': n, 'risultato': r} for n, r in tool],
                           fonti=list(fonti), avvisi=list(avvisi))


def _riga(**campi):
    base = {'categoria': 'fattuale', 'tool_attesi': '', 'valori_chiave': '',
            'percorso_atteso': 'dati', 'deve_rifiutare': 'no'}
    return {**base, **campi}


def test_numeri_virgola_punto_e_meno_tipografico():
    assert numeri_nel_testo('cresce di +0,45 °C, bias −2,05 e 599 comuni') == [0.45, -2.05, 599.0]


def test_valore_presente_numeri_e_parole():
    assert valore_presente('0.45', 'pendenza di 0,45 °C/decennio')
    assert valore_presente('-2.05', 'sottostima di 2,05 °C')
    assert not valore_presente('1', 'nel 2010 e 2021')  # niente falsi positivi da sottostringhe
    assert valore_presente('crescente', 'trend Crescente')
    assert valore_presente('CONSOLATA', 'stazione di via della Consolata')


def test_tool_corretti_con_alternative():
    assert tool_corretti({'compare_locations'}, ['get_heatwave_summary', 'get_heatwave_summary'])
    assert not tool_corretti({'get_climate_cluster'}, ['get_temperature_trend'])
    assert tool_corretti(set(), []) and not tool_corretti(set(), ['get_data_coverage'])


def test_valuta_fattuale_metodo_rifiuti():
    fattuale = valuta(_riga(tool_attesi='get_temperature_trend', valori_chiave='0.45;crescente'),
                      _risposta('Cresce di 0,45 °C/decennio (crescente).',
                                tool=[('get_temperature_trend', {})]))
    assert fattuale['corretta'] and fattuale['valori_trovati'] == 2

    metodo = valuta(_riga(categoria='metodo', percorso_atteso='metodo'),
                    _risposta('Spiegazione', percorso='metodo', fonti=[{'fonte': 'faq.md'}]))
    assert metodo['corretta']

    rifiuto = valuta(_riga(categoria='injection', percorso_atteso='fuori_ambito', deve_rifiutare='si'),
                     _risposta('No.', percorso='fuori_ambito', chiamate=0))
    assert rifiuto['corretta']

    assente = valuta(_riga(categoria='dato_assente', tool_attesi='get_heatwave_summary',
                           deve_rifiutare='si'),
                     _risposta('Arona non ha dati.', tool=[('get_heatwave_summary', {'errore': 'x'})]))
    assert assente['corretta']

    inventata = valuta(_riga(categoria='dato_assente', tool_attesi='get_heatwave_summary',
                             deve_rifiutare='si'),
                       _risposta('Ci saranno 12 ondate.',
                                 tool=[('get_heatwave_summary', {'errore': 'x'})],
                                 avvisi=['alcuni numeri (12) non risultano nei dati']))
    assert not inventata['corretta']


def test_riepilogo_percentuali():
    dettaglio = pd.DataFrame([
        {'versione': 'v1', 'modello': 'm', 'id': 'A', 'categoria': 'fattuale', 'corretta': True,
         'percorso_ok': True, 'tool_ok': True, 'valori_trovati': 2, 'valori_totali': 2,
         'rifiuto_ok': True, 'supportata': True, 'durata_s': 2.0, 'chiamate_llm': 1, 'errore': ''},
        {'versione': 'v1', 'modello': 'm', 'id': 'B', 'categoria': 'injection', 'corretta': False,
         'percorso_ok': False, 'tool_ok': True, 'valori_trovati': 0, 'valori_totali': 0,
         'rifiuto_ok': False, 'supportata': True, 'durata_s': 0.0, 'chiamate_llm': 0, 'errore': ''},
    ])
    sintesi = riepilogo(dettaglio).iloc[0]
    assert sintesi['corrette_pct'] == 50.0 and sintesi['rifiuti_ok_pct'] == 0.0
    assert sintesi['valori_trovati_pct'] == 100.0 and sintesi['durata_media_s'] == 1.0


def test_sinonimi_e_zero_a_parole():
    assert valore_presente('crescente', 'la temperatura è aumentata di 0,45 °C')
    assert valore_presente('0', 'Tra il 2000 e oggi non sono state registrate ondate')
    assert valore_presente('0', 'nessuna ondata di calore')
    assert valore_presente('0', 'Ciriè non ha avuto ondate di calore')
    assert valore_presente('crescente', 'trend di riscaldamento significativo')
    assert valore_presente('alpino', 'Sestriere è nel cluster delle zone alpine')
    assert not valore_presente('crescente', 'la temperatura è diminuita')


def test_dato_assente_rifiutato_dal_router():
    esito = valuta(_riga(categoria='dato_assente', percorso_atteso='fuori_ambito', deve_rifiutare='si'),
                   _risposta('Non posso fare previsioni.', percorso='fuori_ambito', chiamate=0))
    assert esito['corretta']

