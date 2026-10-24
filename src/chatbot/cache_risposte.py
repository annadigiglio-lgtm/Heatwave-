"""Cache su disco delle risposte dell'agente (prestazioni su CPU).

Su questo PC una risposta richiede 40-170 s (il modello genera circa 3 token/s).
Una domanda già posta, con la stessa conversazione precedente, la stessa
versione del prompt, lo stesso modello e gli stessi dati, viene quindi
servita dalla cache all'istante; la pagina lo dichiara ("risposta dalla
cache").

La chiave include una **firma dei dati**: data di modifica e dimensione dello
snapshot (`overview_stats.json`), dell'indice RAG (`manifest.json`) e dei
metadati dei modelli. Se uno di questi cambia, le risposte salvate non
vengono più usate. Ogni risposta è un file JSON in ``chatbot.cache_risposte.dir``
(default ``data/cache_risposte/``, non versionato).

Disattivazione: ``chatbot.cache_risposte.enabled: false`` in ``config.yaml``
oppure la variabile d'ambiente ``HEATWAVE_CACHE_RISPOSTE=0`` (usata dai test
e dal benchmark, che devono sempre interrogare il modello).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from src.chatbot.tools import normalizza_nome
from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

VARIABILE_CACHE = 'HEATWAVE_CACHE_RISPOSTE'
CARTELLA_PREDEFINITA = './data/cache_risposte'
RADICE_PROGETTO = Path(__file__).resolve().parents[2]

# File la cui modifica invalida le risposte salvate (relativi alla radice).
FILE_FIRMA = (
    'data/dashboard_export/overview_stats.json',
    'data/vector_store/manifest.json',
    'models/climate_kmeans_metadata.json',
    'models/temperature_regressor_metadata.json',
)


def cache_attiva() -> bool:
    """Vero se la cache è attiva (variabile d'ambiente, poi ``config.yaml``)."""
    valore = os.getenv(VARIABILE_CACHE)
    if valore is not None:
        return valore.strip().lower() not in ('0', 'false', 'no', 'off', '')
    return bool(config.get('chatbot.cache_risposte.enabled', True))


def cartella_cache() -> Path:
    percorso = Path(str(config.get('chatbot.cache_risposte.dir', CARTELLA_PREDEFINITA)))
    return percorso if percorso.is_absolute() else (RADICE_PROGETTO / percorso).resolve()


def firma_dati(radice: Path | None = None) -> str:
    """Impronta di data di modifica e dimensione dei file da cui dipendono le risposte."""
    radice = radice or RADICE_PROGETTO
    parti = []
    for relativo in FILE_FIRMA:
        percorso = radice / relativo
        if percorso.exists():
            stato = percorso.stat()
            parti.append(f'{relativo}:{stato.st_mtime_ns}:{stato.st_size}')
        else:
            parti.append(f'{relativo}:assente')
    return hashlib.sha256('|'.join(parti).encode('utf-8')).hexdigest()[:16]


def _normalizza(testo: str) -> str:
    """Solo lettere e numeri, minuscolo e senza accenti: "Com'è" e "com e" coincidono."""
    return re.sub(r'[^a-z0-9]+', ' ', normalizza_nome(testo)).strip()


def chiave(domanda: str, storia: list[dict], versione: str, modello: str,
           system_prompt: str, firma: str | None = None) -> str:
    """Chiave SHA-256 della risposta: domanda, storia, prompt, modello e dati."""
    contenuto = {
        'domanda': _normalizza(domanda),
        'storia': [(m.get('role'), _normalizza(str(m.get('content', '')))) for m in storia],
        'versione': versione,
        'modello': modello,
        'system_prompt': hashlib.sha256(system_prompt.encode('utf-8')).hexdigest(),
        'dati': firma if firma is not None else firma_dati(),
    }
    testo = json.dumps(contenuto, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(testo.encode('utf-8')).hexdigest()


def leggi(chiave_risposta: str, cartella: Path | None = None) -> dict | None:
    """Risposta salvata oppure ``None`` (file assente o illeggibile)."""
    percorso = (cartella or cartella_cache()) / f'{chiave_risposta}.json'
    if not percorso.exists():
        return None
    try:
        return json.loads(percorso.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as errore:
        logger.warning(f'Cache risposte: file illeggibile ignorato ({type(errore).__name__})')
        return None


def scrivi(chiave_risposta: str, dati: dict, cartella: Path | None = None) -> None:
    """Salva la risposta in modo atomico (file temporaneo + rinomina)."""
    cartella = cartella or cartella_cache()
    cartella.mkdir(parents=True, exist_ok=True)
    finale = cartella / f'{chiave_risposta}.json'
    temporaneo = finale.with_suffix('.tmp')
    temporaneo.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(temporaneo, finale)


def conta(cartella: Path | None = None) -> int:
    cartella = cartella or cartella_cache()
    return len(list(cartella.glob('*.json'))) if cartella.exists() else 0


def svuota(cartella: Path | None = None) -> int:
    """Cancella tutte le risposte salvate; restituisce quante erano."""
    cartella = cartella or cartella_cache()
    if not cartella.exists():
        return 0
    file = list(cartella.glob('*.json'))
    for percorso in file:
        percorso.unlink(missing_ok=True)
    logger.info(f'Cache risposte svuotata: {len(file)} risposte')
    return len(file)
