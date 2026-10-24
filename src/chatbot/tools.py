"""Tool dati controllati per l'agente del chatbot "Assistente climatico".

L'LLM non esegue mai SQL o codice: può solo chiedere di chiamare una delle
funzioni registrate in ``TOOLS`` (whitelist, lezione 20-03), passando i
parametri descritti in ``TOOL_DESCRIPTIONS``. ``esegui_tool()`` valida nome
e parametri e restituisce sempre un ``dict`` serializzabile in JSON: gli
errori diventano ``{"errore": "..."}`` e arrivano all'agente come
osservazione, senza interrompere il ciclo (lezione 20-04).

I dati sono gli stessi della dashboard (``data/dashboard_export/`` e
``models/``, vedi ``dashboard/components/queries.py``), letti con
``functools.lru_cache`` invece di ``st.cache_data``: il modulo non dipende
da Streamlit. Le cartelle dati e modelli sono parametri, così i test usano
parquet sintetici in una cartella temporanea.
"""

from __future__ import annotations

import difflib
import json
import math
import re
import unicodedata
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from scipy import stats

from src.utils.config import config

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANNO_MIN = 2000
ANNO_MAX = 2026
MAX_ONDATE = 10
SOGLIA_SIGNIFICATIVITA = 0.05
FONTE_OPEN_METEO = 'Open-Meteo Historical Weather API (rianalisi), elaborazioni Heatwave Piemonte'
NOTA_RIANALISI = (
    'Open-Meteo è una rianalisi: rispetto alle stazioni ARPA sottostima le '
    'temperature massime di circa 1,5 °C.'
)
DEFINIZIONE_ONDATA = 'Ondata di calore: almeno 3 giorni consecutivi con temperatura massima > 35 °C.'
SIGNIFICATO_CLUSTER = {
    0: 'alpino / più fresco',
    1: 'intermedio',
    2: 'pianura calda',
}
ESITI_MANN_KENDALL = {
    'increasing': 'crescente',
    'decreasing': 'decrescente',
    'no trend': 'nessun trend significativo',
}


# --- Percorsi e lettura con cache ------------------------------------------

def _cartella(percorso: Path | str | None, chiave_config: str, predefinita: str) -> Path:
    """Risolve una cartella: parametro esplicito oppure valore di ``config.yaml``."""
    if percorso is None:
        percorso = config.get(chiave_config) or predefinita
    cartella = Path(percorso)
    if not cartella.is_absolute():
        cartella = PROJECT_ROOT / cartella
    return cartella


def _data_dir(data_dir: Path | str | None) -> Path:
    return _cartella(data_dir, 'paths.dashboard_export', 'data/dashboard_export')


def _models_dir(models_dir: Path | str | None) -> Path:
    return _cartella(models_dir, 'ml.models_dir', 'models')


@lru_cache(maxsize=32)
def _leggi_parquet_cache(percorso: str) -> pd.DataFrame:
    """Legge un parquet una sola volta per percorso (cache di processo)."""
    file = Path(percorso)
    if not file.exists():
        raise ValueError(f'File dati non disponibile: {file.name}')
    return pd.read_parquet(file)


def _parquet(data_dir: Path | str | None, nome_file: str) -> pd.DataFrame:
    """Restituisce una copia del parquet richiesto, per non alterare la cache."""
    return _leggi_parquet_cache(str(_data_dir(data_dir) / nome_file)).copy()


@lru_cache(maxsize=16)
def _leggi_json_cache(percorso: str) -> dict:
    file = Path(percorso)
    if not file.exists():
        raise ValueError(f'File dati non disponibile: {file.name}')
    with open(file, 'r', encoding='utf-8') as f:
        return json.load(f)


def svuota_cache() -> None:
    """Svuota la cache dei file letti (utile dopo un nuovo export dei dati)."""
    _leggi_parquet_cache.cache_clear()
    _leggi_json_cache.cache_clear()
    _indice_comuni.cache_clear()


# --- Conversione in tipi JSON ------------------------------------------------

def _valore_python(valore: Any, decimali: int = 2) -> Any:
    """Converte numpy/pandas in tipi Python nativi, arrotondando i float."""
    if valore is None:
        return None
    if isinstance(valore, (pd.Timestamp, date)):
        return valore.strftime('%Y-%m-%d')
    if hasattr(valore, 'item') and not isinstance(valore, (str, bytes)):
        valore = valore.item()
    if isinstance(valore, bool):
        return valore
    if isinstance(valore, int):
        return valore
    if isinstance(valore, float):
        if math.isnan(valore) or math.isinf(valore):
            return None
        return round(valore, decimali)
    return valore


def _p_value(valore: Any) -> float | None:
    """I p-value si arrotondano a 4 decimali: con 2 un p=0.0009 diventerebbe 0."""
    return _valore_python(valore, decimali=4)


# --- Validazione parametri ---------------------------------------------------

def normalizza_nome(nome: str) -> str:
    """Normalizza un nome di comune: minuscole, senza accenti, spazi singoli."""
    testo = unicodedata.normalize('NFKD', str(nome))
    testo = ''.join(c for c in testo if not unicodedata.combining(c))
    testo = testo.replace('’', "'").replace('`', "'")
    return re.sub(r'\s+', ' ', testo).strip().casefold()


def _valida_anno(anno: Any, nome_parametro: str = 'anno') -> int:
    """Converte e valida un anno nell'intervallo coperto dai dati."""
    if isinstance(anno, bool):
        raise ValueError(f'{nome_parametro} deve essere un anno intero')
    try:
        valore = int(str(anno).strip()) if isinstance(anno, str) else int(anno)
    except (TypeError, ValueError):
        raise ValueError(f'{nome_parametro} deve essere un anno intero, ricevuto: {anno!r}') from None
    if isinstance(anno, float) and anno != valore:
        raise ValueError(f'{nome_parametro} deve essere un anno intero, ricevuto: {anno!r}')
    if not ANNO_MIN <= valore <= ANNO_MAX:
        raise ValueError(
            f'{nome_parametro}={valore} fuori intervallo: i dati coprono {ANNO_MIN}-{ANNO_MAX}'
        )
    return valore


def _valida_periodo(anno_inizio: Any, anno_fine: Any) -> tuple[int | None, int | None]:
    inizio = _valida_anno(anno_inizio, 'anno_inizio') if anno_inizio is not None else None
    fine = _valida_anno(anno_fine, 'anno_fine') if anno_fine is not None else None
    if inizio is not None and fine is not None and inizio > fine:
        raise ValueError(f'anno_inizio ({inizio}) deve essere <= anno_fine ({fine})')
    return inizio, fine


# --- Comuni ------------------------------------------------------------------

@lru_cache(maxsize=8)
def _indice_comuni(data_dir: str) -> tuple[dict[str, str], frozenset[str]]:
    """Indice ``nome normalizzato -> nome ufficiale`` e insieme dei comuni con dati."""
    con_dati: set[str] = set()
    for nome_file in ('spatial_analysis.parquet', 'trend_analysis.parquet'):
        try:
            con_dati |= set(_parquet(data_dir, nome_file)['municipality_name'])
        except ValueError:
            continue
    try:
        tutti = set(_parquet(data_dir, 'municipality_metadata_all.parquet')['municipality_name'])
    except ValueError:
        tutti = set()
    indice = {normalizza_nome(nome): nome for nome in sorted(tutti | con_dati)}
    return indice, frozenset(con_dati)


def _risolvi_comune(comune: Any, data_dir: Path | str | None, richiede_dati: bool = True) -> str:
    """Restituisce il nome ufficiale del comune o solleva ``ValueError`` chiaro."""
    if not isinstance(comune, str) or not comune.strip():
        raise ValueError('Il parametro comune deve essere un nome di comune non vuoto')
    indice, con_dati = _indice_comuni(str(_data_dir(data_dir)))
    chiave = normalizza_nome(comune)
    if chiave not in indice:
        simili = difflib.get_close_matches(chiave, list(indice), n=3, cutoff=0.6)
        suggerimenti = ', '.join(indice[s] for s in simili)
        messaggio = f"Comune '{comune}' non trovato tra i comuni del Piemonte."
        if suggerimenti:
            messaggio += f' Forse intendevi: {suggerimenti}?'
        raise ValueError(messaggio)
    nome = indice[chiave]
    if richiede_dati and nome not in con_dati:
        raise ValueError(
            f'Il comune {nome} esiste in Piemonte ma non ha dati di temperatura Open-Meteo '
            f'nel progetto (coperti {len(con_dati)} comuni su {len(indice)}): '
            'non posso calcolare questo indicatore.'
        )
    return nome


def _riga_comune(df: pd.DataFrame, nome: str) -> pd.Series | None:
    righe = df.loc[df['municipality_name'] == nome]
    return None if righe.empty else righe.iloc[0]


def _risultato(valori: dict, unita: dict, fonte: str, periodo: str, note: list[str]) -> dict:
    """Formato comune a tutti i tool."""
    risultato = {'valori': valori, 'unita': unita, 'fonte': fonte, 'periodo': periodo}
    if note:
        risultato['note'] = note
    return risultato


def _anni_parziali(kpi: pd.DataFrame) -> list[int]:
    """Anni con meno di 365 giorni osservati (es. 2026, dati fino a luglio)."""
    return sorted(int(a) for a in kpi.loc[kpi['total_days'] < 365, 'year'])


# --- 1. Trend di temperatura -----------------------------------------------

def _trend_mann_kendall(valori: pd.Series) -> dict:
    """Mann-Kendall sul sotto-periodo (pymannkendall, come in trend_analysis.py)."""
    import pymannkendall as mk

    test = mk.original_test(valori.to_numpy())
    return {'esito': ESITI_MANN_KENDALL.get(test.trend, test.trend), 'p_value': _p_value(test.p),
            'sen_slope_per_decennio': _valore_python(test.slope * 10)}


def get_temperature_trend(comune: str, anno_inizio: int | None = None, anno_fine: int | None = None,
                          *, data_dir: Path | str | None = None) -> dict:
    """Trend della temperatura media annua di un comune (°C/decennio, Mann-Kendall)."""
    inizio, fine = _valida_periodo(anno_inizio, anno_fine)
    nome = _risolvi_comune(comune, data_dir)
    kpi = _parquet(data_dir, 'kpi_annual.parquet')
    kpi = kpi.loc[kpi['municipality_name'] == nome].sort_values('year')
    if kpi.empty:
        raise ValueError(f'Nessuna serie annuale disponibile per {nome}')

    anno_min, anno_max = int(kpi['year'].min()), int(kpi['year'].max())
    inizio = anno_min if inizio is None else inizio
    fine = anno_max if fine is None else fine
    periodo = kpi.loc[kpi['year'].between(inizio, fine)]
    if len(periodo) < 3:
        raise ValueError(f'Servono almeno 3 anni di dati per un trend: {nome} ne ha {len(periodo)} '
                         f'nel periodo {inizio}-{fine}')

    note = [NOTA_RIANALISI]
    parziali = _anni_parziali(periodo)
    completi = periodo.loc[~periodo['year'].isin(parziali)]
    if parziali:
        note.append(f'Anni parziali esclusi dalle medie: {parziali} (i dati 2026 finiscono a luglio).')
    if completi.empty:
        completi = periodo

    intero_periodo = inizio <= anno_min and fine >= anno_max
    trend = _riga_comune(_parquet(data_dir, 'trend_analysis.parquet'), nome) if intero_periodo else None
    if trend is not None:
        metodo = 'precalcolato sull\'intero periodo (src/analysis/trend_analysis.py)'
        pendenza = trend['lr_slope_per_decade']
        lr_p = trend['lr_p_value']
        r2 = trend['lr_r_squared']
        mk_esito = {'esito': ESITI_MANN_KENDALL.get(trend['mk_trend'], trend['mk_trend']),
                    'p_value': _p_value(trend['mk_p_value']),
                    'sen_slope_per_decennio': _valore_python(trend['mk_sen_slope'] * 10)}
        if parziali:
            note.append('Il trend precalcolato include anche gli anni parziali.')
    else:
        metodo = f'ricalcolato sul sotto-periodo {inizio}-{fine} (regressione lineare + Mann-Kendall)'
        reg = stats.linregress(periodo['year'], periodo['temp_mean_annual'])
        pendenza, lr_p, r2 = reg.slope * 10, reg.pvalue, reg.rvalue ** 2
        mk_esito = _trend_mann_kendall(periodo['temp_mean_annual'])

    primo, ultimo = completi.iloc[0], completi.iloc[-1]
    valori = {
        'comune': nome,
        'metodo_trend': metodo,
        'pendenza_per_decennio': _valore_python(pendenza),
        'regressione_p_value': _p_value(lr_p),
        'regressione_r2': _valore_python(r2),
        'mann_kendall': mk_esito,
        'significativo': bool(mk_esito['p_value'] is not None
                              and mk_esito['p_value'] < SOGLIA_SIGNIFICATIVITA),
        'n_anni': int(len(periodo)),
        'temp_media_primo_anno': {'anno': int(primo['year']),
                                  'valore': _valore_python(primo['temp_mean_annual'])},
        'temp_media_ultimo_anno': {'anno': int(ultimo['year']),
                                   'valore': _valore_python(ultimo['temp_mean_annual'])},
        'giorni_gt_30c_medi_annui': _valore_python(completi['days_gt_30c'].mean()),
        'giorni_gt_35c_medi_annui': _valore_python(completi['days_gt_35c'].mean()),
    }
    unita = {'pendenza_per_decennio': '°C/decennio', 'temp_media': '°C',
             'giorni': "giorni/anno, media sull'intero periodo (non è una variazione)",
             'significativo': f'p-value Mann-Kendall < {SOGLIA_SIGNIFICATIVITA}'}
    return _risultato(valori, unita, FONTE_OPEN_METEO, f'{inizio}-{fine}', note)


# --- 2. Ondate di calore ---------------------------------------------------

def _ondate_in_lista(eventi: pd.DataFrame) -> list[dict]:
    """Le ondate più intense, al massimo ``MAX_ONDATE``."""
    piu_intense = eventi.sort_values('intensity_index', ascending=False).head(MAX_ONDATE)
    return [{
        'inizio': _valore_python(r.start_date),
        'fine': _valore_python(r.end_date),
        'durata_giorni': _valore_python(r.duration_days),
        'temp_max': _valore_python(r.max_temp),
        'temp_media': _valore_python(r.mean_temp),
        'intensita': _valore_python(r.intensity_index),
    } for r in piu_intense.itertuples()]


def get_heatwave_summary(comune: str, anno: int | None = None, *,
                         data_dir: Path | str | None = None) -> dict:
    """Numero, durata e intensità delle ondate di calore di un comune."""
    anno = _valida_anno(anno) if anno is not None else None
    nome = _risolvi_comune(comune, data_dir)
    eventi = _parquet(data_dir, 'heatwave_events.parquet')
    eventi = eventi.loc[eventi['municipality_name'] == nome].copy()
    eventi['anno'] = pd.to_datetime(eventi['start_date']).dt.year
    note = [DEFINIZIONE_ONDATA, NOTA_RIANALISI]

    if anno is None:
        statistiche = _riga_comune(_parquet(data_dir, 'heatwave_stats_by_municipality.parquet'), nome)
        campi = ('avg_duration_days', 'max_duration_days', 'avg_intensity', 'max_intensity', 'avg_max_temp')
        totali = {campo: (None if statistiche is None else _valore_python(statistiche[campo]))
                  for campo in campi}
        n_ondate = 0 if statistiche is None else int(statistiche['n_heatwaves'])
        valori = {
            'comune': nome,
            'n_ondate': n_ondate,
            'durata_media_giorni': totali['avg_duration_days'],
            'durata_max_giorni': totali['max_duration_days'],
            'intensita_media': totali['avg_intensity'],
            'intensita_max': totali['max_intensity'],
            'temp_max_media_ondate': totali['avg_max_temp'],
            'ondate_per_anno': {str(int(a)): int(n) for a, n in eventi.groupby('anno').size().items()},
            'ondate_piu_intense': _ondate_in_lista(eventi),
        }
        periodo = f'{ANNO_MIN}-{ANNO_MAX} (intero periodo disponibile)'
    else:
        dell_anno = eventi.loc[eventi['anno'] == anno]
        valori = {
            'comune': nome,
            'anno': anno,
            'n_ondate': int(len(dell_anno)),
            'durata_media_giorni': (_valore_python(dell_anno['duration_days'].mean())
                                    if len(dell_anno) else None),
            'durata_max_giorni': _valore_python(dell_anno['duration_days'].max()) if len(dell_anno) else None,
            'intensita_max': _valore_python(dell_anno['intensity_index'].max()) if len(dell_anno) else None,
            'ondate_piu_intense': _ondate_in_lista(dell_anno),
        }
        periodo = str(anno)
        if anno == ANNO_MAX:
            note.append('Il 2026 è parziale: i dati finiscono a luglio.')
    if valori['n_ondate'] == 0:
        note.append('Nessuna ondata di calore rilevata nel periodo: è un risultato, non un dato mancante.')
    elif len(valori['ondate_piu_intense']) == MAX_ONDATE:
        note.append(f'Elenco limitato alle {MAX_ONDATE} ondate più intense.')
    unita = {'durata': 'giorni', 'temperature': '°C',
             'intensita': '°C x giorni: (temp. massima - 35 °C) x durata (intensity_index)'}
    return _risultato(valori, unita, FONTE_OPEN_METEO, periodo, note)


# --- 3. Confronto tra comuni -----------------------------------------------

def _indicatori_comune(nome: str, data_dir: Path | str | None) -> dict:
    spaziale = _riga_comune(_parquet(data_dir, 'spatial_analysis.parquet'), nome)
    trend = _riga_comune(_parquet(data_dir, 'trend_analysis.parquet'), nome)
    ondate = _riga_comune(_parquet(data_dir, 'heatwave_stats_by_municipality.parquet'), nome)
    return {
        'temp_media': None if spaziale is None else _valore_python(spaziale['temp_mean_avg']),
        'trend_per_decennio': None if trend is None else _valore_python(trend['lr_slope_per_decade']),
        'trend_mann_kendall': (None if trend is None
                               else ESITI_MANN_KENDALL.get(trend['mk_trend'], trend['mk_trend'])),
        'giorni_gt_30c_medi_annui': None if spaziale is None else _valore_python(spaziale['days_gt_30c_avg']),
        'giorni_gt_35c_medi_annui': None if spaziale is None else _valore_python(spaziale['days_gt_35c_avg']),
        'n_ondate': 0 if ondate is None else int(ondate['n_heatwaves']),
        'cluster_climatico': None if spaziale is None else int(spaziale['climate_cluster']),
    }


def compare_locations(comune_a: str, comune_b: str, *, data_dir: Path | str | None = None) -> dict:
    """Indicatori climatici di due comuni affiancati, con differenza a - b."""
    nome_a = _risolvi_comune(comune_a, data_dir)
    nome_b = _risolvi_comune(comune_b, data_dir)
    if nome_a == nome_b:
        raise ValueError('Per un confronto servono due comuni diversi')
    a, b = _indicatori_comune(nome_a, data_dir), _indicatori_comune(nome_b, data_dir)
    differenza = {
        chiave: _valore_python(a[chiave] - b[chiave])
        for chiave in a
        if chiave not in ('trend_mann_kendall', 'cluster_climatico')
        and a[chiave] is not None and b[chiave] is not None
    }
    valori = {nome_a: a, nome_b: b, f'differenza ({nome_a} - {nome_b})': differenza,
              'significato_cluster': {str(k): v for k, v in SIGNIFICATO_CLUSTER.items()}}
    unita = {'temp_media': '°C', 'trend_per_decennio': '°C/decennio',
             'giorni': 'giorni/anno (media sul periodo)', 'n_ondate': 'ondate nel periodo'}
    note = [NOTA_RIANALISI, DEFINIZIONE_ONDATA]
    periodo = f"{ANNO_MIN}-{ANNO_MAX} (medie sull'intero periodo)"
    return _risultato(valori, unita, FONTE_OPEN_METEO, periodo, note)


# --- 4. Cluster climatico --------------------------------------------------

FEATURE_CLUSTER = ('temp_mean_avg', 'days_gt_30c_avg', 'days_gt_35c_avg')


def _metadati_modello(models_dir: Path | str | None) -> dict | None:
    try:
        return _leggi_json_cache(str(_models_dir(models_dir) / 'climate_kmeans_metadata.json'))
    except ValueError:
        return None


def get_climate_cluster(comune: str, *, data_dir: Path | str | None = None,
                        models_dir: Path | str | None = None) -> dict:
    """Cluster climatico K-Means del comune, sue feature e media del cluster."""
    nome = _risolvi_comune(comune, data_dir)
    spaziale = _parquet(data_dir, 'spatial_analysis.parquet')
    riga = _riga_comune(spaziale, nome)
    if riga is None:
        raise ValueError(f'Il comune {nome} non ha un cluster climatico calcolato')
    cluster = int(riga['climate_cluster'])
    stesso = spaziale.loc[spaziale['climate_cluster'] == cluster]
    metadati = _metadati_modello(models_dir)
    note = ['Le feature sono medie annue sull\'intero periodo; '
            'le etichette sono ordinate dal cluster più fresco (0) al più caldo.']
    if metadati is None:
        note.append('Metadati del modello non disponibili: k e silhouette non riportati.')
    valori = {
        'comune': nome,
        'cluster': cluster,
        'significato': SIGNIFICATO_CLUSTER.get(cluster, 'non classificato'),
        'feature_comune': {f: _valore_python(riga[f]) for f in FEATURE_CLUSTER},
        'media_feature_cluster': {f: _valore_python(stesso[f].mean()) for f in FEATURE_CLUSTER},
        'n_comuni_nel_cluster': int(len(stesso)),
        'n_comuni_totali': int(len(spaziale)),
        'modello': None if metadati is None else {
            'tipo': metadati.get('model_type'),
            'k': _valore_python(metadati.get('selected_k')),
            'silhouette_score': _valore_python(metadati.get('silhouette_score')),
        },
        'significato_cluster': {str(k): v for k, v in SIGNIFICATO_CLUSTER.items()},
    }
    unita = {'temp_mean_avg': '°C', 'days_gt_30c_avg': 'giorni/anno', 'days_gt_35c_avg': 'giorni/anno'}
    fonte = f'{FONTE_OPEN_METEO}; K-Means (models/climate_kmeans_metadata.json)'
    return _risultato(valori, unita, fonte, f'{ANNO_MIN}-{ANNO_MAX} (medie sull\'intero periodo)', note)


# --- 5. Copertura dei dati -------------------------------------------------

def _overview(data_dir: Path | str | None) -> dict:
    return _leggi_json_cache(str(_data_dir(data_dir) / 'overview_stats.json'))


def get_data_coverage(comune: str | None = None, *, data_dir: Path | str | None = None) -> dict:
    """Quali dati esistono (Open-Meteo, ARPA) per la regione o per un comune."""
    stat = _overview(data_dir)
    periodo = f"{stat.get('date_start')} - {stat.get('date_end')}"
    fonte = 'data/dashboard_export (Open-Meteo, ARPA Piemonte, ISTAT)'
    if comune is None:
        valori = {
            'righe_temperatura_open_meteo': _valore_python(stat.get('n_temperature_rows')),
            'data_inizio': stat.get('date_start'),
            'data_fine': stat.get('date_end'),
            'comuni_piemonte': _valore_python(stat.get('n_municipalities')),
            'comuni_con_open_meteo': _valore_python(stat.get('n_municipalities_with_data')),
            'ondate_rilevate': _valore_python(stat.get('n_heatwaves')),
            'righe_arpa': _valore_python(stat.get('n_arpa_rows')),
            'comuni_con_arpa': _valore_python(stat.get('n_arpa_municipalities')),
        }
        note = [NOTA_RIANALISI, 'L\'ultimo anno è parziale: i dati finiscono alla data_fine indicata.']
        return _risultato(valori, {'righe': 'giorni x comune'}, fonte, periodo, note)

    nome = _risolvi_comune(comune, data_dir, richiede_dati=False)
    _, con_dati = _indice_comuni(str(_data_dir(data_dir)))
    meta = _riga_comune(_parquet(data_dir, 'municipality_metadata_all.parquet'), nome)
    try:
        arpa = _riga_comune(_parquet(data_dir, 'arpa_validation.parquet'), nome)
    except ValueError:
        arpa = None
    valori = {
        'comune': nome,
        'provincia': None if meta is None else meta['province_name'],
        'quota_m': None if meta is None else _valore_python(meta['elevation_m']),
        'ha_open_meteo': nome in con_dati,
        'ha_arpa': arpa is not None,
        'validazione_arpa': None if arpa is None else {
            'stazione': arpa['station_name'],
            'giorni_confrontati': _valore_python(arpa['temp_max_n_days']),
            'bias_temp_max': _valore_python(arpa['temp_max_bias']),
            'mae_temp_max': _valore_python(arpa['temp_max_mae']),
            'rmse_temp_max': _valore_python(arpa['temp_max_rmse']),
            'r_temp_max': _valore_python(arpa['temp_max_r']),
        },
    }
    note = []
    if not valori['ha_open_meteo']:
        note.append(f'{nome} non ha dati Open-Meteo: trend, ondate e cluster non sono disponibili.')
    if arpa is not None:
        note.append('bias = Open-Meteo - ARPA sulla temperatura massima giornaliera '
                    '(negativo = Open-Meteo sottostima).')
    unita = {'quota_m': 'm s.l.m.', 'bias/mae/rmse': '°C', 'r': 'correlazione di Pearson'}
    return _risultato(valori, unita, fonte, periodo, note)


# --- 6. Quadro regionale ---------------------------------------------------

def _giorni_osservati_per_comune(data_dir: Path | str | None, anno: int) -> int:
    """Giorni osservati nell'anno per un comune (204 nel 2026 parziale)."""
    kpi = _parquet(data_dir, 'kpi_annual.parquet')
    giorni = kpi.loc[kpi['year'] == anno, 'total_days']
    return int(giorni.max()) if not giorni.empty else (366 if anno % 4 == 0 else 365)


def _ultimo_anno_completo(data_dir: Path | str | None, anni: list[int]) -> int:
    for anno in sorted(anni, reverse=True):
        if _giorni_osservati_per_comune(data_dir, anno) >= 365:
            return anno
    return max(anni)


def get_regional_overview(anno: int | None = None, *, data_dir: Path | str | None = None) -> dict:
    """Quadro delle province piemontesi e delle ondate regionali in un anno."""
    anno = _valida_anno(anno) if anno is not None else None
    province = _parquet(data_dir, 'kpi_annual_by_province.parquet')
    anni = sorted(int(a) for a in province['year'].unique())
    if not anni:
        raise ValueError('Nessun dato provinciale disponibile')
    if anno is None:
        anno = _ultimo_anno_completo(data_dir, anni)
    if anno not in anni:
        raise ValueError(f'Nessun dato provinciale per il {anno}: anni disponibili {anni[0]}-{anni[-1]}')

    giorni_anno = _giorni_osservati_per_comune(data_dir, anno)
    dell_anno = province.loc[province['year'] == anno].sort_values('temp_mean_annual', ascending=False)
    tabella = []
    for r in dell_anno.itertuples():
        n_comuni = r.total_days / giorni_anno
        tabella.append({
            'provincia': r.province_name,
            'n_comuni_con_dati': int(round(n_comuni)),
            'temp_media': _valore_python(r.temp_mean_annual),
            'temp_max_assoluta': _valore_python(r.temp_max_annual),
            'giorni_gt_30c_medi_per_comune': _valore_python(r.days_gt_30c / n_comuni),
            'giorni_gt_35c_medi_per_comune': _valore_python(r.days_gt_35c / n_comuni),
        })
    frequenza = _parquet(data_dir, 'heatwave_frequency_by_year.parquet')
    riga = frequenza.loc[frequenza['year'] == anno]
    ondate = {
        'n_ondate': int(riga['n_heatwaves'].iloc[0]) if not riga.empty else 0,
        'durata_media_giorni': _valore_python(riga['avg_duration_days'].iloc[0]) if not riga.empty else None,
        'intensita_media': _valore_python(riga['avg_intensity'].iloc[0]) if not riga.empty else None,
    }
    note = [NOTA_RIANALISI, DEFINIZIONE_ONDATA,
            'Le ondate regionali sono la somma degli eventi rilevati in tutti i comuni con dati.']
    if giorni_anno < 365:
        note.append(f'Il {anno} è parziale ({giorni_anno} giorni osservati, i dati finiscono a luglio): '
                    'non confrontarlo con gli anni completi.')
    valori = {'anno': anno, 'province': tabella, 'ondate_regionali': ondate}
    unita = {'temperature': '°C', 'giorni': 'giorni/anno per comune (media provinciale)'}
    return _risultato(valori, unita, FONTE_OPEN_METEO, str(anno), note)


# --- Registro per l'agente (whitelist) -------------------------------------

TOOLS: dict[str, Callable[..., dict]] = {
    'get_temperature_trend': get_temperature_trend,
    'get_heatwave_summary': get_heatwave_summary,
    'compare_locations': compare_locations,
    'get_climate_cluster': get_climate_cluster,
    'get_data_coverage': get_data_coverage,
    'get_regional_overview': get_regional_overview,
}

_COMUNE = {'nome': 'comune', 'tipo': 'str', 'obbligatorio': True,
           'descrizione': 'nome di un comune del Piemonte, es. "Alessandria"'}

TOOL_DESCRIPTIONS: dict[str, dict] = {
    'get_temperature_trend': {
        'descrizione': ('Trend della temperatura media annua di un comune: pendenza in °C/decennio, '
                        'test di Mann-Kendall, significatività, media del primo e ultimo anno.'),
        'parametri': [
            _COMUNE,
            {'nome': 'anno_inizio', 'tipo': 'int', 'obbligatorio': False,
             'descrizione': f'primo anno del periodo ({ANNO_MIN}-{ANNO_MAX})'},
            {'nome': 'anno_fine', 'tipo': 'int', 'obbligatorio': False,
             'descrizione': f'ultimo anno del periodo ({ANNO_MIN}-{ANNO_MAX})'},
        ],
    },
    'get_heatwave_summary': {
        'descrizione': ('Ondate di calore di un comune (>= 3 giorni con massima > 35 °C): '
                        'numero, durata, intensità e le ondate più intense.'),
        'parametri': [
            _COMUNE,
            {'nome': 'anno', 'tipo': 'int', 'obbligatorio': False,
             'descrizione': 'anno da analizzare; se assente, intero periodo'},
        ],
    },
    'compare_locations': {
        'descrizione': ('Confronta due comuni: temperatura media, trend, giorni > 30/35 °C, '
                        'numero di ondate, cluster climatico e differenza tra i due.'),
        'parametri': [
            {'nome': 'comune_a', 'tipo': 'str', 'obbligatorio': True, 'descrizione': 'primo comune'},
            {'nome': 'comune_b', 'tipo': 'str', 'obbligatorio': True, 'descrizione': 'secondo comune'},
        ],
    },
    'get_climate_cluster': {
        'descrizione': ('Cluster climatico K-Means del comune (0 alpino/più fresco, 1 intermedio, '
                        '2 pianura calda), con le sue feature e la media del cluster.'),
        'parametri': [_COMUNE],
    },
    'get_data_coverage': {
        'descrizione': ('Copertura dei dati: senza comune, panoramica regionale; con un comune, '
                        'se ha dati Open-Meteo e ARPA, provincia, quota e bias della stazione ARPA.'),
        'parametri': [
            {**_COMUNE, 'obbligatorio': False},
        ],
    },
    'get_regional_overview': {
        'descrizione': ('Quadro regionale di un anno: temperatura media e giorni > 30/35 °C per '
                        'provincia, ondate di calore regionali. Senza anno: ultimo anno completo.'),
        'parametri': [
            {'nome': 'anno', 'tipo': 'int', 'obbligatorio': False,
             'descrizione': f'anno ({ANNO_MIN}-{ANNO_MAX}); il {ANNO_MAX} è parziale'},
        ],
    },
}


def descrivi_tool_per_prompt() -> str:
    """Elenco testuale dei tool per il system prompt (formato ``TOOL:``/``PARAMS:``)."""
    righe = []
    for indice, (nome, info) in enumerate(TOOL_DESCRIPTIONS.items(), start=1):
        firma = ', '.join(p['nome'] + ('' if p['obbligatorio'] else '?') for p in info['parametri'])
        righe.append(f'{indice}. {nome}({firma}): {info["descrizione"]}')
        for p in info['parametri']:
            stato = 'obbligatorio' if p['obbligatorio'] else 'facoltativo'
            righe.append(f'   - {p["nome"]} ({p["tipo"]}, {stato}): {p["descrizione"]}')
    return '\n'.join(righe)


def _prepara_parametri(nome: str, parametri: Any) -> dict:
    """Controlla parametri sconosciuti/mancanti e converte i tipi dichiarati."""
    if parametri is None:
        parametri = {}
    if not isinstance(parametri, dict):
        raise ValueError('I parametri devono essere un oggetto JSON (dizionario)')
    previsti = {p['nome']: p for p in TOOL_DESCRIPTIONS[nome]['parametri']}
    sconosciuti = sorted(set(parametri) - set(previsti))
    if sconosciuti:
        raise ValueError(f'Parametri non previsti per {nome}: {", ".join(sconosciuti)}. '
                         f'Ammessi: {", ".join(previsti) or "nessuno"}')
    mancanti = [p for p, info in previsti.items()
                if info['obbligatorio'] and parametri.get(p) in (None, '')]
    if mancanti:
        raise ValueError(f'Parametri obbligatori mancanti per {nome}: {", ".join(mancanti)}')
    puliti = {}
    for chiave, valore in parametri.items():
        if valore is None or (isinstance(valore, str) and not valore.strip()):
            continue
        if previsti[chiave]['tipo'] == 'int':
            valore = _valida_anno(valore, chiave)
        elif not isinstance(valore, str):
            raise ValueError(f'Il parametro {chiave} deve essere una stringa')
        puliti[chiave] = valore
    return puliti


def esegui_tool(nome: str, parametri: dict | None = None, *, data_dir: Path | str | None = None,
                models_dir: Path | str | None = None) -> dict:
    """Esegue un tool della whitelist; ogni errore diventa ``{"errore": ...}``."""
    if nome not in TOOLS:
        return {'errore': f"Tool '{nome}' non disponibile. Tool ammessi: {', '.join(TOOLS)}"}
    try:
        argomenti = _prepara_parametri(nome, parametri)
        argomenti['data_dir'] = data_dir
        if nome == 'get_climate_cluster':
            argomenti['models_dir'] = models_dir
        return TOOLS[nome](**argomenti)
    except ValueError as errore:
        return {'errore': str(errore)}
    except Exception as errore:  # noqa: BLE001 - l'agente riceve un'osservazione, mai un crash
        return {'errore': f'Errore interno del tool {nome}: {type(errore).__name__}: {errore}'}
