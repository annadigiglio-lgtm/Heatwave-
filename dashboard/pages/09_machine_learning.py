"""Valutazione e risultati della Pipeline K-Means del progetto."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.express as px
import streamlit as st

from components import PROJECT_ROOT
from components.charts import apply_chart_theme
from components.styling import inject_custom_css, render_sidebar_branding
from src.analysis.spatial_analysis import load_municipality_features
from src.machine_learning.climate_clustering import load_model, predict_clusters

st.set_page_config(page_title='Machine Learning — Heatwave Piemonte', layout='wide')
inject_custom_css()
render_sidebar_branding()


@st.cache_resource
def get_persisted_model():
    return load_model(PROJECT_ROOT / 'models')


@st.cache_data(ttl=600)
def get_model_data() -> pd.DataFrame:
    return load_municipality_features()


st.title('🤖 Machine Learning — cluster climatici')
st.caption(
    'Una Pipeline scikit-learn raggruppa i comuni con caratteristiche climatiche '
    'simili. Il modello è addestrato separatamente, salvato con joblib e ricaricato '
    'in questa pagina.'
)

try:
    pipeline, metadata = get_persisted_model()
    data = get_model_data().copy()
    data['climate_cluster'] = predict_clusters(data, pipeline, metadata)
except (FileNotFoundError, ValueError, OSError) as exc:
    st.error(f'Impossibile caricare il modello climatico: {exc}')
    st.info('Eseguire: `python -m src.machine_learning.train_climate_model`')
    st.stop()
except Exception as exc:
    st.error(f'Database o modello non disponibile: {exc}')
    st.stop()

selected_k = int(metadata['selected_k'])
score = float(metadata['silhouette_score'])

metric_model, metric_k, metric_score, metric_rows = st.columns(4)
metric_model.metric('Modello', 'K-Means')
metric_k.metric('Cluster scelti', selected_k)
metric_score.metric('Silhouette score', f'{score:.3f}')
metric_rows.metric('Comuni', f'{len(data):,}'.replace(',', '.'))

st.info(
    'Il silhouette score varia da −1 a 1: valori più alti indicano gruppi più '
    'compatti e separati. È adatto al clustering non supervisionato; non si usano '
    'accuracy, precision o recall perché non esiste una classe vera nota.'
)

evaluation = pd.DataFrame(metadata['k_evaluation'])
chart = px.line(
    evaluation, x='k', y='silhouette_score', markers=True,
    title='Scelta del numero di cluster',
    labels={'k': 'Numero di cluster (k)', 'silhouette_score': 'Silhouette score'},
)
chart.add_vline(x=selected_k, line_dash='dash', line_color='#e4572e')
st.plotly_chart(apply_chart_theme(chart), width='stretch')
st.caption(
    f'Il valore selezionato è k={selected_k}. La differenza con k=2 è contenuta: '
    'oltre alla metrica, tre gruppi sono mantenuti perché distinguono in modo '
    'interpretabile aree più fresche, intermedie e più calde.'
)

st.subheader('Come è costruito il modello')
left, right = st.columns(2)
with left:
    st.markdown(
        '1. I KPI vengono aggregati per comune da PostgreSQL/PostGIS.\n'
        '2. `StandardScaler` porta le feature sulla stessa scala.\n'
        '3. `KMeans` individua gruppi senza etichette preesistenti.\n'
        '4. Le etichette vengono ordinate dalla temperatura minore alla maggiore.\n'
        '5. Pipeline e metadati sono salvati e ricaricati dalla dashboard.'
    )
with right:
    feature_labels = {
        'temp_mean_avg': 'Temperatura media nel periodo',
        'days_gt_30c_avg': 'Media annuale dei giorni sopra 30 °C',
        'days_gt_35c_avg': 'Media annuale dei giorni sopra 35 °C',
    }
    st.markdown('**Feature utilizzate**')
    for feature in metadata['scikit_learn_features']:
        st.markdown(f'- `{feature}` — {feature_labels.get(feature, feature)}')

cluster_names = {
    cluster_id: name
    for cluster_id, name in enumerate(['Più fresco', 'Intermedio', 'Più caldo'])
}
data['cluster_label'] = data['climate_cluster'].map(cluster_names)
summary = data.groupby(['climate_cluster', 'cluster_label'], as_index=False).agg(
    comuni=('municipality_name', 'count'),
    temperatura_media=('temp_mean_avg', 'mean'),
    giorni_sopra_30=('days_gt_30c_avg', 'mean'),
    giorni_sopra_35=('days_gt_35c_avg', 'mean'),
)
numeric_summary = ['temperatura_media', 'giorni_sopra_30', 'giorni_sopra_35']
summary[numeric_summary] = summary[numeric_summary].round(2)

st.subheader('Interpretazione dei cluster')
st.dataframe(
    summary.rename(columns={
        'climate_cluster': 'Cluster', 'cluster_label': 'Interpretazione',
        'comuni': 'Comuni', 'temperatura_media': 'Temperatura media (°C)',
        'giorni_sopra_30': 'Giorni >30 °C / anno',
        'giorni_sopra_35': 'Giorni >35 °C / anno',
    }),
    hide_index=True, width='stretch',
)

map_chart = px.scatter_map(
    data, lat='lat', lon='lon', color='cluster_label',
    hover_name='municipality_name',
    hover_data={
        'lat': False, 'lon': False, 'temp_mean_avg': ':.1f',
        'days_gt_30c_avg': ':.1f', 'days_gt_35c_avg': ':.1f',
    },
    zoom=6.7, center={'lat': 45.1, 'lon': 7.9}, height=580,
    title='Distribuzione geografica dei cluster',
    labels={
        'cluster_label': 'Cluster', 'temp_mean_avg': 'Temperatura media',
        'days_gt_30c_avg': 'Giorni >30 °C', 'days_gt_35c_avg': 'Giorni >35 °C',
    },
)
map_chart.update_layout(map_style='carto-positron')
st.plotly_chart(apply_chart_theme(map_chart), width='stretch')

with st.expander('Limiti metodologici'):
    st.markdown(
        '- K-Means è esplorativo: i cluster non sono categorie climatiche ufficiali.\n'
        '- La soluzione dipende dalle feature, dalla scala e dal valore di `k`.\n'
        '- Le tre feature sono correlate e descrivono aspetti dello stesso regime termico.\n'
        '- Il risultato di k=3 è solo leggermente superiore a quello di k=2.\n'
        '- Open-Meteo è una rianalisi e presenta differenze rispetto alle stazioni ARPA.\n'
        '- Il modello descrive il periodo osservato e non produce previsioni future.'
    )

st.caption(
    f"Artefatto creato il {metadata['created_at_utc']}; random seed "
    f"{metadata['random_seed']}. Riaddestramento: "
    '`python -m src.machine_learning.train_climate_model`.'
)
