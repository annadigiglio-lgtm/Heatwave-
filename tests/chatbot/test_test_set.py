"""Validazione del test set del chatbot (``test_set.csv``, T8.1): struttura, valori ammessi, riferimenti.

Il test set serve al benchmark T8.2 (lezione 12). Qui si controlla solo che il
file sia coerente con il codice e con la wiki: nessuna rete, nessun LLM.
"""

from pathlib import Path

import pandas as pd
import pytest

from src.chatbot.tools import TOOLS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_SET = Path(__file__).with_name('test_set.csv')

COLONNE = ['id', 'categoria', 'domanda', 'percorso_atteso', 'tool_attesi',
           'valori_chiave', 'fonti_attese', 'deve_rifiutare', 'note']
MINIMI_PER_CATEGORIA = {
    'fattuale': 7,
    'confronto': 3,
    'metodo': 5,
    'dato_assente': 3,
    'fuori_ambito': 3,
    'injection': 3,
}
PERCORSI = {'dati', 'metodo', 'misto', 'fuori_ambito'}
RIFIUTI = {'si', 'no'}


def _lista(valore: str) -> list[str]:
    """Campo multi-valore separato da ``;`` (vuoto -> lista vuota)."""
    return [parte.strip() for parte in str(valore).split(';') if parte.strip()]


@pytest.fixture(scope='module')
def test_set() -> pd.DataFrame:
    return pd.read_csv(TEST_SET, encoding='utf-8', dtype=str, keep_default_na=False)


def test_colonne_esatte(test_set):
    assert list(test_set.columns) == COLONNE


def test_id_univoci_e_non_vuoti(test_set):
    assert (test_set['id'].str.strip() != '').all()
    assert test_set['id'].is_unique


def test_domande_non_vuote(test_set):
    assert (test_set['domanda'].str.strip() != '').all()


def test_numero_righe_e_minimi_per_categoria(test_set):
    assert len(test_set) >= 24
    conteggi = test_set['categoria'].value_counts()
    for categoria, minimo in MINIMI_PER_CATEGORIA.items():
        assert conteggi.get(categoria, 0) >= minimo, categoria


def test_valori_ammessi(test_set):
    assert set(test_set['categoria']) <= set(MINIMI_PER_CATEGORIA)
    assert set(test_set['percorso_atteso']) <= PERCORSI
    assert set(test_set['deve_rifiutare']) <= RIFIUTI


def test_tool_attesi_nella_whitelist(test_set):
    for riga in test_set.itertuples():
        for nome in _lista(riga.tool_attesi):
            assert nome in TOOLS, f'{riga.id}: tool sconosciuto {nome}'


def test_fonti_attese_esistono(test_set):
    for riga in test_set.itertuples():
        for fonte in _lista(riga.fonti_attese):
            assert (PROJECT_ROOT / fonte).is_file(), f'{riga.id}: fonte mancante {fonte}'


def test_fuori_ambito_e_injection_rifiutano_senza_tool(test_set):
    righe = test_set.loc[test_set['categoria'].isin(['fuori_ambito', 'injection'])]
    for riga in righe.itertuples():
        assert riga.deve_rifiutare == 'si', riga.id
        assert _lista(riga.tool_attesi) == [], riga.id
        assert riga.percorso_atteso == 'fuori_ambito', riga.id


def test_domande_sui_dati_hanno_tool_e_valori(test_set):
    """Fattuali e confronti: almeno un tool e almeno un valore chiave da cercare."""
    righe = test_set.loc[test_set['categoria'].isin(['fattuale', 'confronto'])]
    for riga in righe.itertuples():
        assert _lista(riga.tool_attesi), riga.id
        assert _lista(riga.valori_chiave), riga.id


def test_domande_di_metodo_hanno_fonti(test_set):
    righe = test_set.loc[test_set['percorso_atteso'].isin(['metodo', 'misto'])]
    for riga in righe.itertuples():
        assert _lista(riga.fonti_attese), riga.id
