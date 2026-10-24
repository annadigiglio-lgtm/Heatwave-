"""
constants.py - Palette colori e costanti condivise tra le pagine.

Centralizza le scelte visive per mantenerle coerenti in tutta la dashboard
(stessa colormap per lo stesso tipo di dato in ogni pagina/mappa), invece di
sceglierle indipendentemente pagina per pagina.
"""

# Comuni capoluogo di provincia (nome del comune, non della provincia:
# "Verbano-Cusio-Ossola" ha come capoluogo "Verbania" - vedi
# docs/pages/etl-pipeline.md).
CAPOLUOGHI = {
    "Alessandria", "Asti", "Biella", "Cuneo",
    "Novara", "Torino", "Verbania", "Vercelli",
}

# Fasce altitudinali (metri s.l.m.), soglie semplificate per uso divulgativo
# (la classificazione ISTAT ufficiale di "zona altimetrica" è per comune
# intero ed è più complessa; qui è una semplificazione a 3 fasce comunemente
# usata in divulgazione, basata sull'elevazione del centroide del comune).
ELEVATION_BANDS = [
    (0, 300, "Pianura"),
    (300, 700, "Collina"),
    (700, float("inf"), "Montagna"),
]


def elevation_band(elevation_m: float) -> str:
    """Assegna una fascia altitudinale a un valore di elevazione in metri."""
    for lower, upper, label in ELEVATION_BANDS:
        if lower <= elevation_m < upper:
            return label
    return "Montagna"


# Etichette leggibili per l'output grezzo di pymannkendall
# (`mann_kendall_trend()` in `src/analysis/trend_analysis.py` restituisce
# testualmente 'increasing'/'decreasing'/'no trend'), pensate per chi non
# conosce il test: "nessun trend chiaro" invece di "no trend" chiarisce che
# è un limite del test (26 anni non bastano per essere sicuri), non
# un'affermazione che il clima sia stabile.
MK_TREND_LABELS = {
    "increasing": "📈 In aumento",
    "decreasing": "📉 In diminuzione",
    "no trend": "🔍 Nessun trend chiaro",
}


def format_mk_trend(mk_trend: str) -> str:
    """Traduce l'esito grezzo di Mann-Kendall in un'etichetta leggibile."""
    return MK_TREND_LABELS.get(mk_trend, mk_trend)


# Stagioni meteorologiche standard (non astronomiche): DJF/MAM/JJA/SON.
SEASON_BY_MONTH = {
    12: "Inverno", 1: "Inverno", 2: "Inverno",
    3: "Primavera", 4: "Primavera", 5: "Primavera",
    6: "Estate", 7: "Estate", 8: "Estate",
    9: "Autunno", 10: "Autunno", 11: "Autunno",
}
SEASON_ORDER = ["Inverno", "Primavera", "Estate", "Autunno"]
SEASON_COLORS = {
    "Inverno": "#3498db",
    "Primavera": "#2ecc71",
    "Estate": "#e74c3c",
    "Autunno": "#f39c12",
}

# Colormap sequenziale per valori assoluti di temperatura (blu freddo -> rosso
# caldo), usata in tutte le mappe/grafici che mostrano un valore di
# temperatura assoluto.
TEMPERATURE_COLORSCALE = "RdYlBu_r"

# Colormap divergente per valori di *variazione* (trend, anomalie): centrata
# sullo zero, blu = raffreddamento/sotto media, rosso = riscaldamento/sopra
# media. Non va confusa con la colorscale sequenziale sopra: qui lo zero ha
# un significato preciso (nessun cambiamento) che va sempre al centro.
TREND_COLORSCALE = "RdBu_r"

# Cluster climatici: `climate_clustering()` in
# `src/analysis/spatial_analysis.py` rinumera le etichette grezze di K-means
# per temperatura media crescente (0 = più fresco ... k-1 = più caldo), non
# più un ordine arbitrario di sklearn - i colori qui seguono la stessa
# convenzione blu→rosso della colormap di temperatura, invece di colori
# categorici senza relazione con "quanto è caldo" il gruppo.
CLUSTER_COLORS = {0: "#3498db", 1: "#f39c12", 2: "#e74c3c"}

# Colore neutro di base per elementi non critici; il rosso "caldo" è
# riservato a evidenziare anomalie/eventi/valori sopra soglia, per non
# perdere forza comunicativa usandolo ovunque.
NEUTRAL_COLOR = "#3498db"
ALERT_COLOR = "#e74c3c"

# --- Design tokens per l'identità visiva "calore" della dashboard ---------
# Riusano la stessa palette freddo→caldo già impiegata nei grafici sopra
# (NEUTRAL_COLOR, ALERT_COLOR) invece di introdurne una nuova: l'interfaccia
# eredita il linguaggio cromatico dei dati, non il contrario. Usati da
# `styling.py` (CSS di hero/card/sidebar) e `charts.py` (tema Plotly).
THEME_COLD = NEUTRAL_COLOR
THEME_MID = "#f39c12"
THEME_HOT = ALERT_COLOR
THEME_HOT_DEEP = "#c0392b"

# Grigio ardesia (non nero puro): scelta dopo un giro di feedback sul mockup
# della Home ("sfondo troppo nero"), vedi docs/log.md 2026-07-17.
# THEME_INK_SIDEBAR non è consumato da nessun modulo Python: esiste solo come
# riferimento per chi tocca `.streamlit/config.toml` (deve restare allineato a
# [theme.dark.sidebar].backgroundColor).
THEME_INK_SIDEBAR = "#161a26"

# Token mode-dipendenti per l'identità "calore" (hero, card di navigazione,
# striscia numeri chiave). Lo sfondo `ink` è pensato per FONDERSI con lo
# sfondo nativo di Streamlit dello stesso modo (vedi backgroundColor in
# .streamlit/config.toml [theme]/[theme.dark]), non per contrastarci: il
# pannello si distingue via bordo/glow/gradiente del titolo, non via un
# blocco di colore diverso dalla pagina. Per questo ogni modo ha la sua
# variante invece di un unico set fisso — prima del 2026-07-18 il tema
# chiaro nativo di Streamlit veniva applicato ma questi pannelli restavano
# sempre scuri, risultando in un tema "chiaro" fatto solo di sfondo bianco +
# blocchi neri fuori posto (segnalato dall'utente, vedi docs/log.md
# 2026-07-18). Selezionati a runtime in `styling.py` via
# `st.context.theme.type`.
THEME_TOKENS = {
    "dark": {
        "ink": "#1c2130",
        "surface": "#262c3d",
        "surface_raised": "#2d3448",
        "border": "rgba(255,255,255,0.10)",
        "border_strong": "rgba(255,255,255,0.18)",
        "text": "#f1f3f8",
        "text_muted": "#a3adc2",
        "text_faint": "#737e97",
        # Titolo hero "che si accende" sullo sfondo quasi nero: da bianco a
        # crema/corallo caldo.
        "hero_title_gradient": "linear-gradient(100deg, #fff 30%, #ffe9c7 55%, #ffb199 78%)",
        "glow_opacity": (0.30, 0.20, 0.26),
        # Testo del box st.warning: arancione caldo leggibile sullo sfondo
        # scuro, al posto del marrone/ocra di default di Streamlit (feedback
        # utente, 2026-07-19: "il marrone non mi piace, prova con un
        # arancione").
        "warning_text": "#ffb454",
    },
    "light": {
        "ink": "#ffffff",
        "surface": "#f8fafc",
        "surface_raised": "#eef2f7",
        "border": "rgba(15,23,42,0.10)",
        "border_strong": "rgba(15,23,42,0.18)",
        "text": "#1a202c",
        "text_muted": "#5a6472",
        "text_faint": "#8a93a3",
        # Stesso concetto del gradiente scuro (base neutra -> accento caldo),
        # speculare: da ardesia scuro a rosso ember (THEME_HOT_DEEP), invece
        # di bianco-su-nero che sul bianco sarebbe illeggibile.
        "hero_title_gradient": "linear-gradient(100deg, #1a202c 25%, #c2703d 55%, #c0392b 80%)",
        # Sfumature radiali più tenui: sullo sfondo bianco la stessa opacità
        # del tema scuro risulterebbe "sporca" invece che un bagliore sottile.
        "glow_opacity": (0.16, 0.12, 0.14),
        # Vedi commento nel tema "dark": stesso concetto, tono più scuro per
        # restare leggibile sullo sfondo ambra chiaro invece che su uno scuro.
        "warning_text": "#b45a0c",
    },
}

FONT_DISPLAY = "'Fraunces', 'Iowan Old Style', 'Palatino Linotype', Georgia, serif"
FONT_BODY = "'Manrope', -apple-system, 'Segoe UI', system-ui, sans-serif"
FONT_MONO = "'JetBrains Mono', ui-monospace, 'Cascadia Code', 'SFMono-Regular', monospace"

# Tornata a "CartoDB positron" (2026-07-17): il tentativo con
# "CartoDB dark_matter" è stato respinto dall'utente ("mappe brutte, scure,
# troppi casini") — le etichette/strade del tile scuro competono con i
# poligoni colorati sovrapposti, mai validato su un mockup reale (nel
# mockup approvato la mappa era un'illustrazione SVG statica, non un vero
# tile Folium). Non riprovare senza rivalidare la scelta con l'utente.
MAP_TILES = "CartoDB positron"

# Uso del suolo (CORINE Land Cover, vedi municipality_land_cover e
# docs/pages/data-sources.md): colori vicini alla palette ufficiale CLC per
# ciascuna categoria di Livello 1 (presa da data/external/clc_legend.csv,
# colore della classe più rappresentativa di ciascun gruppo), non una
# palette inventata - così una mappa di uso del suolo qui si legge in modo
# coerente con qualunque altra mappa CORINE si sia già visto altrove.
LAND_COVER_COLORS = {
    "urban": "#e6004d",
    "agricultural": "#ffffa8",
    "forest_seminatural": "#80ff00",
    "wetland": "#a6a6ff",
    "water": "#00cced",
    "other": "#cccccc",
}
LAND_COVER_LABELS = {
    "urban": "Urbano/artificiale",
    "agricultural": "Agricolo",
    "forest_seminatural": "Forestale/seminaturale",
    "wetland": "Zone umide",
    "water": "Corpi idrici",
    "other": "Altro/non classificato",
}

# NDVI (verde da satellite, Copernicus Global Land Service - vedi
# municipality_ndvi e docs/pages/data-sources.md): gradiente marrone/sabbia
# -> verde, convenzione standard per la visualizzazione NDVI (basso =
# suolo nudo/vegetazione rada, alto = vegetazione densa) - diversa
# deliberatamente dalla scala blu->rosso di temperatura/trend, per non
# far sembrare l'NDVI un'altra mappa di temperatura a prima vista.
NDVI_COLORS = ["#a6611a", "#f5deb3", "#1a9850"]
VEGETATION_CLASS_LABELS = {
    "no_vegetation": "Nessuna vegetazione",
    "sparse": "Vegetazione rada",
    "moderate": "Vegetazione moderata",
    "dense": "Vegetazione densa",
    "very_dense": "Vegetazione molto densa",
}

# Valori di riferimento pubblicati in letteratura scientifica, usati solo
# come contesto di confronto ("il nostro trend locale è più o meno ripido
# della media?"). NON sono calcolati da questo progetto e non vengono
# scaricati in tempo reale da nessuna API - sono ordini di grandezza citati
# comunemente da IPCC AR6 (2021, riscaldamento medio globale delle terre
# emerse) e dai rapporti annuali ISPRA "Gli indicatori del clima in Italia"
# (riscaldamento medio italiano, tipicamente più rapido della media globale).
NATIONAL_GLOBAL_REFERENCE = {
    "Riscaldamento medio globale (terre emerse)": 0.20,
    "Riscaldamento medio Italia (ISPRA)": 0.40,
}
