"""
Home.py - Heatwave Piemonte Dashboard (pagina principale)

Entry point Streamlit. Le altre pagine sono in `pages/` (convenzione
multipage di Streamlit): 02_analisi_temporale, 03_analisi_spaziale,
04_ondate_di_calore, 05_contesto_territoriale, 06_sintesi_della_ricerca,
07_download_dati, 08_citazioni_e_fonti, 09_machine_learning,
10_assistente_climatico, 11_etica_e_limiti.

Usage:
    streamlit run dashboard/Home.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import folium
import streamlit as st
from branca.colormap import LinearColormap
from streamlit_folium import st_folium

from components.constants import MAP_TILES, THEME_COLD, THEME_HOT, THEME_MID, format_mk_trend
from components.maps import render_gradient_legend, wkt_to_geojson
from components.queries import (
    get_arpa_overview_stats,
    get_combined_heatwave_count,
    get_combined_municipality_geometries_wkt,
    get_combined_trend_analysis,
    get_n_municipalities_both_sources,
    get_overview_stats,
)
from components.styling import (
    inject_custom_css, render_hero, render_nav_card_header, render_sidebar_branding, render_stats_row,
)
from src.utils.config import config

st.set_page_config(
    page_title=config.get('dashboard.title', 'Heatwave Piemonte'),
    layout='wide',
)
inject_custom_css()
render_sidebar_branding()

stats = get_overview_stats()
arpa_stats = get_arpa_overview_stats()
n_years = stats['date_end'].year - stats['date_start'].year + 1
# Copertura combinata: unione dei comuni Open-Meteo (599) e ARPA (218),
# tutti e 218 in comune a entrambe (copertura ARPA completa dal 2026-07-23)
# - non una somma ingenua (599+218), che conterebbe due volte quei 218.
# Vedi docs/pages/dashboard.md.
combined_trend_df = get_combined_trend_analysis()
n_municipalities_combined = combined_trend_df['municipality_name'].nunique() if not combined_trend_df.empty else 0
n_rows_combined = stats['n_temperature_rows'] + arpa_stats['n_arpa_rows']

render_hero(
    eyebrow="Heatwave Piemonte — analisi spazio-temporale",
    title="Il riscaldamento del Piemonte",
    lede=(
        f"<b>{n_years} anni di dati meteorologici reali</b> per capire come sta "
        "cambiando il clima in Piemonte: le temperature stanno davvero salendo? "
        "Ci sono zone della regione più colpite di altre? E quanto sono "
        "diventate più frequenti e intense le <b>ondate di calore</b>?"
    ),
    meta=[
        ("Periodo", f"{stats['date_start'].year}–{stats['date_end'].year}"),
        ("Comuni con dati (Open-Meteo + ARPA)", f"{n_municipalities_combined} / {stats['n_municipalities']}"),
        ("Ultimo aggiornamento", stats['date_end'].strftime('%d/%m/%Y')),
    ],
)

st.subheader("Esplora la dashboard")
CARD_HEIGHT = 280  # altezza fissa: senza, ogni card si dimensiona sul proprio testo (vedi docs/log.md 2026-07-16)
card1, card2, card3 = st.columns(3)
with card1:
    with st.container(key="navcard-temporale", height=CARD_HEIGHT):
        render_nav_card_header(
            icon="📈", title="Analisi Temporale",
            description=(
                "Le temperature stanno davvero salendo? Trend, anomalie, "
                "confronto tra stagioni e variabilità nel tempo, comune per comune."
            ),
        )
        st.page_link("pages/02_analisi_temporale.py", label="Vai alla pagina →")
with card2:
    with st.container(key="navcard-spaziale", height=CARD_HEIGHT):
        render_nav_card_header(
            icon="🗺️", title="Analisi Spaziale",
            description=(
                "Quali zone del Piemonte sono più calde o si scaldano più in "
                "fretta? Mappe per provincia, fascia altitudinale, isola di "
                "calore urbana."
            ),
        )
        st.page_link("pages/03_analisi_spaziale.py", label="Vai alla pagina →")
with card3:
    with st.container(key="navcard-ondate", height=CARD_HEIGHT):
        render_nav_card_header(
            icon="🔥", title="Ondate di Calore",
            description=(
                "Quando, dove e quanto intense sono state le ondate di calore "
                "dal 2000 a oggi, e se il fenomeno sta accelerando."
            ),
        )
        st.page_link("pages/04_ondate_di_calore.py", label="Vai alla pagina →")

card4, card5, card6, card7 = st.columns(4)
with card4:
    with st.container(key="navcard-territoriale", height=CARD_HEIGHT):
        render_nav_card_header(
            icon="🌍", title="Contesto Territoriale",
            description=(
                "Uso del suolo, densità di popolazione e verde da satellite per "
                "tutti i 1180 comuni piemontesi, e il loro legame con la "
                "temperatura osservata."
            ),
        )
        st.page_link("pages/05_contesto_territoriale.py", label="Vai alla pagina →")
with card5:
    with st.container(key="navcard-sintesi", height=CARD_HEIGHT):
        render_nav_card_header(
            icon="🔬", title="Sintesi della Ricerca",
            description=(
                "Cosa dicono 26 anni di dati sul clima piemontese: i "
                "risultati principali del progetto, in breve."
            ),
        )
        st.page_link("pages/06_sintesi_della_ricerca.py", label="Vai alla pagina →")
with card6:
    with st.container(key="navcard-download", height=CARD_HEIGHT):
        render_nav_card_header(
            icon="⬇️", title="Download Dati",
            description=(
                "Tutti i dati e i risultati di analisi mostrati in questo sito, "
                "scaricabili in formato CSV."
            ),
        )
        st.page_link("pages/07_download_dati.py", label="Vai alla pagina →")
with card7:
    with st.container(key="navcard-citazioni", height=CARD_HEIGHT):
        render_nav_card_header(
            icon="📚", title="Citazioni e Fonti",
            description=(
                "Da dove vengono i dati e quale letteratura scientifica è stata "
                "usata per definizioni, metodi e confronti."
            ),
        )
        st.page_link("pages/08_citazioni_e_fonti.py", label="Vai alla pagina →")

st.divider()

st.warning(
    f"**Limite importante dei dati**: le temperature reali coprono "
    f"**{n_municipalities_combined} dei {stats['n_municipalities']} comuni "
    f"piemontesi** — {stats['n_municipalities_with_data']} con dati Open-Meteo "
    f"e {arpa_stats['n_arpa_municipalities']} con dati ARPA (stazione reale), "
    f"{get_n_municipalities_both_sources()} dei quali con entrambe le fonti — non un censimento completo. Gli "
    "8 capoluoghi di provincia più altri comuni scelti per coprire bene il "
    "territorio (zone di montagna, pianura, collina). Le pagine di analisi "
    "hanno un selettore per scegliere quale fonte guardare comune per "
    "comune; questa Home e la mappa/tabella sotto usano invece l'**unione** "
    "delle due (Open-Meteo dove disponibile, ARPA per i comuni scoperti da "
    "Open-Meteo)."
)

st.subheader("Il progetto in numeri")
st.caption("Open-Meteo + ARPA combinati (unione dei comuni, mai la stessa ondata contata due volte).")
render_stats_row([
    {
        'label': "Righe di temperatura", 'unit': "Open-Meteo + ARPA", 'color': THEME_COLD,
        'value': f"{n_rows_combined:,}".replace(',', '.'),
        'spark': [0.3, 0.35, 0.5, 0.45, 0.65, 0.6, 0.8, 1.0],
        'unit_wrap': True,
    },
    {
        'label': "Periodo coperto", 'unit': f"{n_years} anni", 'color': THEME_MID,
        'value': f"{stats['date_start'].year}–{stats['date_end'].year}",
        'spark': [0.1, 0.2, 0.3, 0.4, 0.55, 0.7, 0.85, 1.0],
        'unit_wrap': True,
    },
    {
        'label': "Comuni con dati reali", 'unit': f"/ {stats['n_municipalities']}", 'color': THEME_MID,
        'value': str(n_municipalities_combined),
        'spark': [0.15, 0.15, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0],
    },
    {
        'label': "Ondate di calore identificate", 'unit': "eventi", 'color': THEME_HOT,
        'value': str(get_combined_heatwave_count()),
        'spark': [0.05, 0.1, 0.15, 0.3, 0.4, 0.55, 0.75, 1.0],
    },
])

st.divider()

geo_df = get_combined_municipality_geometries_wkt()
trend_df = combined_trend_df

st.subheader("Velocità di riscaldamento per comune")
st.caption(
    f"Ogni comune è colorato in base a quanto si è scaldato tra il "
    f"{stats['date_start'].year} e il {stats['date_end'].year}: più il "
    "colore vira verso il rosso, più il riscaldamento è stato rapido; il "
    "blu segnala le zone rimaste più stabili (o leggermente più fresche). "
    f"{stats['n_municipalities_with_data']} comuni usano il trend Open-Meteo, "
    f"{n_municipalities_combined - stats['n_municipalities_with_data']} (senza dati Open-Meteo) "
    "usano il trend ARPA — vedi la colonna \"Fonte\" nella tabella sotto. Passa il mouse su un "
    "comune per il valore esatto."
)
m = folium.Map(location=[45.0, 8.0], zoom_start=8, tiles=MAP_TILES)

if trend_df.empty:
    for _, row in geo_df.iterrows():
        folium.GeoJson(
            wkt_to_geojson(row['geometry_wkt']),
            tooltip=f"{row['municipality_name']} ({row['province_name']})",
            style_function=lambda _: {'fillColor': '#e74c3c', 'color': '#c0392b', 'fillOpacity': 0.5},
        ).add_to(m)
    st_folium(m, width=None, height=420, returned_objects=[])
    st.info("Dati di trend non ancora disponibili per colorare la mappa.")
else:
    merged = geo_df.merge(trend_df[['municipality_name', 'lr_slope_per_decade', 'source']], on='municipality_name')
    max_abs_slope = merged['lr_slope_per_decade'].abs().max() or 1
    cmap_trend = LinearColormap(['#3498db', '#f7f7f7', '#e74c3c'], vmin=-max_abs_slope, vmax=max_abs_slope)

    for _, row in merged.iterrows():
        color = cmap_trend(row['lr_slope_per_decade'])
        folium.GeoJson(
            wkt_to_geojson(row['geometry_wkt']),
            tooltip=f"{row['municipality_name']} ({row['source']}): {row['lr_slope_per_decade']:+.2f} °C/decade",
            style_function=lambda _, c=color: {'fillColor': c, 'color': '#555', 'weight': 1, 'fillOpacity': 0.75},
        ).add_to(m)
    st_folium(m, width=None, height=420, returned_objects=[])
    render_gradient_legend(
        cmap_trend, -max_abs_slope, max_abs_slope,
        labels=["Raffreddamento", "Riscaldamento lento", "Riscaldamento moderato",
                "Riscaldamento sostenuto", "Riscaldamento rapido"],
        unit="°C/decade", title="Legenda — velocità di riscaldamento", signed=True,
    )

st.subheader(f"Trend di riscaldamento ({stats['date_start'].year}-{stats['date_end'].year})")
if trend_df.empty:
    st.caption("La temperatura media di ogni comune sta salendo, scendendo, o restando stabile?")
    st.info("Dati di trend non ancora disponibili.")
else:
    n_sig_warm = int(((trend_df['lr_p_value'] < 0.05) & (trend_df['lr_slope_per_decade'] > 0)).sum())
    n_sig_cool = int(((trend_df['lr_p_value'] < 0.05) & (trend_df['lr_slope_per_decade'] < 0)).sum())
    cooling_clause = (
        f", mentre {n_sig_cool} comuni di alta quota mostrano un raffreddamento significativo"
        if n_sig_cool else ""
    )
    st.caption(
        f"**Sta salendo**: su {len(trend_df)} comuni con dati, {n_sig_warm} mostrano un trend di "
        "riscaldamento statisticamente significativo (Mann-Kendall e regressione lineare, "
        f"p<0.05){cooling_clause}. Coerente con il 2025, quinto anno più caldo dal 1958 in "
        "Piemonte (ARPA Piemonte, 2026)."
    )
    display_df = trend_df[['municipality_name', 'source', 'mk_trend', 'lr_slope_per_decade', 'lr_p_value']].copy()
    display_df['mk_trend'] = display_df['mk_trend'].apply(format_mk_trend)
    display_df.columns = ['Comune', 'Fonte', 'Trend (Mann-Kendall)', '°C/decade', 'p-value']
    display_df['°C/decade'] = display_df['°C/decade'].round(2)
    display_df['p-value'] = display_df['p-value'].round(4)
    st.dataframe(display_df.sort_values('Comune'), hide_index=True, width='stretch')
    st.caption(
        "Trend significativo se p-value < 0.05. Colonna \"Fonte\": Open-Meteo dove disponibile, "
        "ARPA (stazione reale) per i comuni non coperti da Open-Meteo. Vedi pagina 'Analisi "
        "Temporale' per il confronto diretto comune per comune."
    )

st.divider()
st.subheader("Machine Learning")
st.caption(
    "Come sono stati individuati i regimi climatici? La pagina dedicata mostra "
    "la Pipeline K-Means salvata con joblib, il confronto tra diversi valori di "
    "k, il silhouette score e i limiti del modello."
)
st.page_link("pages/09_machine_learning.py", label="Apri Machine Learning →")

st.subheader("Assistente climatico")
st.caption(
    "Fai domande in italiano su temperature, ondate di calore, trend e metodi: "
    "un assistente AI risponde usando solo i dati e i documenti del progetto, "
    "mostrando tool chiamati e fonti."
)
st.page_link("pages/10_assistente_climatico.py", label="Apri l'Assistente climatico →")

st.subheader("Etica, privacy e limiti")
st.caption(
    "Cosa il progetto è e cosa non è: limiti dei dati e dei modelli, uso "
    "responsabile dell'assistente AI, richiamo ad AI Act e GDPR."
)
st.page_link("pages/11_etica_e_limiti.py", label="Apri Etica e limiti →")

st.divider()
st.caption("Progetto portfolio di analisi dati climatici — Data Engineering / Data Science / GIS.")
