"""Benchmark del chatbot: prompt v1 contro v2 sul test set (T8.2, lezione 12).

Non è un test pytest: interroga il modello reale (di default il provider di
``config.yaml``, oggi Gemini) su tutte le domande di
``tests/chatbot/test_set.csv``, una volta per ogni versione del prompt, senza
cache delle risposte. Per ogni risposta calcola criteri oggettivi:

- ``percorso_ok``: il router ha scelto il percorso atteso;
- ``tool_ok``: è stato chiamato almeno uno dei tool attesi (nessun tool se
  non ne sono attesi);
- ``valori_trovati``: quanti ``valori_chiave`` compaiono nella risposta
  (numeri confrontati come numeri, virgola o punto indifferenti);
- ``fonti_ok``: per le domande di metodo, almeno un documento citato;
- ``rifiuto_ok``: fuori ambito e injection rifiutati senza chiamare l'LLM;
  dati assenti segnalati dal tool con un errore;
- ``supportata``: il Revisore non ha trovato numeri non presenti nei dati;
- ``corretta``: la combinazione dei criteri che conta per la categoria.

La chiarezza (scala 1–5) resta una valutazione manuale su un campione.

Uso:
    python -m tests.chatbot.benchmark                    # v1 e v2, provider di config
    python -m tests.chatbot.benchmark --prompt v2 --provider ollama --solo F01 M02

Risultati in ``data/benchmark/chatbot_benchmark.csv`` (una riga per domanda e
versione) e ``data/benchmark/chatbot_benchmark_riepilogo.csv`` (una riga per
versione), letti dalla tab "Valutazione" della pagina 10.
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from pathlib import Path

import pandas as pd

from src.chatbot.agent import esegui_agente
from src.chatbot.llm_client import LLMNonDisponibile, crea_client
from src.chatbot.prompts import SYSTEM_PROMPTS
from src.chatbot.tools import normalizza_nome
from src.utils.logger import get_logger

logger = get_logger(__name__)

RADICE = Path(__file__).resolve().parents[2]
TEST_SET = Path(__file__).with_name('test_set.csv')
CARTELLA_RISULTATI = RADICE / 'data' / 'benchmark'
FILE_DETTAGLIO = CARTELLA_RISULTATI / 'chatbot_benchmark.csv'
FILE_RIEPILOGO = CARTELLA_RISULTATI / 'chatbot_benchmark_riepilogo.csv'

PAUSA_SECONDI = 3.0          # tra una domanda e l'altra (piano gratuito Gemini)
PAUSA_LIMITE_SECONDI = 30.0  # dopo un 429 (troppe richieste)
TENTATIVI_LIMITE = 3
TOLLERANZA = 0.006           # 0,45 e 0,451 coincidono; arrotondamenti dei tool a 2 decimali
TOOL_ALTERNATIVI = {'compare_locations': {'get_heatwave_summary', 'get_temperature_trend'}}

_RE_NUMERO = re.compile(r'[-−]?\d+(?:[.,]\d+)?')


# ---------------------------------------------------------------------------
# Criteri
# ---------------------------------------------------------------------------

def numeri_nel_testo(testo: str) -> list[float]:
    """Numeri della risposta: virgola o punto decimale, segno meno anche tipografico."""
    numeri = []
    for grezzo in _RE_NUMERO.findall(testo or ''):
        try:
            numeri.append(float(grezzo.replace('−', '-').replace(',', '.')))
        except ValueError:
            continue
    return numeri


def _e_numero(valore: str) -> bool:
    return bool(re.fullmatch(r'[-−]?\d+(?:[.,]\d+)?', valore.strip()))


def valore_presente(valore: str, testo: str) -> bool:
    """Un valore chiave è presente: i numeri come numeri (anche senza segno), le parole come testo."""
    valore = valore.strip()
    if not valore:
        return True
    if _e_numero(valore):
        atteso = float(valore.replace('−', '-').replace(',', '.'))
        return any(abs(n - atteso) <= TOLLERANZA or abs(abs(n) - abs(atteso)) <= TOLLERANZA
                   for n in numeri_nel_testo(testo))
    return normalizza_nome(valore) in normalizza_nome(testo or '')


def tool_corretti(attesi: set[str], chiamati: list[str]) -> bool:
    if not attesi:
        return not chiamati
    ammessi = set(attesi)
    for nome in attesi:
        ammessi |= TOOL_ALTERNATIVI.get(nome, set())
    return bool(set(chiamati) & ammessi)


def valuta(riga: dict, risposta) -> dict:
    """Criteri oggettivi per una risposta del test set."""
    categoria = riga['categoria']
    attesi = {t for t in riga['tool_attesi'].split(';') if t}
    chiamati = [t['nome'] for t in risposta.tool_chiamati]
    valori = [v for v in riga['valori_chiave'].split(';') if v.strip()]
    trovati = sum(valore_presente(v, risposta.testo) for v in valori)
    percorso_ok = risposta.percorso == riga['percorso_atteso']
    tool_ok = tool_corretti(attesi, chiamati)
    fonti_ok = bool(risposta.fonti)
    errore_tool = any('errore' in (t.get('risultato') or {}) for t in risposta.tool_chiamati)
    supportata = not any('numeri' in a for a in risposta.avvisi)
    deve_rifiutare = riga['deve_rifiutare'].strip().lower() == 'si'

    if categoria in ('fuori_ambito', 'injection'):
        rifiuto_ok = risposta.percorso == 'fuori_ambito' and risposta.chiamate_llm == 0
    elif deve_rifiutare:
        rifiuto_ok = errore_tool and supportata
    else:
        rifiuto_ok = True

    if categoria in ('fattuale', 'confronto'):
        corretta = tool_ok and trovati == len(valori) and (
            fonti_ok if riga['percorso_atteso'] == 'misto' else True)
    elif categoria == 'metodo':
        corretta = percorso_ok and fonti_ok and not chiamati
    elif categoria == 'dato_assente':
        corretta = rifiuto_ok if deve_rifiutare else (tool_ok and trovati == len(valori))
    else:
        corretta = rifiuto_ok

    return {
        'percorso_ok': percorso_ok, 'tool_ok': tool_ok, 'valori_trovati': trovati,
        'valori_totali': len(valori), 'fonti_ok': fonti_ok, 'rifiuto_ok': rifiuto_ok,
        'supportata': supportata, 'corretta': bool(corretta),
    }


# ---------------------------------------------------------------------------
# Esecuzione
# ---------------------------------------------------------------------------

def leggi_test_set(path: Path = TEST_SET, solo: list[str] | None = None) -> list[dict]:
    with open(path, encoding='utf-8', newline='') as f:
        righe = list(csv.DictReader(f))
    return [r for r in righe if not solo or r['id'] in solo]


def _chiedi_con_attesa(domanda: str, client, versione: str):
    """``esegui_agente`` senza cache; sui limiti del piano gratuito aspetta e riprova."""
    for tentativo in range(1, TENTATIVI_LIMITE + 1):
        try:
            return esegui_agente(domanda, client=client, prompt_version=versione, usa_cache=False)
        except LLMNonDisponibile as errore:
            if 'piano gratuito' not in str(errore) or tentativo == TENTATIVI_LIMITE:
                raise
            logger.warning(f'Limite di richieste: pausa di {PAUSA_LIMITE_SECONDI:.0f} s '
                           f'(tentativo {tentativo})')
            time.sleep(PAUSA_LIMITE_SECONDI)
    raise RuntimeError('non raggiungibile')


def esegui_benchmark(versioni: list[str], provider: str | None = None, solo: list[str] | None = None,
                     pausa: float = PAUSA_SECONDI) -> pd.DataFrame:
    client = crea_client(provider, con_riserva=False)  # si misura un solo modello
    modello = getattr(client, 'model', type(client).__name__)
    righe_test = leggi_test_set(solo=solo)
    risultati = []
    for versione in versioni:
        for numero, riga in enumerate(righe_test, start=1):
            print(f'[{versione}] {numero}/{len(righe_test)} {riga["id"]} …', flush=True)
            base = {'versione': versione, 'modello': modello, 'id': riga['id'],
                    'categoria': riga['categoria'], 'domanda': riga['domanda']}
            try:
                risposta = _chiedi_con_attesa(riga['domanda'], client, versione)
            except LLMNonDisponibile as errore:
                risultati.append({**base, 'errore': str(errore), 'corretta': False})
                continue
            risultati.append({
                **base, **valuta(riga, risposta),
                'percorso': risposta.percorso,
                'tool': ';'.join(t['nome'] for t in risposta.tool_chiamati),
                'chiamate_llm': risposta.chiamate_llm, 'durata_s': risposta.durata_s,
                'avvisi': ' | '.join(risposta.avvisi), 'risposta': risposta.testo,
                'errore': '',
            })
            if risposta.chiamate_llm:
                time.sleep(pausa)
    return pd.DataFrame(risultati)


def riepilogo(dettaglio: pd.DataFrame) -> pd.DataFrame:
    """Una riga per versione del prompt: percentuali dei criteri e tempi medi."""
    righe = []
    for versione, gruppo in dettaglio.groupby('versione', sort=True):
        valutate = gruppo[gruppo['errore'].fillna('') == '']
        valori_tot = valutate['valori_totali'].sum()
        riga = {
            'versione': versione,
            'modello': gruppo['modello'].iloc[0],
            'domande': len(gruppo),
            'errori_llm': int((gruppo['errore'].fillna('') != '').sum()),
            'corrette_pct': round(100 * gruppo['corretta'].fillna(False).astype(bool).mean(), 1),
            'percorso_ok_pct': round(100 * valutate['percorso_ok'].astype(bool).mean(), 1),
            'tool_ok_pct': round(100 * valutate['tool_ok'].astype(bool).mean(), 1),
            'valori_trovati_pct': round(100 * valutate['valori_trovati'].sum() / valori_tot, 1)
            if valori_tot else None,
            'rifiuti_ok_pct': round(100 * valutate.loc[
                valutate['categoria'].isin(['fuori_ambito', 'injection', 'dato_assente']),
                'rifiuto_ok'].astype(bool).mean(), 1),
            'supportate_pct': round(100 * valutate['supportata'].astype(bool).mean(), 1),
            'durata_media_s': round(valutate['durata_s'].mean(), 2),
            'chiamate_llm_medie': round(valutate['chiamate_llm'].mean(), 2),
        }
        for categoria, sotto in gruppo.groupby('categoria'):
            riga[f'corrette_{categoria}_pct'] = round(
                100 * sotto['corretta'].fillna(False).astype(bool).mean(), 1)
        righe.append(riga)
    return pd.DataFrame(righe)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Benchmark del chatbot: prompt v1 contro v2.')
    parser.add_argument('--prompt', nargs='+', default=list(SYSTEM_PROMPTS),
                        choices=list(SYSTEM_PROMPTS))
    parser.add_argument('--provider', default=None, help='ollama | gemini | anthropic (default: config)')
    parser.add_argument('--solo', nargs='*', default=None, help='solo questi id del test set')
    parser.add_argument('--pausa', type=float, default=PAUSA_SECONDI)
    argomenti = parser.parse_args(argv)

    dettaglio = esegui_benchmark(argomenti.prompt, argomenti.provider, argomenti.solo, argomenti.pausa)
    CARTELLA_RISULTATI.mkdir(parents=True, exist_ok=True)
    dettaglio.to_csv(FILE_DETTAGLIO, index=False, encoding='utf-8')
    sintesi = riepilogo(dettaglio)
    sintesi.to_csv(FILE_RIEPILOGO, index=False, encoding='utf-8')
    print(sintesi.T.to_string(header=False))
    print(f'\nDettaglio: {FILE_DETTAGLIO}\nRiepilogo: {FILE_RIEPILOGO}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
