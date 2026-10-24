"""
build_maps.py - Genera i progetti QGIS pianificati (vedi docs/pages/dashboard.md)

Esegue con l'interprete Python bundled di QGIS (PyQGIS), non con il venv
del progetto:

    "C:\\Program Files\\QGIS 3.44.12\\bin\\python-qgis-ltr.bat" qgis_projects\\build_maps.py

Genera:
    - qgis_projects/temperature_heatmap.qgz
    - qgis_projects/hotspot_analysis.qgz
    - qgis_projects/evolution_animation.qgz
    - qgis_projects/previews/*.png (render offscreen per verifica)

Nota di granularità: solo 8 comuni su 1180 hanno temperature reali (vedi
docs/pages/etl-pipeline.md). I 1180 comuni ISTAT sono mostrati come sfondo
grigio di contesto; gli 8 con dati reali sono evidenziati a colori sopra.
"""

import os
import re
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QGIS_PROJECTS_DIR = PROJECT_ROOT / 'qgis_projects'
PREVIEWS_DIR = QGIS_PROJECTS_DIR / 'previews'
PREVIEWS_DIR.mkdir(exist_ok=True)

from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsCategorizedSymbolRenderer,
    QgsDataSourceUri,
    QgsDateTimeRange,
    QgsFillSymbol,
    QgsGradientColorRamp,
    QgsGraduatedSymbolRenderer,
    QgsMapRendererParallelJob,
    QgsMapSettings,
    QgsPalLayerSettings,
    QgsProject,
    QgsReferencedRectangle,
    QgsRectangle,
    QgsRendererCategory,
    QgsRendererRange,
    QgsTemporalNavigationObject,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsVectorLayerJoinInfo,
    QgsVectorLayerSimpleLabeling,
    QgsVectorLayerTemporalProperties,
)
from qgis.PyQt.QtCore import QSize, QDateTime, QDate
from qgis.PyQt.QtGui import QColor, QFont


def load_env(env_path: Path) -> dict:
    """Parser minimale di .env (KEY=VALUE), senza dipendenze esterne."""
    values = {}
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.match(r'^([A-Z_]+)=(.*)$', line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def build_postgres_uri(db: dict, table: str, key: str, geom_col: str = 'geometry', sql: str = '',
                        srid: str = None, wkb_type=None) -> QgsDataSourceUri:
    uri = QgsDataSourceUri()
    uri.setConnection(db['DB_HOST'], db['DB_PORT'], db['DB_NAME'], db['DB_USER'], db['DB_PASSWORD'])
    uri.setDataSource('public' if not table.startswith('(') else '', table, geom_col, sql, key)
    # Per le subquery (table tra parentesi), il provider Postgres di QGIS
    # spesso non riesce a introspezionare tipo di geometria e SRID dal
    # catalogo (non essendo una tabella reale) — vanno dichiarati esplicitamente
    # o il layer risulta invalido senza un messaggio di errore chiaro.
    if srid is not None:
        uri.setSrid(srid)
    if wkb_type is not None:
        uri.setWkbType(wkb_type)
    return uri


def combined_extent(layers: list) -> QgsRectangle:
    extent = QgsRectangle()
    for layer in layers:
        if layer.isValid() and not layer.extent().isEmpty():
            extent.combineExtentWith(layer.extent())
    extent.scale(1.05)
    return extent


def set_project_view_extent(project: QgsProject, layers: list) -> None:
    """
    Imposta l'estensione di vista iniziale del progetto: senza questo,
    QGIS Desktop apre il progetto senza sapere su quale area centrare la
    mappa (nessun <mapcanvas> viene salvato da QgsProject.write() se non
    lo si imposta esplicitamente) — risultato: pagina bianca all'apertura,
    finché l'utente non fa manualmente "Zoom to Layer".
    """
    extent = combined_extent(layers)
    project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(extent, layers[0].crs()))


def render_preview(layers: list, output_path: Path, temporal_range=None, title: str = '') -> None:
    """Renderizza offscreen i layer in un PNG, per verifica visiva senza QGIS Desktop."""
    settings = QgsMapSettings()
    settings.setLayers(layers)
    settings.setBackgroundColor(QColor(255, 255, 255))
    settings.setOutputSize(QSize(1000, 800))

    settings.setExtent(combined_extent(layers))
    settings.setDestinationCrs(layers[0].crs())

    if temporal_range is not None:
        settings.setIsTemporal(True)
        settings.setTemporalRange(temporal_range)

    job = QgsMapRendererParallelJob(settings)
    job.start()
    job.waitForFinished()
    image = job.renderedImage()
    image.save(str(output_path))
    print(f"  ✓ Preview renderizzata: {output_path} ({'con filtro temporale' if temporal_range else 'statica'})")


def main():
    env = load_env(PROJECT_ROOT / '.env')
    db = {
        'DB_HOST': env.get('DB_HOST', 'localhost'),
        'DB_PORT': env.get('DB_PORT', '5432'),
        'DB_NAME': env.get('DB_NAME', 'heatwave_piemonte'),
        'DB_USER': env.get('DB_USER', 'postgres'),
        'DB_PASSWORD': env['DB_PASSWORD'],
    }

    QgsApplication.setPrefixPath(r"C:\Program Files\QGIS 3.44.12\apps\qgis-ltr", True)
    qgs = QgsApplication([], False)
    qgs.initQgis()

    try:
        build_temperature_heatmap(db)
        build_hotspot_analysis(db)
        build_evolution_animation(db)
    finally:
        qgs.exitQgis()


def load_all_municipalities_layer(db: dict) -> QgsVectorLayer:
    """Sfondo grigio: tutti i 1180 comuni piemontesi (senza dati di temperatura)."""
    uri = build_postgres_uri(db, 'municipalities', 'municipality_id')
    layer = QgsVectorLayer(uri.uri(False), 'Tutti i comuni (1180, senza dati reali)', 'postgres')
    symbol = QgsFillSymbol.createSimple({'color': '#e0e0e0', 'outline_color': '#bdbdbd', 'outline_width': '0.1'})
    layer.renderer().setSymbol(symbol)
    return layer


def load_municipalities_with_data_layer(db: dict, name: str) -> QgsVectorLayer:
    """Gli 8 comuni capoluogo con dati di temperatura reali."""
    sql = "municipality_id IN (SELECT DISTINCT municipality_id FROM temperature)"
    uri = build_postgres_uri(db, 'municipalities', 'municipality_id', sql=sql)
    return QgsVectorLayer(uri.uri(False), name, 'postgres')


def add_csv_join(layer: QgsVectorLayer, csv_path: Path, join_field: str = 'municipality_name') -> QgsVectorLayer:
    csv_uri = f"file:///{csv_path.as_posix()}?type=csv&detectTypes=yes&geomType=none"
    csv_layer = QgsVectorLayer(csv_uri, csv_path.stem, 'delimitedtext')
    QgsProject.instance().addMapLayer(csv_layer, False)

    join_info = QgsVectorLayerJoinInfo()
    join_info.setJoinLayer(csv_layer)
    join_info.setJoinFieldName(join_field)
    join_info.setTargetFieldName('name')
    join_info.setUsingMemoryCache(True)
    join_info.setPrefix('')
    layer.addJoin(join_info)
    return csv_layer


def add_labels(layer: QgsVectorLayer, field_expression: str) -> None:
    label_settings = QgsPalLayerSettings()
    label_settings.fieldName = field_expression
    label_settings.isExpression = True
    label_settings.enabled = True

    # Font esplicito: nell'ambiente di rendering offscreen usato per le
    # anteprime PNG, il font di default di QGIS non risolve sempre a un
    # font di sistema disponibile e le etichette appaiono come rettangoli
    # vuoti invece che testo.
    text_format = label_settings.format()
    font = QFont('Arial')
    font.setPointSize(9)
    text_format.setFont(font)
    text_format.setSize(9)
    label_settings.setFormat(text_format)

    layer.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
    layer.setLabelsEnabled(True)


def build_temperature_heatmap(db: dict) -> None:
    print("Costruzione temperature_heatmap.qgz ...")
    project = QgsProject.instance()
    project.clear()

    background = load_all_municipalities_layer(db)
    data_layer = load_municipalities_with_data_layer(db, 'Comuni capoluogo (temperatura media 2000-2025)')
    add_csv_join(data_layer, PROJECT_ROOT / 'output' / 'spatial_analysis.csv')

    field = '"temp_mean_avg"'
    ramp = QgsGradientColorRamp(QColor('#fee5d9'), QColor('#a50f15'))
    renderer = QgsGraduatedSymbolRenderer.createRenderer(
        data_layer, field, 5, QgsGraduatedSymbolRenderer.EqualInterval,
        QgsFillSymbol.createSimple({'outline_color': '#555555', 'outline_width': '0.3'}), ramp,
    )
    data_layer.setRenderer(renderer)
    add_labels(data_layer, "\"name\" || ' (' || round(\"temp_mean_avg\", 1) || '°C)'")

    project.addMapLayer(background)
    project.addMapLayer(data_layer)
    set_project_view_extent(project, [data_layer, background])

    output_path = QGIS_PROJECTS_DIR / 'temperature_heatmap.qgz'
    project.write(str(output_path))
    print(f"  ✓ Salvato: {output_path}")

    render_preview([data_layer, background], PREVIEWS_DIR / 'temperature_heatmap.png')


def build_hotspot_analysis(db: dict) -> None:
    print("Costruzione hotspot_analysis.qgz ...")
    project = QgsProject.instance()
    project.clear()

    background = load_all_municipalities_layer(db)
    data_layer = load_municipalities_with_data_layer(db, 'Cluster climatici (K-means, k=3)')
    add_csv_join(data_layer, PROJECT_ROOT / 'output' / 'spatial_analysis.csv')

    # 0 = più fresco, 2 = più caldo (climate_clustering() rinumera le
    # etichette K-means per temperatura media crescente) - stessa
    # convenzione blu->rosso della dashboard, non più colori arbitrari.
    cluster_colors = {'0': '#3498db', '1': '#f39c12', '2': '#e74c3c'}
    categories = []
    for value, color in cluster_colors.items():
        symbol = QgsFillSymbol.createSimple({'color': color, 'outline_color': '#555555', 'outline_width': '0.3'})
        categories.append(QgsRendererCategory(value, symbol, f'Cluster {value}'))
    renderer = QgsCategorizedSymbolRenderer('"climate_cluster"', categories)
    data_layer.setRenderer(renderer)
    add_labels(data_layer, '"name"')

    project.addMapLayer(background)
    project.addMapLayer(data_layer)
    set_project_view_extent(project, [data_layer, background])

    output_path = QGIS_PROJECTS_DIR / 'hotspot_analysis.qgz'
    project.write(str(output_path))
    print(f"  ✓ Salvato: {output_path}")

    render_preview([data_layer, background], PREVIEWS_DIR / 'hotspot_analysis.png')


def build_evolution_animation(db: dict) -> None:
    print("Costruzione evolution_animation.qgz ...")
    project = QgsProject.instance()
    project.clear()

    background = load_all_municipalities_layer(db)

    # Usa la vista Postgres `kpi_temporal_view` (creata da
    # qgis_projects/create_temporal_view.py) invece di una subquery inline:
    # QgsDataSourceUri mette sempre tra virgolette l'intero valore di
    # `table` come se fosse un unico identificatore, quindi una subquery
    # `(SELECT ...) AS alias` passata così non viene mai eseguita come SQL
    # reale — genera un layer invalido senza un messaggio d'errore chiaro
    # nelle API Python (visibile solo abilitando il log messaggi di QGIS).
    # Una vista reale in catalogo si comporta come qualunque altra tabella.
    uri = build_postgres_uri(db, 'kpi_temporal_view', 'feature_id')
    temporal_layer = QgsVectorLayer(uri.uri(False), 'Evoluzione annuale (2000-2025)', 'postgres')

    ramp = QgsGradientColorRamp(QColor('#fee5d9'), QColor('#a50f15'))
    renderer = QgsGraduatedSymbolRenderer.createRenderer(
        temporal_layer, '"temp_mean_annual"', 5, QgsGraduatedSymbolRenderer.EqualInterval,
        QgsFillSymbol.createSimple({'outline_color': '#555555', 'outline_width': '0.3'}), ramp,
    )
    temporal_layer.setRenderer(renderer)
    add_labels(temporal_layer, "\"name\" || ' (' || round(\"temp_mean_annual\", 1) || '°C)'")

    temporal_props = temporal_layer.temporalProperties()
    temporal_props.setMode(QgsVectorLayerTemporalProperties.ModeFeatureDateTimeStartAndEndFromFields)
    temporal_props.setStartField('year_start')
    temporal_props.setEndField('year_end')
    temporal_props.setIsActive(True)

    project.addMapLayer(background)
    project.addMapLayer(temporal_layer)
    set_project_view_extent(project, [temporal_layer, background])

    full_range = QgsDateTimeRange(QDateTime(QDate(2000, 1, 1)), QDateTime(QDate(2025, 12, 31)))
    project.timeSettings().setTemporalRange(full_range)

    output_path = QGIS_PROJECTS_DIR / 'evolution_animation.qgz'
    project.write(str(output_path))
    print(f"  ✓ Salvato: {output_path}")

    # Verifica che il filtro temporale funzioni davvero: due frame diversi
    # (2000 vs 2025) devono differire.
    frame_2000 = QgsDateTimeRange(QDateTime(QDate(2000, 1, 1)), QDateTime(QDate(2000, 12, 31)))
    frame_2025 = QgsDateTimeRange(QDateTime(QDate(2025, 1, 1)), QDateTime(QDate(2025, 12, 31)))
    render_preview([temporal_layer, background], PREVIEWS_DIR / 'evolution_2000.png', temporal_range=frame_2000)
    render_preview([temporal_layer, background], PREVIEWS_DIR / 'evolution_2025.png', temporal_range=frame_2025)


if __name__ == '__main__':
    main()
