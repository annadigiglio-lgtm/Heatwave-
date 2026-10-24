"""
aggiorna_pipeline.py - Rigenera lo stato della pipeline d'esame nella wiki.

Legge gli stati dei task in `wiki/pages/todo-agenti.md` (intestazioni
`### T<fase>.<n> <stato> <titolo>`, con stato ✅ ⬜ 🔄 ⛔) e riscrive il blocco
compreso tra i marcatori `<!-- PIPELINE:START -->` e `<!-- PIPELINE:END -->`
in `wiki/pages/roadmap-esame.md`: schema con lo stato di ogni fase,
avanzamento complessivo, tabella dei task e task pronti da avviare (tutte le
dipendenze ✅).

Solo libreria standard: gira con qualsiasi Python 3.10+.

Usage:
    python scripts/aggiorna_pipeline.py          # aggiornamento manuale
    python scripts/aggiorna_pipeline.py --hook   # da hook PostToolUse di Claude Code:
                                                 # legge il JSON da stdin e agisce solo
                                                 # se il file modificato è todo-agenti.md
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TODO = ROOT / 'wiki' / 'pages' / 'todo-agenti.md'
ROADMAP = ROOT / 'wiki' / 'pages' / 'roadmap-esame.md'
START, END = '<!-- PIPELINE:START -->', '<!-- PIPELINE:END -->'

FATTO, DA_FARE, IN_CORSO, BLOCCATO = '✅', '⬜', '🔄', '⛔'
PRONTA = '▶️'

# Dipendenze tra fasi, come nello schema di roadmap-esame.md
DIPENDENZE_FASI = {
    'F0': [], 'F1': ['F0'], 'F2': ['F1'], 'F3': ['F1'], 'F9': ['F1'],
    'F4': ['F3'], 'F5': ['F1'], 'F6': ['F4', 'F5'], 'F7': ['F6'],
    'F8': ['F7'], 'F10': ['F2', 'F8', 'F9'], 'F11': ['F10'],
}

SCHEMA = """\
{F0} F0  Messa in sicurezza
 │
{F1} F1  Base solida
 ├──────────────────────┬──────────────────────────┐
{F2} F2  ML supervis.   {F3} F3  Client LLM         {F9} F9  Etica e limiti
 │                      ├─────────────┐
 │                   {F4} F4 RAG    {F5} F5 Tool dati
 │                      └──────┬──────┘
 │                          {F6} F6  Agente
 │                             │
 │                          {F7} F7  Pagina chat
 │                             │
 │                          {F8} F8  Valutazione
 └──────────────┬──────────────┘
             {F10} F10 Qualità
                │
             {F11} F11 Consegna e demo"""

RE_TASK = re.compile(r'^### (T(\d+)\.(\d+)) (✅|⬜|🔄|⛔) (.+)$')
RE_FASE = re.compile(r'^### (F\d+) — (.+)$')
RE_DIPENDE = re.compile(r'\*\*Dipende da:\*\*([^·\n]*)')


def leggi_task(testo: str) -> list[dict]:
    """Estrae id, fase, stato, titolo, obbligatorietà e dipendenze di ogni task."""
    righe = testo.splitlines()
    tasks = []
    for i, riga in enumerate(righe):
        match = RE_TASK.match(riga.strip())
        if not match:
            continue
        task_id, fase, _, stato, titolo = match.groups()
        dipendenze = []
        for successiva in righe[i + 1:i + 4]:
            dip = RE_DIPENDE.search(successiva)
            if dip:
                dipendenze = re.findall(r'T\d+\.\d+', dip.group(1))
                break
        tasks.append({
            'id': task_id,
            'fase': f'F{fase}',
            'stato': stato,
            'titolo': titolo.strip(),
            'facoltativo': 'facoltativo' in titolo.lower(),
            'dipendenze': dipendenze,
        })
    return tasks


def leggi_nomi_fasi(testo: str) -> dict[str, str]:
    nomi = {}
    for riga in testo.splitlines():
        match = RE_FASE.match(riga.strip())
        if match:
            nomi[match.group(1)] = match.group(2).strip()
    return nomi


def stato_fase(tasks_fase: list[dict]) -> str:
    """✅ se tutti i task obbligatori sono fatti; ⛔/🔄/⬜ altrimenti."""
    obbligatori = [t for t in tasks_fase if not t['facoltativo']] or tasks_fase
    stati = [t['stato'] for t in obbligatori]
    if not stati:
        return DA_FARE
    if all(s == FATTO for s in stati):
        return FATTO
    if BLOCCATO in stati:
        return BLOCCATO
    if IN_CORSO in stati or FATTO in stati:
        return IN_CORSO
    return DA_FARE


def calcola_stati(tasks: list[dict]) -> dict[str, str]:
    stati = {fase: stato_fase([t for t in tasks if t['fase'] == fase]) for fase in DIPENDENZE_FASI}
    for fase, dipendenze in DIPENDENZE_FASI.items():
        if stati[fase] == DA_FARE and all(stati[d] == FATTO for d in dipendenze):
            stati[fase] = PRONTA
    return stati


def task_pronti(tasks: list[dict]) -> list[dict]:
    fatti = {t['id'] for t in tasks if t['stato'] == FATTO}
    return [t for t in tasks if t['stato'] == DA_FARE and all(d in fatti for d in t['dipendenze'])]


def genera_blocco(tasks: list[dict], nomi_fasi: dict[str, str]) -> str:
    stati = calcola_stati(tasks)
    obbligatori = [t for t in tasks if not t['facoltativo']]
    fatti = sum(t['stato'] == FATTO for t in obbligatori)
    totale = len(obbligatori) or 1
    pieni = round(10 * fatti / totale)
    barra = '█' * pieni + '░' * (10 - pieni)
    ora = datetime.now().strftime('%Y-%m-%d %H:%M')

    righe = [
        START,
        f'_Generato da `scripts/aggiorna_pipeline.py` il {ora}: non modificare a mano,'
        ' si aggiorna da solo quando cambia [To-do per agenti](todo-agenti.md)._',
        '',
        f'**Avanzamento:** {fatti}/{len(obbligatori)} task obbligatori '
        f'({100 * fatti // totale}%) `{barra}`',
        '',
        f'Legenda: {FATTO} fatta · {IN_CORSO} in corso · {PRONTA} pronta da avviare · '
        f'{DA_FARE} in attesa · {BLOCCATO} bloccata',
        '',
        '```text',
        SCHEMA.format(**stati),
        '```',
        '',
        '| Fase | Stato | Task |',
        '|---|:---:|---|',
    ]
    for fase in DIPENDENZE_FASI:
        elenco = ' · '.join(
            f"{t['id']} {t['stato']}" + (' *(facolt.)*' if t['facoltativo'] else '')
            for t in tasks if t['fase'] == fase
        ) or '—'
        righe.append(f"| {fase} {nomi_fasi.get(fase, '')} | {stati[fase]} | {elenco} |")

    pronti = task_pronti(tasks)
    righe += ['', '**Task pronti da avviare** (dipendenze tutte ✅, eseguibili in parallelo):', '']
    righe += [f"- {t['id']} — {t['titolo']}" for t in pronti] or ['- nessuno']
    righe.append(END)
    return '\n'.join(righe)


def aggiorna() -> str:
    tasks = leggi_task(TODO.read_text(encoding='utf-8'))
    roadmap = ROADMAP.read_text(encoding='utf-8')
    if START not in roadmap or END not in roadmap:
        raise SystemExit(f'Marcatori {START} / {END} non trovati in {ROADMAP}')
    blocco = genera_blocco(tasks, leggi_nomi_fasi(roadmap))
    prima, resto = roadmap.split(START, 1)
    _, dopo = resto.split(END, 1)
    ROADMAP.write_text(prima + blocco + dopo, encoding='utf-8')
    obbligatori = [t for t in tasks if not t['facoltativo']]
    fatti = sum(t['stato'] == FATTO for t in obbligatori)
    pronti = ', '.join(t['id'] for t in task_pronti(tasks)) or 'nessuno'
    return f'Pipeline aggiornata: {fatti}/{len(obbligatori)} task fatti; pronti: {pronti}'


def main() -> int:
    if '--hook' in sys.argv:
        try:
            evento = json.loads(sys.stdin.read() or '{}')
        except json.JSONDecodeError:
            return 0
        percorso = (evento.get('tool_input') or {}).get('file_path', '')
        if not percorso.replace('\\', '/').endswith('wiki/pages/todo-agenti.md'):
            return 0
        print(json.dumps({'systemMessage': aggiorna()}, ensure_ascii=False))
        return 0
    print(aggiorna())
    return 0


if __name__ == '__main__':
    sys.exit(main())
