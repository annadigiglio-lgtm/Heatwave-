"""
queries.py - Funzioni di accesso dati per la dashboard.

Nessuna connessione a Postgres: tutti i dati (Open-Meteo, ARPA, risultati di
`src/analysis/*.py`) vengono letti da uno snapshot statico in
`data/dashboard_export/` (Parquet + un JSON), prodotto da
`src/data_processing/export_dashboard_data.py` e tracciato in Git - vedi
docs/pages/dashboard.md per il perché (deploy pubblico senza DB live) e
docs/pages/statistical-analysis.md per i risultati di `src/analysis/`.

Da rilanciare `export_dashboard_data.py` e ricaricare la dashboard dopo ogni
aggiornamento dei dati in locale: qui non c'è mai una query live.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from . import PROJECT_ROOT  # noqa: F401 (side effect: aggiunge la root al sys.path)
from src.utils.config import config


def _export_path(filename: str) -> Path:
    return Path(config.get('paths.dashboard_export')) / filename


# --- Loader di base (un solo pd.read_parquet per file, riusato da più
# funzioni pubbliche) -------------------------------------------------------
#
# Due riduzioni di memoria applicate ai file con una riga per comune/giorno
# (milioni di righe): float64 -> float32 sulle colonne numeriche (precisione
# persa trascurabile per dati di temperatura, ben sotto la risoluzione delle
# misure stesse) e municipality_name/province_name -> category (poche
# centinaia di valori distinti ripetuti su milioni di righe - str/object le
# ripete per intero a ogni riga, category le codifica come interi). Merge/
# groupby/isin restano invariati (pandas 3 li gestisce in modo trasparente
# anche misti a colonne str, verificato). Necessario su Streamlit Community
# Cloud (limite RAM ~1GB): con 599 comuni i precalcolati superano 750MB
# senza queste riduzioni, a ridosso del limite - vedi docs/log.md 2026-07-24.

def _shrink_memory(df: pd.DataFrame) -> pd.DataFrame:
    float_cols = df.select_dtypes(include='float64').columns
    if len(float_cols):
        df[float_cols] = df[float_cols].astype('float32')
    for col in ('municipality_name', 'province_name'):
        if col in df.columns:
            df[col] = df[col].astype('category')
    return df


@st.cache_data(ttl=600)
def _load_temperature_daily_all() -> pd.DataFrame:
    return _shrink_memory(pd.read_parquet(_export_path('temperature_daily_all.parquet')))


@st.cache_data(ttl=600)
def _load_arpa_temperature_daily_all() -> pd.DataFrame:
    return _shrink_memory(pd.read_parquet(_export_path('arpa_temperature_daily_all.parquet')))


@st.cache_data(ttl=600)
def _load_municipality_metadata_all() -> pd.DataFrame:
    return pd.read_parquet(_export_path('municipality_metadata_all.parquet'))


@st.cache_data(ttl=600)
def _load_all_municipality_geometries() -> pd.DataFrame:
    return pd.read_parquet(_export_path('all_municipality_geometries.parquet'))


@st.cache_data(ttl=600)
def _load_seasonal_decomposition_all() -> pd.DataFrame:
    path = _export_path('seasonal_decomposition_all.parquet')
    if not path.exists():
        return pd.DataFrame()
    return _shrink_memory(pd.read_parquet(path))


# --- Overview / KPI ---------------------------------------------------------

@st.cache_data(ttl=600)
def get_overview_stats() -> dict:
    """Statistiche generali Open-Meteo per la home page."""
    with open(_export_path('overview_stats.json'), 'r', encoding='utf-8') as f:
        stats = json.load(f)
    return {
        'n_temperature_rows': stats['n_temperature_rows'],
        'date_start': pd.Timestamp(stats['date_start']).date(),
        'date_end': pd.Timestamp(stats['date_end']).date(),
        'n_municipalities': stats['n_municipalities'],
        'n_municipalities_with_data': stats['n_municipalities_with_data'],
        'n_heatwaves': stats['n_heatwaves'],
    }


@st.cache_data(ttl=600)
def get_arpa_overview_stats() -> dict:
    """Statistiche generali ARPA (equivalenti a `get_overview_stats()`), per la Home combinata."""
    with open(_export_path('overview_stats.json'), 'r', encoding='utf-8') as f:
        stats = json.load(f)
    return {'n_arpa_rows': stats['n_arpa_rows'], 'n_arpa_municipalities': stats['n_arpa_municipalities']}


@st.cache_data(ttl=600)
def get_combined_trend_analysis() -> pd.DataFrame:
    """
    Trend per **tutti** i comuni con dati reali, unendo le due fonti invece
    di limitarsi a Open-Meteo: i 599 comuni Open-Meteo usano il trend
    Open-Meteo (fonte più validata finora, vedi
    docs/pages/statistical-analysis.md), i comuni **solo ARPA** (nessun
    dato Open-Meteo) usano il trend ARPA calcolato al volo
    (`get_arpa_trend_analysis()`) - nessuna doppia conta: ogni comune
    compare una sola volta, con un'unica fonte. Colonna `source` aggiunta
    per distinguere le due provenienze in tabella/mappa. Usata dalla Home
    per estendere la copertura mostrata oltre i soli comuni Open-Meteo.
    """
    om = get_trend_analysis().copy()
    if not om.empty:
        om['source'] = 'Open-Meteo'
    arpa_names = get_arpa_municipality_names_with_data()
    om_names = set(om['municipality_name']) if not om.empty else set()
    arpa_only_names = [n for n in arpa_names if n not in om_names]
    if arpa_only_names:
        arpa = get_arpa_trend_analysis()
        arpa = arpa[arpa['municipality_name'].isin(arpa_only_names)].copy()
        arpa['source'] = 'ARPA'
    else:
        arpa = pd.DataFrame()
    return pd.concat([om, arpa], ignore_index=True) if not arpa.empty else om


@st.cache_data(ttl=600)
def get_combined_municipality_geometries_wkt() -> pd.DataFrame:
    """Geometrie (WKT) di tutti i comuni con dati reali, Open-Meteo o ARPA (unione)."""
    om_names = set(get_municipality_names_with_data())
    arpa_names = set(get_arpa_municipality_names_with_data())
    all_names = om_names | arpa_names
    geo_all = get_all_municipality_geometries_wkt()
    return geo_all[geo_all['municipality_name'].isin(all_names)]


@st.cache_data(ttl=600)
def get_combined_heatwave_count() -> int:
    """
    N. ondate di calore totali sull'unione dei comuni: quelle già in
    `heatwave_events` (Open-Meteo) più quelle rilevate al volo su ARPA
    **solo** per i comuni senza Open-Meteo - mai sommando due conteggi per
    lo stesso comune (sarebbe la stessa ondata reale contata due volte da
    due metodi diversi, non due ondate diverse).
    """
    from components.heatwave_definitions import identify_heatwaves_events

    om_count = len(get_heatwave_events())
    om_names = set(get_municipality_names_with_data())
    arpa_names = set(get_arpa_municipality_names_with_data())
    arpa_only_names = tuple(sorted(arpa_names - om_names))
    if not arpa_only_names:
        return om_count
    daily = get_arpa_daily_temperature_multi(arpa_only_names)
    arpa_only_events = identify_heatwaves_events(daily)
    return om_count + len(arpa_only_events)


@st.cache_data(ttl=600)
def get_kpi_annual() -> pd.DataFrame:
    """Serie annuale di KPI per comune (vista kpi_annual_by_municipality)."""
    return pd.read_parquet(_export_path('kpi_annual.parquet'))


@st.cache_data(ttl=600)
def get_kpi_annual_by_province() -> pd.DataFrame:
    """Serie annuale di KPI per provincia (vista kpi_annual_by_province)."""
    return pd.read_parquet(_export_path('kpi_annual_by_province.parquet'))


# --- Serie giornaliere Open-Meteo -------------------------------------------

@st.cache_data(ttl=600, max_entries=50)
def get_daily_temperature(municipality_name: str) -> pd.DataFrame:
    """Serie giornaliera di temperatura per un comune."""
    daily = _load_temperature_daily_all()
    cols = ['date', 'temp_mean', 'temp_max', 'temp_min', 'precipitation']
    df = daily.loc[daily['municipality_name'] == municipality_name, cols]
    return df.sort_values('date').reset_index(drop=True)


@st.cache_data(ttl=600, max_entries=20)
def get_daily_temperature_aggregate(municipality_names: tuple) -> pd.DataFrame:
    """
    Media giornaliera di temperatura sui comuni indicati - usata per
    l'opzione "Piemonte / media dei comuni filtrati" nella pagina Analisi
    Temporale. È una media aritmetica non pesata per popolazione/superficie
    dei soli comuni con dati reali passati in `municipality_names`, non una
    stima ufficiale della temperatura regionale (vedi
    docs/pages/etl-pipeline.md per la granularità reale dei dati).
    """
    daily = _load_temperature_daily_all()
    subset = daily[daily['municipality_name'].isin(municipality_names)]
    cols = ['temp_mean', 'temp_max', 'temp_min', 'precipitation']
    return subset.groupby('date', as_index=False)[cols].mean().sort_values('date').reset_index(drop=True)


@st.cache_data(ttl=600)
def get_heatwave_events() -> pd.DataFrame:
    """Tutte le ondate di calore rilevate, con nome comune/provincia."""
    return pd.read_parquet(_export_path('heatwave_events.parquet'))


@st.cache_data(ttl=600)
def get_municipality_geometries_wkt() -> pd.DataFrame:
    """Geometrie (come WKT) dei comuni che hanno dati di temperatura Open-Meteo reali, per la mappa."""
    names = set(get_municipality_names_with_data())
    geo_all = _load_all_municipality_geometries()
    return geo_all[geo_all['municipality_name'].isin(names)].reset_index(drop=True)


# --- Risultati precalcolati di src/analysis/*.py ----------------------------

@st.cache_data(ttl=600)
def get_trend_analysis() -> pd.DataFrame:
    """Risultati di src/analysis/trend_analysis.py (Mann-Kendall + regressione)."""
    path = _export_path('trend_analysis.parquet')
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(ttl=600)
def get_heatwave_stats_by_municipality() -> pd.DataFrame:
    """Risultati di src/analysis/heatwave_stats.py."""
    path = _export_path('heatwave_stats_by_municipality.parquet')
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(ttl=600)
def get_arpa_validation() -> pd.DataFrame:
    """Bias/MAE/RMSE/correlazione Open-Meteo vs ARPA per comune (src/analysis/validate_arpa.py)."""
    path = _export_path('arpa_validation.parquet')
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(ttl=600)
def get_arpa_hot_day_bias() -> pd.DataFrame:
    """Bias per condizione (tutti i giorni / giorni caldi), src/analysis/validate_arpa.py."""
    path = _export_path('arpa_hot_day_bias.parquet')
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(ttl=600)
def get_arpa_trend_comparison() -> pd.DataFrame:
    """Confronto trend ARPA vs Open-Meteo per comune, src/analysis/validate_arpa.py."""
    path = _export_path('arpa_trend_comparison.parquet')
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(ttl=600)
def get_arpa_event_comparison_summary() -> dict:
    """Precision/recall delle ondate Open-Meteo vs ARPA (src/analysis/validate_arpa.py), riga unica."""
    path = _export_path('arpa_event_comparison_summary.parquet')
    if not path.exists():
        return {}
    return pd.read_parquet(path).iloc[0].to_dict()


@st.cache_data(ttl=600)
def get_heatwave_frequency_by_year() -> pd.DataFrame:
    path = _export_path('heatwave_frequency_by_year.parquet')
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(ttl=600)
def get_spatial_analysis() -> pd.DataFrame:
    """Risultati di src/analysis/spatial_analysis.py (cluster climatici)."""
    path = _export_path('spatial_analysis.parquet')
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(ttl=600)
def get_ml_features() -> pd.DataFrame:
    """
    Feature per comune usate dalla Pipeline K-Means della pagina Machine
    Learning - stesse colonne di
    `src/analysis/spatial_analysis.py::load_municipality_features()`
    (municipality_name, lon, lat, temp_mean_avg, days_gt_30c_avg,
    days_gt_35c_avg), lette da `spatial_analysis.parquet` invece che da
    PostgreSQL. La colonna `climate_cluster` del parquet viene esclusa:
    i cluster li ricalcola la pagina con il modello salvato in `models/`.
    """
    columns = ['municipality_name', 'lon', 'lat', 'temp_mean_avg', 'days_gt_30c_avg', 'days_gt_35c_avg']
    return pd.read_parquet(_export_path('spatial_analysis.parquet'), columns=columns)


@st.cache_data(ttl=600)
def get_temperature_regression_residuals() -> pd.DataFrame:
    """
    Residui fuori campione del regressore della temperatura media
    (`cross_val_predict` con GroupKFold per provincia), scritti da
    `python -m src.machine_learning.train_temperature_model`. Colonne:
    municipality_name, province_name, lon, lat, osservato, predetto,
    residuo = osservato - predetto. Solleva FileNotFoundError se il file manca.
    """
    return pd.read_parquet(_export_path('temperature_regression_residuals.parquet'))


@st.cache_data(ttl=600)
def get_temperature_regression_metadata() -> dict:
    """
    Metadati JSON del regressore (`models/temperature_regressor_metadata.json`):
    metriche di tutti i modelli x set di feature x schema di CV, importanza
    per permutazione, parametri scelti e note metodologiche. Solleva
    FileNotFoundError se il file manca.
    """
    path = Path(PROJECT_ROOT) / 'models' / 'temperature_regressor_metadata.json'
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


@st.cache_data(ttl=600)
def get_morans_i_summary() -> pd.DataFrame:
    path = _export_path('morans_i_summary.parquet')
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(ttl=600, max_entries=50)
def get_seasonal_decomposition(municipality_name: str) -> pd.DataFrame:
    """Risultati di src/analysis/seasonal_analysis.py per un comune."""
    all_stl = _load_seasonal_decomposition_all()
    if all_stl.empty:
        return pd.DataFrame()
    cols = ['date', 'observed', 'trend', 'seasonal', 'resid']
    df = all_stl.loc[all_stl['municipality_name'] == municipality_name, cols]
    return df.sort_values('date').reset_index(drop=True)


@st.cache_data(ttl=600, max_entries=20)
def get_seasonal_decomposition_aggregate(municipality_names: tuple) -> pd.DataFrame:
    """
    STL decomposition calcolata al volo sulla media giornaliera dei comuni
    indicati (a differenza di `get_seasonal_decomposition`, che legge il
    precalcolato per comune - qui non esiste un precalcolato per
    l'aggregato "Piemonte", quindi si ricalcola con la stessa funzione
    `decompose()` di `src/analysis/seasonal_analysis.py`).
    """
    from src.analysis.seasonal_analysis import decompose

    daily = get_daily_temperature_aggregate(municipality_names)
    if daily.empty:
        return pd.DataFrame()

    series = daily.set_index('date')['temp_mean'].asfreq('D')
    if series.isna().any():
        series = series.interpolate(method='linear')

    decomposed = decompose(series).reset_index()
    return decomposed


# --- Metadati/geometrie comuni e province -----------------------------------

@st.cache_data(ttl=600)
def get_municipality_names_with_data() -> list:
    """Nomi dei comuni con dati di temperatura Open-Meteo reali, ordinati alfabeticamente."""
    names = _load_temperature_daily_all()['municipality_name'].unique()
    return sorted(names.tolist())


@st.cache_data(ttl=600)
def get_municipality_metadata() -> pd.DataFrame:
    """
    Metadati (provincia, elevazione, centroide) dei comuni con dati
    Open-Meteo reali - usato per filtri, fasce altitudinali, mappe.
    """
    names = set(get_municipality_names_with_data())
    meta = _load_municipality_metadata_all()
    return meta[meta['municipality_name'].isin(names)].reset_index(drop=True)


@st.cache_data(ttl=600)
def get_province_geometries_wkt() -> pd.DataFrame:
    """
    Confine reale di ciascuna provincia, ottenuto aggregando via PostGIS
    (`ST_Union`) le geometrie di tutti i 1180 comuni ISTAT che appartengono
    a quella provincia (non solo quelli con dati di temperatura) - usato per
    la mappa coropletica a livello provinciale.
    """
    return pd.read_parquet(_export_path('province_geometries.parquet'))


@st.cache_data(ttl=600)
def get_land_cover_with_population() -> pd.DataFrame:
    """
    Uso del suolo (`municipality_land_cover`) e popolazione/densità per i
    comuni con dati di temperatura Open-Meteo reali.
    """
    df = pd.read_parquet(_export_path('land_cover_with_population.parquet'))
    df['pop_density'] = df['population'] / df['area_km2']
    return df


@st.cache_data(ttl=600)
def get_land_cover_all() -> pd.DataFrame:
    """
    Uso del suolo e popolazione/densità per **tutti i 1180 comuni**
    piemontesi (non solo quelli con temperatura, a differenza di
    `get_land_cover_with_population`).
    """
    df = pd.read_parquet(_export_path('land_cover_all.parquet'))
    df['pop_density'] = df['population'] / df['area_km2']
    return df


@st.cache_data(ttl=600)
def get_all_municipality_geometries_wkt() -> pd.DataFrame:
    """Geometrie (come WKT) di **tutti i 1180 comuni** piemontesi."""
    return _load_all_municipality_geometries()


@st.cache_data(ttl=600)
def get_ndvi_all() -> pd.DataFrame:
    """
    NDVI medio (`municipality_ndvi`) per tutti i 1180 comuni piemontesi -
    copertura completa, indipendente dalla disponibilità di temperatura.
    """
    return pd.read_parquet(_export_path('ndvi_all.parquet'))


# --- ARPA (seconda fonte dati, copre anche comuni senza Open-Meteo) --------

@st.cache_data(ttl=600)
def get_arpa_municipality_names_with_data() -> list:
    """Nomi dei comuni con dati ARPA reali, ordinati alfabeticamente."""
    names = _load_arpa_temperature_daily_all()['municipality_name'].unique()
    return sorted(names.tolist())


@st.cache_data(ttl=600)
def get_n_municipalities_both_sources() -> int:
    """
    N. comuni con **sia** Open-Meteo sia ARPA (intersezione) - calcolato
    dall'intersezione reale dei due elenchi invece di un numero scritto a
    mano, che altrimenti va aggiornato manualmente in testo statico a ogni
    estensione della copertura (era successo con "108", stale dopo
    l'estensione a 599/218 del 2026-07-23 - vedi docs/log.md).
    """
    om_names = set(get_municipality_names_with_data())
    arpa_names = set(get_arpa_municipality_names_with_data())
    return len(om_names & arpa_names)


@st.cache_data(ttl=600)
def get_n_municipalities_arpa_only() -> int:
    """N. comuni con **solo** ARPA (nessun dato Open-Meteo) - vedi `get_n_municipalities_both_sources()`."""
    om_names = set(get_municipality_names_with_data())
    arpa_names = set(get_arpa_municipality_names_with_data())
    return len(arpa_names - om_names)


@st.cache_data(ttl=600)
def get_arpa_municipality_metadata() -> pd.DataFrame:
    """Provincia, elevazione e centroide per ciascun comune con dati ARPA."""
    names = set(get_arpa_municipality_names_with_data())
    meta = _load_municipality_metadata_all()
    return meta[meta['municipality_name'].isin(names)].reset_index(drop=True)


@st.cache_data(ttl=600, max_entries=50)
def get_arpa_daily_temperature(municipality_name: str) -> pd.DataFrame:
    """Serie giornaliera ARPA (osservazione di stazione reale) per un comune."""
    daily = _load_arpa_temperature_daily_all()
    cols = ['date', 'temp_mean', 'temp_max', 'temp_min']
    df = daily.loc[daily['municipality_name'] == municipality_name, cols]
    return df.sort_values('date').reset_index(drop=True)


@st.cache_data(ttl=600, max_entries=20)
def get_arpa_daily_temperature_multi(municipality_names: tuple) -> pd.DataFrame:
    """
    Serie giornaliera ARPA per più comuni insieme (una riga per
    comune/giorno, non aggregata) - usata per calcolare le ondate di
    calore al volo su un insieme di comuni filtrati, dato che
    `heatwave_events` è popolata solo dalla fonte Open-Meteo.
    """
    if not municipality_names:
        return pd.DataFrame(columns=['municipality_name', 'date', 'temp_mean', 'temp_max', 'temp_min'])
    daily = _load_arpa_temperature_daily_all()
    cols = ['municipality_name', 'date', 'temp_mean', 'temp_max', 'temp_min']
    df = daily.loc[daily['municipality_name'].isin(municipality_names), cols]
    return df.sort_values(['municipality_name', 'date']).reset_index(drop=True)


@st.cache_data(ttl=600)
def get_arpa_municipality_geometries_wkt() -> pd.DataFrame:
    """Geometrie (WKT) dei comuni con dati ARPA - equivalente ARPA di `get_municipality_geometries_wkt`."""
    names = set(get_arpa_municipality_names_with_data())
    geo_all = _load_all_municipality_geometries()
    return geo_all[geo_all['municipality_name'].isin(names)].reset_index(drop=True)


@st.cache_data(ttl=600)
def get_arpa_seasonal_decomposition(municipality_name: str) -> pd.DataFrame:
    """
    Scomposizione STL calcolata al volo sulla serie ARPA di un comune - non
    esiste un precalcolato per ARPA (a differenza di
    `get_seasonal_decomposition`, che legge l'output di
    `src/analysis/seasonal_analysis.py`, eseguito solo su Open-Meteo).
    """
    from src.analysis.seasonal_analysis import decompose

    daily = get_arpa_daily_temperature(municipality_name)
    if daily.empty:
        return pd.DataFrame()

    series = daily.set_index('date')['temp_mean'].asfreq('D')
    if series.isna().any():
        series = series.interpolate(method='linear')

    decomposed = decompose(series).reset_index()
    return decomposed


def compute_annual_kpi_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregati annuali (temp_mean_annual/temp_max_annual/temp_min_annual) da
    una serie giornaliera - stessa semantica della vista materializzata
    `kpi_annual_by_municipality` (media di temp_mean, MASSIMO di temp_max,
    MINIMO di temp_min nell'anno, non medie di max/min). Usata per fonti
    senza vista precalcolata (ARPA).
    """
    d = daily.copy()
    d['year'] = d['date'].dt.year
    return d.groupby('year', as_index=False).agg(
        temp_mean_annual=('temp_mean', 'mean'),
        temp_max_annual=('temp_max', 'max'),
        temp_min_annual=('temp_min', 'min'),
    )


@st.cache_data(ttl=600, max_entries=20)
def get_arpa_heatwave_events(municipality_names: tuple, threshold: float = 35.0, min_duration: int = 3) -> pd.DataFrame:
    """
    Ondate di calore (definizione canonica a soglia fissa) calcolate al
    volo sui dati ARPA per l'insieme di comuni indicato - non esiste una
    `heatwave_events` equivalente per ARPA (popolata solo dalla fonte
    Open-Meteo).
    """
    from components.heatwave_definitions import identify_heatwaves_events

    daily = get_arpa_daily_temperature_multi(municipality_names)
    events = identify_heatwaves_events(daily, threshold=threshold, min_duration=min_duration)
    if events.empty:
        return events
    meta = get_arpa_municipality_metadata()
    return events.merge(meta, on='municipality_name', how='left')


def compute_frequency_by_year(events: pd.DataFrame) -> pd.DataFrame:
    """
    Frequenza/durata/intensità media delle ondate per anno - equivalente
    calcolato al volo di `heatwave_frequency_by_year.csv`
    (`src/analysis/heatwave_stats.py`), usato quando gli eventi vengono da
    una fonte senza precalcolato (ARPA).
    """
    if events.empty:
        return pd.DataFrame(columns=['year', 'n_heatwaves', 'avg_duration_days', 'avg_intensity'])
    e = events.copy()
    e['year'] = e['start_date'].apply(lambda d: d.year)
    return e.groupby('year', as_index=False).agg(
        n_heatwaves=('start_date', 'size'),
        avg_duration_days=('duration_days', 'mean'),
        avg_intensity=('intensity_index', 'mean'),
    )


def compute_stats_by_municipality(events: pd.DataFrame) -> pd.DataFrame:
    """
    Statistiche per comune (n. ondate, durata/intensità media e massima,
    temp. max media) - equivalente calcolato al volo di
    `heatwave_stats_by_municipality.csv`, per fonti senza precalcolato (ARPA).
    """
    if events.empty:
        return pd.DataFrame(columns=[
            'municipality_name', 'n_heatwaves', 'avg_duration_days', 'max_duration_days',
            'avg_intensity', 'max_intensity', 'avg_max_temp',
        ])
    return events.groupby('municipality_name', as_index=False).agg(
        n_heatwaves=('start_date', 'size'),
        avg_duration_days=('duration_days', 'mean'),
        max_duration_days=('duration_days', 'max'),
        avg_intensity=('intensity_index', 'mean'),
        max_intensity=('intensity_index', 'max'),
        avg_max_temp=('max_temp', 'mean'),
    )


@st.cache_data(ttl=600)
def get_arpa_kpi_annual() -> pd.DataFrame:
    """
    Aggregati annuali per comune (stessa semantica di `kpi_annual_by_municipality`,
    vedi `compute_annual_kpi_from_daily`) su tutti i comuni ARPA insieme -
    equivalente ARPA della vista materializzata Open-Meteo, che non esiste
    per questa fonte.
    """
    daily = _load_arpa_temperature_daily_all()
    daily = daily.loc[daily['temp_max'].notna()].copy()
    daily['year'] = daily['date'].dt.year

    grouped = daily.groupby(['municipality_name', 'year'], as_index=False).agg(
        temp_mean_annual=('temp_mean', 'mean'),
        temp_max_annual=('temp_max', 'max'),
        temp_min_annual=('temp_min', 'min'),
    )
    days_30 = daily.loc[daily['temp_max'] > 30].groupby(['municipality_name', 'year']).size()
    days_35 = daily.loc[daily['temp_max'] > 35].groupby(['municipality_name', 'year']).size()

    grouped = grouped.set_index(['municipality_name', 'year'])
    grouped['days_gt_30c'] = days_30
    grouped['days_gt_35c'] = days_35
    grouped[['days_gt_30c', 'days_gt_35c']] = grouped[['days_gt_30c', 'days_gt_35c']].fillna(0).astype(int)
    grouped = grouped.reset_index().sort_values(['municipality_name', 'year']).reset_index(drop=True)

    return grouped[['municipality_name', 'year', 'temp_mean_annual', 'temp_max_annual',
                     'temp_min_annual', 'days_gt_30c', 'days_gt_35c']]


@st.cache_data(ttl=600)
def get_arpa_trend_analysis() -> pd.DataFrame:
    """
    Mann-Kendall + regressione per ciascun comune ARPA - equivalente ARPA
    di `trend_analysis.csv`, mai calcolato in batch su tutti i comuni ARPA
    (il confronto in `validate_arpa.py` copre solo i comuni con anche
    Open-Meteo).
    """
    from src.analysis.trend_analysis import linear_trend, mann_kendall_trend

    annual = get_arpa_kpi_annual()
    results = []
    for name, group in annual.groupby('municipality_name'):
        group = group.sort_values('year')
        if len(group) < 2:
            continue
        row = {'municipality_name': name}
        row.update(mann_kendall_trend(group['temp_mean_annual']))
        row.update(linear_trend(group['year'], group['temp_mean_annual']))
        results.append(row)
    return pd.DataFrame(results)


@st.cache_data(ttl=600)
def get_arpa_municipality_centroids() -> pd.DataFrame:
    """Centroide (lon/lat) dei comuni con dati ARPA - per clustering/Moran's I calcolati al volo."""
    names = set(get_arpa_municipality_names_with_data())
    meta = _load_municipality_metadata_all()
    subset = meta.loc[meta['municipality_name'].isin(names), ['municipality_name', 'lon', 'lat']]
    return subset.reset_index(drop=True)


@st.cache_data(ttl=600)
def get_arpa_municipality_features() -> pd.DataFrame:
    """
    Centroide + feature climatiche aggregate sull'intero periodo per
    ciascun comune ARPA - stesse colonne di
    `src/analysis/spatial_analysis.py::load_municipality_features()`
    (municipality_name, lon, lat, temp_mean_avg, days_gt_30c_avg,
    days_gt_35c_avg), drop-in per `climate_clustering()`/
    `build_inverse_distance_weights()`/`morans_i_permutation_test()`.
    """
    annual = get_arpa_kpi_annual()
    agg = annual.groupby('municipality_name', as_index=False).agg(
        temp_mean_avg=('temp_mean_annual', 'mean'),
        days_gt_30c_avg=('days_gt_30c', 'mean'),
        days_gt_35c_avg=('days_gt_35c', 'mean'),
    )
    centroids = get_arpa_municipality_centroids()
    return centroids.merge(agg, on='municipality_name')


@st.cache_data(ttl=600)
def get_arpa_spatial_clustering(k: int = 3) -> pd.DataFrame:
    """Cluster climatici K-means calcolati al volo sui comuni ARPA (stesso metodo/k di `spatial_analysis.py`)."""
    from src.analysis.spatial_analysis import climate_clustering

    features = get_arpa_municipality_features()
    if features.empty:
        return features
    features = features.copy()
    features['climate_cluster'] = climate_clustering(features, k=k)
    return features


@st.cache_data(ttl=600)
def get_arpa_morans_i() -> dict:
    """Indice di Moran (permutazione) calcolato al volo sui comuni ARPA (stesso metodo di `spatial_analysis.py`)."""
    from src.analysis.spatial_analysis import build_inverse_distance_weights, morans_i_permutation_test

    features = get_arpa_municipality_features()
    if len(features) < 3:
        return {}
    w = build_inverse_distance_weights(features)
    return morans_i_permutation_test(features['temp_mean_avg'].to_numpy(), w)
