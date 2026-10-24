"""Test dei tool dati del chatbot su parquet sintetici (nessun dato reale, nessuna rete)."""

import json

import pandas as pd
import pytest

from src.chatbot import tools
from src.chatbot.tools import (
    TOOL_DESCRIPTIONS,
    TOOLS,
    compare_locations,
    descrivi_tool_per_prompt,
    esegui_tool,
    get_climate_cluster,
    get_data_coverage,
    get_heatwave_summary,
    get_regional_overview,
    get_temperature_trend,
    normalizza_nome,
)

ANNI = list(range(2020, 2027))
CHIAVI = {'valori', 'unita', 'fonte', 'periodo'}


def _giorni(anno: int) -> int:
    if anno == 2026:
        return 204
    return 366 if anno % 4 == 0 else 365


@pytest.fixture
def cartelle(tmp_path):
    """Scrive parquet minimi con le colonne reali; Acceglio esiste ma non ha dati Open-Meteo."""
    tools.svuota_cache()
    data_dir = tmp_path / 'export'
    models_dir = tmp_path / 'models'
    data_dir.mkdir()
    models_dir.mkdir()

    pd.DataFrame({
        'municipality_name': ['Alessandria', 'Cuneo', 'Mondovì', 'Acceglio'],
        'province_name': ['Alessandria', 'Cuneo', 'Cuneo', 'Cuneo'],
        'elevation_m': [95.0, 534.0, 395.0, 1200.0],
        'lat': [44.91, 44.38, 44.39, 44.47],
        'lon': [8.61, 7.54, 7.82, 6.99],
    }).to_parquet(data_dir / 'municipality_metadata_all.parquet')

    righe = []
    for anno in ANNI:
        # Alessandria: +0,2 °C/anno fino al 2023, poi piatta -> sotto-periodo diverso dall'intero.
        t_ale = 13.0 + 0.2 * (min(anno, 2023) - 2020)
        for nome, temp, d30, d35 in (('Alessandria', t_ale, 40, 6),
                                     ('Cuneo', 11.0, 10, 1),
                                     ('Mondovì', 11.5, 12, 0)):
            righe.append({'municipality_name': nome, 'year': anno, 'total_days': _giorni(anno),
                          'temp_mean_annual': temp, 'temp_max_annual': temp + 22,
                          'temp_min_annual': temp - 20, 'days_gt_30c': d30, 'days_gt_35c': d35,
                          'days_gt_40c': 0})
    pd.DataFrame(righe).to_parquet(data_dir / 'kpi_annual.parquet')

    pd.DataFrame({
        'municipality_name': ['Alessandria', 'Cuneo', 'Mondovì'],
        'n_years': [7, 7, 7],
        'mk_trend': ['increasing', 'no trend', 'no trend'],
        'mk_p_value': [0.01, 0.9, 0.8],
        'mk_sen_slope': [0.1, 0.0, 0.0],
        'lr_slope_per_year': [0.099, 0.0, 0.0],
        'lr_slope_per_decade': [0.99, 0.0, 0.0],
        'lr_p_value': [0.02, 0.9, 0.8],
        'lr_r_squared': [0.7, 0.0, 0.0],
    }).to_parquet(data_dir / 'trend_analysis.parquet')

    pd.DataFrame({
        'municipality_name': ['Alessandria', 'Cuneo', 'Mondovì'],
        'lon': [8.61, 7.54, 7.82], 'lat': [44.91, 44.38, 44.39],
        'temp_mean_avg': [13.4, 11.0, 11.5],
        'days_gt_30c_avg': [40.0, 10.0, 12.0],
        'days_gt_35c_avg': [6.0, 1.0, 0.0],
        'climate_cluster': [2, 1, 1],
    }).to_parquet(data_dir / 'spatial_analysis.parquet')

    eventi = []
    for i in range(12):  # 12 ondate nel 2022 per verificare il limite di 10
        eventi.append({'municipality_name': 'Alessandria', 'province_name': 'Alessandria',
                       'start_date': pd.Timestamp(2022, 6, 1) + pd.Timedelta(days=7 * i),
                       'end_date': pd.Timestamp(2022, 6, 3) + pd.Timedelta(days=7 * i),
                       'duration_days': 3, 'max_temp': 36.0 + i / 10, 'mean_temp': 29.0,
                       'intensity_index': 3.0 + i})
    eventi.append({'municipality_name': 'Cuneo', 'province_name': 'Cuneo',
                   'start_date': pd.Timestamp(2023, 7, 10), 'end_date': pd.Timestamp(2023, 7, 13),
                   'duration_days': 4, 'max_temp': 35.8, 'mean_temp': 27.0, 'intensity_index': 3.2})
    pd.DataFrame(eventi).to_parquet(data_dir / 'heatwave_events.parquet')

    pd.DataFrame({
        'municipality_name': ['Alessandria', 'Cuneo'],
        'n_heatwaves': [12, 1], 'avg_duration_days': [3.0, 4.0], 'max_duration_days': [3, 4],
        'avg_intensity': [8.5, 3.2], 'max_intensity': [14.0, 3.2], 'avg_max_temp': [36.55, 35.8],
    }).to_parquet(data_dir / 'heatwave_stats_by_municipality.parquet')

    pd.DataFrame({
        'municipality_name': ['Cuneo'], 'station_name': ['CUNEO CAMERA COMMERCIO'],
        'temp_max_n_days': [2000], 'temp_max_bias': [-1.5], 'temp_max_mae': [1.9],
        'temp_max_rmse': [2.3], 'temp_max_r': [0.97], 'temp_max_r_p_value': [0.0],
    }).to_parquet(data_dir / 'arpa_validation.parquet')

    province = []
    for anno in ANNI:
        for nome, n_comuni, d30 in (('Alessandria', 1, 40), ('Cuneo', 2, 11)):
            province.append({'province_name': nome, 'year': anno,
                             'total_days': n_comuni * _giorni(anno), 'temp_mean_annual': 12.0,
                             'temp_max_annual': 36.0, 'temp_min_annual': -8.0,
                             'days_gt_30c': d30 * n_comuni, 'days_gt_35c': n_comuni,
                             'days_gt_40c': 0})
    pd.DataFrame(province).to_parquet(data_dir / 'kpi_annual_by_province.parquet')

    pd.DataFrame({'year': [2022, 2023], 'n_heatwaves': [12, 1],
                  'avg_duration_days': [3.0, 4.0], 'avg_intensity': [8.5, 3.2]}
                 ).to_parquet(data_dir / 'heatwave_frequency_by_year.parquet')

    (data_dir / 'overview_stats.json').write_text(json.dumps({
        'n_temperature_rows': 1000, 'date_start': '2020-01-01', 'date_end': '2026-07-23',
        'n_municipalities': 4, 'n_municipalities_with_data': 3, 'n_heatwaves': 13,
        'n_arpa_rows': 2000, 'n_arpa_municipalities': 1,
    }), encoding='utf-8')
    (models_dir / 'climate_kmeans_metadata.json').write_text(json.dumps({
        'model_type': 'StandardScaler + KMeans', 'selected_k': 3, 'silhouette_score': 0.5389,
    }), encoding='utf-8')
    yield {'data_dir': data_dir, 'models_dir': models_dir}
    tools.svuota_cache()


def _controlla(risultato: dict) -> dict:
    assert CHIAVI <= set(risultato), risultato
    json.dumps(risultato)  # deve essere serializzabile
    return risultato


def test_ogni_tool_restituisce_chiavi_attese_e_json(cartelle):
    d, m = cartelle['data_dir'], cartelle['models_dir']
    _controlla(get_temperature_trend('Alessandria', data_dir=d))
    _controlla(get_heatwave_summary('Alessandria', data_dir=d))
    _controlla(get_heatwave_summary('Alessandria', 2022, data_dir=d))
    _controlla(compare_locations('Alessandria', 'Cuneo', data_dir=d))
    _controlla(get_climate_cluster('Cuneo', data_dir=d, models_dir=m))
    _controlla(get_data_coverage(data_dir=d))
    _controlla(get_data_coverage('Cuneo', data_dir=d))
    _controlla(get_regional_overview(2022, data_dir=d))


def test_normalizzazione_maiuscole_accenti_spazi(cartelle):
    assert normalizza_nome('  MONDOVI\u0300 ') == normalizza_nome('mondovi')
    risultato = get_temperature_trend('  MONDOVI  ', data_dir=cartelle['data_dir'])
    assert risultato['valori']['comune'] == 'Mondovì'
    assert get_climate_cluster('cUNeo', data_dir=cartelle['data_dir'],
                               models_dir=cartelle['models_dir'])['valori']['comune'] == 'Cuneo'


def test_comune_inesistente_con_suggerimenti(cartelle):
    with pytest.raises(ValueError, match='Forse intendevi: .*Alessandria'):
        get_temperature_trend('Alesandria', data_dir=cartelle['data_dir'])


def test_comune_senza_dati_open_meteo(cartelle):
    with pytest.raises(ValueError, match='esiste in Piemonte ma non ha dati'):
        get_heatwave_summary('Acceglio', data_dir=cartelle['data_dir'])
    copertura = get_data_coverage('acceglio', data_dir=cartelle['data_dir'])
    assert copertura['valori']['ha_open_meteo'] is False
    assert copertura['valori']['ha_arpa'] is False
    assert any('non ha dati Open-Meteo' in n for n in copertura['note'])


def test_anno_fuori_intervallo_e_periodo_invertito(cartelle):
    d = cartelle['data_dir']
    with pytest.raises(ValueError, match='fuori intervallo'):
        get_heatwave_summary('Cuneo', 1990, data_dir=d)
    with pytest.raises(ValueError, match='fuori intervallo'):
        get_regional_overview(2030, data_dir=d)
    with pytest.raises(ValueError, match='anno_inizio'):
        get_temperature_trend('Cuneo', 2024, 2021, data_dir=d)


def test_comune_con_zero_ondate(cartelle):
    risultato = get_heatwave_summary('Mondovì', data_dir=cartelle['data_dir'])
    assert risultato['valori']['n_ondate'] == 0
    assert risultato['valori']['ondate_piu_intense'] == []
    assert get_heatwave_summary('Mondovì', 2022, data_dir=cartelle['data_dir'])['valori']['n_ondate'] == 0


def test_ondate_limitate_alle_piu_intense(cartelle):
    valori = get_heatwave_summary('Alessandria', 2022, data_dir=cartelle['data_dir'])['valori']
    assert valori['n_ondate'] == 12
    assert len(valori['ondate_piu_intense']) == tools.MAX_ONDATE
    assert valori['ondate_piu_intense'][0]['intensita'] == 14.0


def test_trend_intero_periodo_usa_il_precalcolato(cartelle):
    valori = get_temperature_trend('Alessandria', data_dir=cartelle['data_dir'])['valori']
    assert valori['metodo_trend'].startswith('precalcolato')
    assert valori['pendenza_per_decennio'] == 0.99
    assert valori['significativo'] is True
    assert valori['temp_media_ultimo_anno']['anno'] == 2025  # 2026 parziale escluso


def test_trend_sotto_periodo_ricalcolato(cartelle):
    risultato = get_temperature_trend('alessandria', '2020', 2023, data_dir=cartelle['data_dir'])
    valori = risultato['valori']
    assert valori['metodo_trend'].startswith('ricalcolato')
    assert valori['pendenza_per_decennio'] == pytest.approx(2.0)
    assert valori['temp_media_primo_anno'] == {'anno': 2020, 'valore': 13.0}
    assert risultato['periodo'] == '2020-2023'


def test_confronto_differenza_e_cluster(cartelle):
    valori = compare_locations('Alessandria', 'cuneo', data_dir=cartelle['data_dir'])['valori']
    differenza = valori['differenza (Alessandria - Cuneo)']
    assert differenza['temp_media'] == pytest.approx(2.4)
    assert differenza['n_ondate'] == 11
    assert valori['Cuneo']['cluster_climatico'] == 1


def test_cluster_media_e_numero_comuni(cartelle):
    valori = get_climate_cluster('Cuneo', data_dir=cartelle['data_dir'],
                                 models_dir=cartelle['models_dir'])['valori']
    assert valori['cluster'] == 1
    assert valori['n_comuni_nel_cluster'] == 2
    assert valori['media_feature_cluster']['temp_mean_avg'] == 11.25
    assert valori['modello']['k'] == 3


def test_copertura_con_arpa(cartelle):
    valori = get_data_coverage('Cuneo', data_dir=cartelle['data_dir'])['valori']
    assert valori['ha_open_meteo'] is True and valori['ha_arpa'] is True
    assert valori['validazione_arpa']['bias_temp_max'] == -1.5
    assert valori['provincia'] == 'Cuneo'


def test_quadro_regionale_default_ultimo_anno_completo(cartelle):
    risultato = get_regional_overview(data_dir=cartelle['data_dir'])
    assert risultato['valori']['anno'] == 2025
    parziale = get_regional_overview(2026, data_dir=cartelle['data_dir'])
    assert any('parziale' in n for n in parziale['note'])
    province = {p['provincia']: p for p in parziale['valori']['province']}
    assert province['Cuneo']['n_comuni_con_dati'] == 2
    assert province['Cuneo']['giorni_gt_30c_medi_per_comune'] == 11.0


def test_esegui_tool_whitelist_e_parametri(cartelle):
    d = cartelle['data_dir']
    assert 'errore' in esegui_tool('os.system', {'comando': 'dir'}, data_dir=d)
    assert 'errore' in esegui_tool('get_climate_cluster', {'comune': 'Cuneo', 'data_dir': 'C:/'}, data_dir=d)
    assert 'errore' in esegui_tool('compare_locations', {'comune_a': 'Cuneo'}, data_dir=d)
    assert 'errore' in esegui_tool('get_heatwave_summary', {'comune': 'Cuneo', 'anno': 'ieri'}, data_dir=d)
    errore = esegui_tool('get_climate_cluster', {'comune': 'Cunneo'}, data_dir=d)
    assert 'Cuneo' in errore['errore']


def test_esegui_tool_converte_anni_stringa(cartelle):
    risultato = esegui_tool('get_heatwave_summary', {'comune': 'Alessandria', 'anno': '2022'},
                            data_dir=cartelle['data_dir'])
    assert risultato['valori']['anno'] == 2022
    risultato = esegui_tool('get_climate_cluster', {'comune': 'Cuneo'},
                            data_dir=cartelle['data_dir'], models_dir=cartelle['models_dir'])
    assert risultato['valori']['cluster'] == 1


def test_esegui_tool_errore_interno_non_solleva(cartelle, monkeypatch):
    def guasto(**_):
        raise RuntimeError('disco pieno')
    monkeypatch.setitem(TOOLS, 'get_data_coverage', guasto)
    assert 'disco pieno' in esegui_tool('get_data_coverage', {}, data_dir=cartelle['data_dir'])['errore']


def test_registro_e_descrizioni_coerenti():
    assert set(TOOLS) == set(TOOL_DESCRIPTIONS)
    testo = descrivi_tool_per_prompt()
    for nome in TOOLS:
        assert nome in testo
    assert len(TOOLS) == 6
