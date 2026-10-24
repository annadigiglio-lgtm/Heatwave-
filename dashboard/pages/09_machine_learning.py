"""Machine Learning del progetto: clustering K-Means e regressione della temperatura.

La pagina legge solo artefatti già prodotti (`models/` e
`data/dashboard_export/`): nessun database e nessun training qui.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.decomposition import PCA

from components import PROJECT_ROOT
from components.charts import apply_chart_theme
from components.constants import CLUSTER_COLORS
from components.queries import (
    get_ml_features,
    get_temperature_regression_metadata,
    get_temperature_regression_residuals,
)
from components.styling import inject_custom_css, render_sidebar_branding
from src.machine_learning.climate_clustering import FEATURE_COLUMNS, load_model, predict_clusters

st.set_page_config(page_title='Machine Learning — Heatwave Piemonte', layout='wide')
inject_custom_css()
render_sidebar_branding()

CLUSTER_NAMES = {0: 'Più fresco', 1: 'Intermedio', 2: 'Più caldo'}
CLUSTER_COLOR_MAP = {CLUSTER_NAMES[k]: color for k, color in CLUSTER_COLORS.items()}
CLUSTER_ORDER = [CLUSTER_NAMES[k] for k in sorted(CLUSTER_NAMES)]

MODEL_LABELS = {
    'LinearRegression': 'Regressione lineare',
    'RandomForestRegressor': 'Random Forest',
    'MLPRegressor': 'Rete neurale (MLP)',
}
FEATURE_LABELS_REG = {
    'elevation_m': 'Elevazione (m)',
    'population_density': 'Densità di popolazione',
    'pct_urban': '% superficie urbana',
    'pct_forest_seminatural': '% boschi e aree seminaturali',
    'ndvi_mean': 'NDVI medio',
    'lat': 'Latitudine',
    'lon': 'Longitudine',
}
TRAIN_REG_CMD = 'python -m src.machine_learning.train_temperature_model'


@st.cache_resource
def get_persisted_model():
    return load_model(PROJECT_ROOT / 'models')


@st.cache_data(ttl=600)
def compute_pca(features: pd.DataFrame) -> tuple[pd.DataFrame, list[float]]:
    """Proietta le feature (scalate con lo scaler del modello) su 2 componenti."""
    pipeline, _ = get_persisted_model()
    scaled = pipeline.named_steps['scaler'].transform(features[list(FEATURE_COLUMNS)])
    pca = PCA(n_components=2, random_state=42)
    components = pca.fit_transform(scaled)
    projected = pd.DataFrame(components, columns=['PC1', 'PC2'], index=features.index)
    return projected, [float(v) for v in pca.explained_variance_ratio_]


st.title('🤖 Machine Learning')
st.caption(
    'Due componenti di machine learning con scikit-learn: un clustering non '
    'supervisionato (K-Means) dei comuni per regime termico e una regressione '
    'supervisionata della temperatura media dalle caratteristiche del territorio. '
    'I modelli sono addestrati separatamente, salvati con joblib e qui solo '
    'ricaricati: la pagina legge `models/` e lo snapshot Parquet della dashboard, '
    'senza connessione al database.'
)

tab_cluster, tab_reg, tab_limits = st.tabs(
    ['🔵 Clustering (K-Means)', '📈 Regressione (supervisionato)', '⚠️ Limiti']
)

# ---------------------------------------------------------------------------
# Tab 1 — Clustering
# ---------------------------------------------------------------------------


def render_clustering() -> None:
    try:
        data = get_ml_features().copy()
    except (FileNotFoundError, OSError) as exc:
        st.error(f'Snapshot della dashboard non disponibile: {exc}')
        st.info('Eseguire: `python -m src.data_processing.export_dashboard_data`')
        return

    try:
        pipeline, metadata = get_persisted_model()
        data['climate_cluster'] = predict_clusters(data, pipeline, metadata)
    except (FileNotFoundError, ValueError, OSError) as exc:
        st.error(f'Impossibile caricare il modello climatico: {exc}')
        st.info('Eseguire: `python -m src.machine_learning.train_climate_model`')
        return
    except Exception as exc:
        st.error(f'Modello o feature non utilizzabili: {exc}')
        return

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
            '1. I KPI annuali vengono aggregati per comune (snapshot Parquet della dashboard).\n'
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

    data['cluster_label'] = data['climate_cluster'].map(CLUSTER_NAMES)
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
        color_discrete_map=CLUSTER_COLOR_MAP,
        category_orders={'cluster_label': CLUSTER_ORDER},
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

    # --- PCA (lezione 18-02) ---------------------------------------------
    st.subheader('Proiezione PCA a 2 componenti')
    try:
        projected, variance = compute_pca(data[list(FEATURE_COLUMNS)])
    except Exception as exc:
        st.warning(f'Proiezione PCA non disponibile: {exc}')
    else:
        pca_data = pd.concat([data[['municipality_name', 'cluster_label']], projected], axis=1)
        pc1, pc2 = variance[0] * 100, variance[1] * 100
        pca_chart = px.scatter(
            pca_data, x='PC1', y='PC2', color='cluster_label',
            color_discrete_map=CLUSTER_COLOR_MAP,
            category_orders={'cluster_label': CLUSTER_ORDER},
            hover_name='municipality_name',
            hover_data={'PC1': ':.2f', 'PC2': ':.2f', 'cluster_label': False},
            height=480,
            title=f'Comuni nello spazio PCA (PC1 {pc1:.1f}% · PC2 {pc2:.1f}% della varianza)',
            labels={
                'PC1': f'PC1 ({pc1:.1f}% varianza)', 'PC2': f'PC2 ({pc2:.1f}% varianza)',
                'cluster_label': 'Cluster',
            },
        )
        pca_chart.update_traces(marker={'size': 7, 'opacity': 0.8})
        st.plotly_chart(apply_chart_theme(pca_chart), width='stretch')
        st.caption(
            f'Le tre feature, standardizzate con lo stesso `StandardScaler` della Pipeline '
            f'salvata, sono proiettate su due componenti principali '
            f'(`PCA(n_components=2)`): insieme spiegano il {pc1 + pc2:.1f}% della varianza. '
            'La PCA serve solo a visualizzare i cluster in 2D; il K-Means lavora sulle '
            'tre feature originali scalate. Una PC1 così dominante conferma che le feature '
            'sono fortemente correlate e descrivono lo stesso gradiente termico.'
        )

    st.caption(
        f"Artefatto creato il {metadata['created_at_utc']}; random seed "
        f"{metadata['random_seed']}. Riaddestramento: "
        '`python -m src.machine_learning.train_climate_model`.'
    )


# ---------------------------------------------------------------------------
# Tab 2 — Regressione
# ---------------------------------------------------------------------------


def _fmt(mean: float, std: float, digits: int = 3) -> str:
    return f'{mean:.{digits}f} ± {std:.{digits}f}'


def render_regression() -> None:
    try:
        meta = get_temperature_regression_metadata()
    except (FileNotFoundError, OSError, ValueError) as exc:
        st.warning(
            'Artefatti del regressore della temperatura non disponibili '
            f'(`models/temperature_regressor_metadata.json`): {exc}'
        )
        st.info(f'Per generarli eseguire: `{TRAIN_REG_CMD}` (circa 6,5 minuti, senza database).')
        return

    best_model = meta['model_name']
    best_set = meta['feature_set']
    selected = meta['selected_metrics']

    m1, m2, m3, m4 = st.columns(4)
    m1.metric('Modello scelto', MODEL_LABELS.get(best_model, best_model))
    m2.metric('RMSE (GroupKFold)', f"{selected['rmse_mean']:.3f} °C")
    m3.metric('R² (GroupKFold)', f"{selected['r2_mean']:.3f}")
    m4.metric('Comuni', f"{meta['n_observations']:,}".replace(',', '.'))

    st.subheader('Domanda e impostazione')
    left, right = st.columns(2)
    with left:
        st.markdown(
            '**Domanda:** quanto le caratteristiche del territorio spiegano la '
            'temperatura media di un comune, e quale modello lo fa meglio?\n\n'
            f"- **Target:** `{meta['target']}` (temperatura media 2000–2025, Open-Meteo).\n"
            f"- **Feature (set `{best_set}`):** "
            + ', '.join(f'`{f}`' for f in meta['features'])
            + '.\n'
            '- **Variante `territorio_coordinate`:** le stesse più `lat` e `lon`.'
        )
    with right:
        st.markdown(
            '**Modelli**, tutti in `Pipeline(StandardScaler → modello)`:\n'
            '- `LinearRegression`;\n'
            '- `RandomForestRegressor` in `GridSearchCV` (griglia 2×2×2);\n'
            '- `MLPRegressor` (rete neurale 32-16, early stopping).\n\n'
            f"**Validazione:** `cross_validate` con KFold({meta['cv_folds']}) casuale e "
            'GroupKFold per provincia (ogni fold lascia fuori province intere). '
            f"Criterio di scelta: {meta['selection_criterion']}."
        )

    # --- Tabella metriche -------------------------------------------------
    st.subheader('Metriche in cross-validation')
    metrics = pd.DataFrame(meta['metrics'])
    table = pd.DataFrame({
        'Modello': metrics['model'].map(lambda m: MODEL_LABELS.get(m, m)),
        'Set di feature': metrics['feature_set'],
        'CV': metrics['cv_scheme'],
        'MAE (°C)': [_fmt(a, b) for a, b in zip(metrics['mae_mean'], metrics['mae_std'])],
        'RMSE (°C)': [_fmt(a, b) for a, b in zip(metrics['rmse_mean'], metrics['rmse_std'])],
        'R²': [_fmt(a, b) for a, b in zip(metrics['r2_mean'], metrics['r2_std'])],
    })
    is_selected = (
        (metrics['model'] == best_model)
        & (metrics['feature_set'] == best_set)
        & (metrics['cv_scheme'] == 'GroupKFold')
    )
    table.insert(0, 'Scelto', np.where(is_selected, '⭐', ''))

    def _highlight(row):
        style = 'background-color: rgba(228, 87, 46, 0.18); font-weight: 600'
        return [style if is_selected.iloc[row.name] else '' for _ in row]

    st.dataframe(table.style.apply(_highlight, axis=1), hide_index=True, width='stretch')
    st.caption(
        'Media ± deviazione standard sui fold. ⭐ = modello salvato '
        f"({MODEL_LABELS.get(best_model, best_model)}, set `{best_set}`, GroupKFold; "
        f"parametri {meta['best_params']}). {meta['validation_note']}"
    )

    # --- Importanza delle feature ----------------------------------------
    importance = pd.DataFrame(meta['feature_importance']).sort_values('importance_mean')
    importance['label'] = importance['feature'].map(lambda f: FEATURE_LABELS_REG.get(f, f))
    imp_chart = px.bar(
        importance, x='importance_mean', y='label', orientation='h',
        error_x='importance_std',
        title='Importanza delle feature (permutation importance)',
        labels={'importance_mean': 'Calo medio di R² quando la feature è mescolata', 'label': ''},
        height=360,
    )
    imp_chart.update_traces(marker_color='#e4572e')
    st.plotly_chart(apply_chart_theme(imp_chart), width='stretch')
    st.caption(
        f"{meta['importance_note']} Attenzione: è calcolata **in-sample** (sui dati di "
        'addestramento), quindi descrive cosa usa il modello, non quanto ogni feature '
        'generalizzi.'
    )

    # --- Residui fuori campione ------------------------------------------
    try:
        residuals = get_temperature_regression_residuals()
    except (FileNotFoundError, OSError) as exc:
        st.warning(
            'Residui fuori campione non disponibili '
            f'(`temperature_regression_residuals.parquet`): {exc}'
        )
        st.info(f'Per generarli eseguire: `{TRAIN_REG_CMD}`')
    else:
        st.subheader('Predizioni fuori campione (GroupKFold per provincia)')
        col_a, col_b = st.columns(2)
        with col_a:
            lo = float(min(residuals['osservato'].min(), residuals['predetto'].min())) - 0.5
            hi = float(max(residuals['osservato'].max(), residuals['predetto'].max())) + 0.5
            pv_chart = px.scatter(
                residuals, x='osservato', y='predetto',
                hover_name='municipality_name',
                hover_data={'province_name': True, 'osservato': ':.2f',
                            'predetto': ':.2f', 'residuo': ':.2f'},
                title='Predetto vs osservato',
                labels={'osservato': 'Osservato (°C)', 'predetto': 'Predetto (°C)',
                        'province_name': 'Provincia', 'residuo': 'Residuo (°C)'},
                height=480,
            )
            pv_chart.update_traces(marker={'size': 6, 'opacity': 0.7, 'color': '#3498db'})
            pv_chart.add_trace(go.Scatter(
                x=[lo, hi], y=[lo, hi], mode='lines', name='y = x',
                line={'dash': 'dash', 'color': '#7f8c8d'},
            ))
            pv_chart.update_layout(xaxis_range=[lo, hi], yaxis_range=[lo, hi])
            st.plotly_chart(apply_chart_theme(pv_chart), width='stretch')
            st.caption(
                'Ogni punto è un comune predetto da un modello che non ha visto la sua '
                'provincia (`cross_val_predict` + GroupKFold). Sulla retta y = x la '
                'predizione è perfetta.'
            )
        with col_b:
            limit = float(residuals['residuo'].abs().max())
            res_map = px.scatter_map(
                residuals, lat='lat', lon='lon', color='residuo',
                color_continuous_scale='RdBu_r', range_color=[-limit, limit],
                color_continuous_midpoint=0,
                hover_name='municipality_name',
                hover_data={'lat': False, 'lon': False, 'province_name': True,
                            'osservato': ':.2f', 'predetto': ':.2f', 'residuo': ':.2f'},
                zoom=6.2, center={'lat': 45.1, 'lon': 7.9}, height=480,
                title='Mappa dei residui (osservato − predetto)',
                labels={'residuo': 'Residuo (°C)', 'province_name': 'Provincia',
                        'osservato': 'Osservato (°C)', 'predetto': 'Predetto (°C)'},
            )
            res_map.update_layout(
                map_style='carto-positron',
                coloraxis_colorbar={'title': 'Residuo °C<br>rosso: sottostima<br>blu: sovrastima'},
            )
            st.plotly_chart(apply_chart_theme(res_map), width='stretch')
            st.caption(
                'Residuo = osservato − predetto. **Rosso** (residuo > 0): il comune è più '
                'caldo di quanto previsto, il modello **sottostima**. **Blu** (residuo < 0): '
                'il comune è più fresco, il modello **sovrastima**.'
            )
        st.caption(
            f"Residui: media {residuals['residuo'].mean():.3f} °C, deviazione standard "
            f"{residuals['residuo'].std():.2f} °C, da {residuals['residuo'].min():.2f} a "
            f"{residuals['residuo'].max():.2f} °C."
        )

    # --- Interpretazione --------------------------------------------------
    st.success(
        '**Cosa ci dice**\n\n'
        '- **KFold casuale è ottimista:** lasciare fuori un\'intera provincia (GroupKFold) '
        'è più difficile, perché comuni vicini e simili non finiscono più sia in training '
        'sia in test. Per questo la scelta del modello usa GroupKFold.\n'
        '- **L\'elevazione domina:** l\'importanza per permutazione dell\'elevazione è circa '
        '2,035, tutte le altre circa 0,004; coerente con la regressione spaziale, dove '
        'l\'elevazione è l\'unico predittore stabile.\n'
        '- **Il Random Forest batte la lineare solo di poco:** la relazione è quasi '
        'lineare (gradiente termico verticale).\n'
        '- **L\'MLP non aggiunge nulla ed è instabile:** con circa 600 righe tabellari il '
        'deep learning non è giustificato (lezione 18-04).'
    )
    st.caption(f"Artefatto creato il {meta['created_at_utc']}; random seed {meta['random_seed']}. "
               f'Riaddestramento: `{TRAIN_REG_CMD}`.')


# ---------------------------------------------------------------------------
# Tab 3 — Limiti
# ---------------------------------------------------------------------------


def render_limits() -> None:
    st.subheader('Clustering (K-Means)')
    st.markdown(
        '- K-Means è esplorativo: i cluster non sono categorie climatiche ufficiali.\n'
        '- La soluzione dipende dalle feature, dalla scala e dal valore di `k`.\n'
        '- Le tre feature sono correlate e descrivono aspetti dello stesso regime termico.\n'
        '- Il risultato di k=3 è solo leggermente superiore a quello di k=2 '
        '(circa 0,002 di silhouette score).\n'
        '- La proiezione PCA è solo una visualizzazione: non è usata dal modello.'
    )
    st.subheader('Regressione della temperatura')
    st.markdown(
        '- La GridSearchCV interna del Random Forest usa KFold(3) e non GroupKFold: la '
        'scelta degli iperparametri non è validata per provincia.\n'
        '- L\'importanza per permutazione è calcolata sui dati di addestramento '
        '(in-sample).\n'
        '- L\'elevazione domina: le altre feature territoriali hanno un\'importanza '
        'di circa 0,004 ciascuna.\n'
        '- Circa 600 comuni sono pochi per una rete neurale: l\'MLP è instabile tra i fold.'
    )
    st.subheader('Validi per entrambi i modelli')
    st.markdown(
        '- I modelli descrivono il periodo osservato (2000–2025) e non producono '
        'previsioni future.\n'
        '- Open-Meteo è una rianalisi e presenta differenze rispetto alle stazioni ARPA.'
    )


with tab_cluster:
    render_clustering()
with tab_reg:
    render_regression()
with tab_limits:
    render_limits()
