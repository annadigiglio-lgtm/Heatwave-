"""
styling.py - CSS e componenti HTML condivisi per l'identità visiva "calore"
della dashboard (hero, card di navigazione, striscia "numeri chiave",
tipografia, sidebar). Palette e font vivono come token in `constants.py`
(THEME_*, FONT_*), così questo file e `charts.py` condividono la stessa
fonte di verità invece di ripetere gli hex in due posti.

Il tema chiaro/scuro nativo di Streamlit (vedi `.streamlit/config.toml`)
resta gestito da Streamlit stesso: widget nativi (bottoni, slider,
dataframe, gli st.metric delle altre pagine) seguono il toggle chiaro/scuro
dell'utente senza bisogno di CSS qui. Hero, card di navigazione e striscia
"numeri chiave" sono invece componenti nuovi: fino al 2026-07-17 avevano
un'identità scura fissa che ignorava il toggle (scelta validata su un
mockup con l'utente, sfondo poi schiarito da nero puro a grigio ardesia
su suo feedback). Con il tema chiaro nativo attivato, però, questo produceva
pannelli neri fuori posto su una pagina bianca ("cambia solo lo sfondo in
bianco ed è brutto" - feedback utente, 2026-07-18): questi componenti ora
leggono `st.context.theme.type` e scelgono la coppia di token corrispondente
da `THEME_TOKENS` in `constants.py`, così lo sfondo del pannello si fonde
con lo sfondo nativo dello stesso modo invece di restare bloccato sullo
scuro.

Limite noto (documentato da Streamlit stesso per `st.context.theme.type`):
il cambio tema dal menu Impostazioni è puramente lato client e NON forza un
rerun dello script, quindi subito dopo il click i colori di questi pannelli
restano quelli del rerun precedente finché non arriva una vera esecuzione
dello script (navigazione tra pagine, refresh, qualunque interazione con un
widget). Verificato manualmente con Playwright il 2026-07-18: dopo un
refresh la corrispondenza è sempre corretta, lo sfasamento è solo nella
finestra "ho appena cliccato Dark/Light senza ancora interagire di nuovo".
"""

import streamlit as st

from . import PROJECT_ROOT
from .constants import (
    FONT_BODY, FONT_DISPLAY, FONT_MONO,
    THEME_COLD, THEME_HOT, THEME_MID, THEME_TOKENS,
)


def _build_custom_css(tokens: dict) -> str:
    glow_a, glow_b, glow_c = tokens["glow_opacity"]
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400..700&family=Manrope:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ---------- Tipografia globale --------------------------------------------
   Solo i font cambiano: i colori restano quelli del tema nativo (chiaro o
   scuro) scelto dall'utente, per non rompere il toggle di Streamlit. */
html, body, [data-testid="stAppViewContainer"] {{
    font-family: {FONT_BODY};
}}
h1, h2, h3,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {{
    font-family: {FONT_DISPLAY} !important;
    font-weight: 600 !important;
}}

/* st.metric tronca con "..." qualunque valore più largo della colonna
   (successo con testi come "Nessun trend chiaro" o nomi di comune lunghi
   come "Verbano-Cusio-Ossola"). Qui il valore va a capo invece di sparire,
   e usa il monospace: le cifre si leggono come una misura, non come testo. */
div[data-testid="stMetricValue"] {{
    font-family: {FONT_MONO} !important;
    font-variant-numeric: tabular-nums;
    white-space: normal !important;
    overflow: visible !important;
    line-height: 1.25 !important;
    font-size: 1.35rem !important;
}}
div[data-testid="stMetricLabel"] {{
    opacity: 0.75;
}}

/* ---------- Respiro tra le sezioni: fade-in leggero al caricamento ------- */
[data-testid="stMainBlockContainer"] {{
    animation: hwFadeIn 0.45s ease both;
}}
@keyframes hwFadeIn {{
    from {{ opacity: 0; transform: translateY(6px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
@media (prefers-reduced-motion: reduce) {{
    [data-testid="stMainBlockContainer"] {{ animation: none; }}
}}

/* ---------- Sidebar: hover/attivo -----------------------------------------
   `data-testid` e `aria-current="page"` sono API stabili di Streamlit 1.58
   (verificate nel bundle installato) - non classi generate/hashate, che
   cambiano da una versione all'altra e romperebbero questo CSS. L'accento è
   una sovrapposizione translucida: funziona sia sulla sidebar chiara sia su
   quella scura del tema nativo, senza fissarne lo sfondo. */
[data-testid="stSidebarNavLink"] {{
    border-radius: 8px !important;
    transition: background 0.15s ease, transform 0.15s ease;
}}
[data-testid="stSidebarNavLink"]:hover {{
    background: rgba(52, 152, 219, 0.12) !important;
    transform: translateX(2px);
}}
[data-testid="stSidebarNavLink"][aria-current="page"] {{
    background: linear-gradient(90deg, rgba(231,76,60,0.18), rgba(243,156,18,0.06) 65%, transparent) !important;
    font-weight: 700 !important;
    box-shadow: inset 3px 0 0 0 {THEME_HOT};
}}

/* ---------- Sidebar: larghezza ridotta, titolo in cima, contatti in fondo -
   Larghezza di default di Streamlit leggermente ridotta (richiesta utente,
   2026-07-20). **Bug corretto lo stesso giorno**: la regola era su
   `[data-testid="stSidebar"]` senza condizione, quindi il `min-width:
   18rem !important` restava applicato anche a sidebar chiusa - impediva
   alla larghezza di scendere a 0 durante il collasso, e la pagina
   principale non si riespandeva più per riempire lo spazio liberato
   (segnalato dall'utente: "chiudo la navbar [ma] la pagina intera non si
   riadatta più"). Ora scoperta da `[aria-expanded="true"]`, stesso
   attributo già usato sotto per i contatti: a sidebar chiusa la regola
   non si applica più e il comportamento nativo di collasso/resize di
   Streamlit torna intatto.

   **Titolo**: tre tentativi precedenti. Un div `st.sidebar.markdown`
   finiva sotto la nav automatica (non richiesto). Un `st.logo()` con SVG
   di testo live (font-family referenziata, non tracciati) rendeva sopra
   la nav ma solo con font di sistema — le immagini SVG passate a
   `st.logo()` sono renderizzate dal browser in modalità sandboxata
   (`<img src="data:image/svg+xml;...">`), che blocca il caricamento di
   font esterni come l'`@import` di Fraunces usato nel resto della pagina
   (respinto dall'utente: "non mi piace esteticamente, deve essere simile
   al titolo della pagina home"). Un div HTML normale risolveva l'estetica
   ma tornava sotto la nav. **Soluzione finale**: l'utente ha fornito due
   SVG (`assets/logo-dark-theme.svg`, `assets/logo-light-theme.svg`) con
   il testo già convertito in tracciati vettoriali invece che in un
   elemento `<text>` - niente font da caricare, quindi funziona anche
   sandboxato, e sono già gradientati con gli stessi colori di
   `hero_title_gradient` sopra/sotto. `st.logo()` sceglie il file giusto
   in base a `st.context.theme.type` in `render_sidebar_branding()`.

   **Contatti in fondo**: un tentativo con `stSidebarContent`/
   `stSidebarUserContent` come colonne flex a piena altezza + `margin-top:
   auto` non ha funzionato (struttura interna di Streamlit non verificabile
   senza ispezionarla in un browser reale). Sostituito con `position:
   fixed`, che non dipende dalla gerarchia flex/altezza dei contenitori di
   Streamlit: ancorato al bordo inferiore della finestra, larghezza
   identica al `min-width` della sidebar sopra. Nascosto quando la sidebar
   è chiusa tramite `aria-expanded` (attributo reale di `stSidebar`,
   verificato nel bundle JS installato), per non restare "appeso" sopra il
   contenuto principale a sidebar chiusa. */
[data-testid="stSidebar"][aria-expanded="true"] {{
    min-width: 18rem !important;
}}
/* Logo un po' più in basso (staccato dal pulsante di collasso) e più
   grande del massimo nativo di `st.logo(size="large")` (32px) - richiesta
   utente, 2026-07-20. `!important` perché l'altezza è impostata da
   Streamlit stesso in base al parametro `size`. */
[data-testid="stSidebarLogo"] {{
    margin-top: 14px;
}}
[data-testid="stSidebarLogo"] img {{
    max-height: 46px !important;
    height: 46px !important;
    width: auto !important;
}}
[data-testid="stSidebar"][aria-expanded="true"] .hw-sidebar-footer {{
    position: fixed;
    left: 0;
    bottom: 0;
    width: 18rem;
    padding: 12px 1.5rem 16px;
    background: {tokens["ink"]};
    border-top: 1px solid {tokens["border"]};
    font-family: {FONT_MONO};
    font-size: 0.72rem;
    line-height: 1.6;
    color: {tokens["text_faint"]};
}}
.hw-sidebar-footer a {{
    color: {tokens["text_muted"]};
    text-decoration: none;
}}
.hw-sidebar-footer a:hover {{ color: {THEME_HOT}; }}

/* st.warning: il giallo acceso di default di Streamlit ("giallino vomito" -
   feedback utente, 2026-07-19) stona con la palette calda del resto della
   pagina. Qui lo sostituiamo con l'ambra del tema (THEME_MID), alla stessa
   opacità bassa usata per gli altri overlay adattivi chiaro/scuro; anche il
   testo passa da marrone/ocra di default a un arancione dedicato
   (`warning_text`, diverso tra chiaro/scuro per restare leggibile). */
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{
    background: rgba(243, 156, 18, 0.10) !important;
    border: 1px solid rgba(243, 156, 18, 0.30) !important;
}}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) * {{
    color: {tokens["warning_text"]} !important;
}}

/* ================== Componenti custom (adattivi chiaro/scuro) =========== */

.hw-hero {{
    position: relative;
    overflow: hidden;
    padding: 40px 32px 32px;
    margin: -1rem -1rem 1.5rem;
    border-radius: 16px;
    background: {tokens["ink"]};
    border: 1px solid {tokens["border"]};
    isolation: isolate;
    color: {tokens["text"]};
}}
.hw-hero::before {{
    content: "";
    position: absolute;
    inset: -30%;
    z-index: -1;
    background:
        radial-gradient(38% 55% at 10% 10%, rgba(52,152,219,{glow_a}), transparent 70%),
        radial-gradient(40% 55% at 55% -10%, rgba(243,156,18,{glow_b}), transparent 70%),
        radial-gradient(45% 60% at 95% 35%, rgba(231,76,60,{glow_c}), transparent 70%);
    filter: blur(40px);
    animation: hwDrift 26s ease-in-out infinite alternate;
}}
@keyframes hwDrift {{
    0%   {{ transform: translate(0,0) scale(1); }}
    100% {{ transform: translate(-2%, 3%) scale(1.06); }}
}}
@media (prefers-reduced-motion: reduce) {{
    .hw-hero::before {{ animation: none; }}
}}
.hw-eyebrow {{
    font-family: {FONT_MONO};
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: {THEME_MID};
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 14px;
}}
.hw-eyebrow .hw-rule {{ width: 28px; height: 1px; background: linear-gradient(90deg, {THEME_COLD}, {THEME_HOT}); }}
.hw-hero h1 {{
    font-family: {FONT_DISPLAY} !important;
    font-weight: 600 !important;
    font-size: clamp(2rem, 3.6vw, 2.9rem) !important;
    line-height: 1.08 !important;
    margin: 0 0 12px !important;
    text-wrap: balance;
    max-width: 18ch;
    background: {tokens["hero_title_gradient"]};
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
}}
.hw-lede {{
    max-width: 68ch;
    color: {tokens["text_muted"]};
    font-size: 1rem;
    margin: 0 0 20px;
}}
.hw-lede b {{ color: {tokens["text"]}; font-weight: 700; }}
.hw-hero-meta {{
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
    font-family: {FONT_MONO};
    font-size: 0.78rem;
    color: {tokens["text_faint"]};
}}
.hw-hero-meta b {{ color: {tokens["text_muted"]}; font-weight: 600; }}

/* Card di navigazione: il wrapper è un vero `st.container(key=...)`, che
   Streamlit espone come classe `st-key-<key>` sull'elemento (vedi
   `render_nav_card_header`) - qui la trasformiamo in card senza toccare il
   markup interno di Streamlit. Il link cliccabile resta un `st.page_link`
   nativo dentro lo stesso container, per non rompere la navigazione SPA. */
[class*="st-key-navcard-"] {{
    position: relative;
    background: {tokens["surface"]};
    border: 1px solid {tokens["border"]};
    border-radius: 14px;
    padding: 18px 18px 6px;
    overflow: hidden;
    transition: transform 0.25s cubic-bezier(.2,.8,.2,1), box-shadow 0.25s ease, border-color 0.25s ease, background 0.25s ease;
}}
[class*="st-key-navcard-"]::before {{
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    opacity: 0.9;
}}
[class*="st-key-navcard-"]:hover {{
    transform: translateY(-4px);
    border-color: {tokens["border_strong"]};
    background: {tokens["surface_raised"]};
    box-shadow: 0 16px 32px -14px rgba(0,0,0,0.55);
}}
.st-key-navcard-temporale::before {{ background: linear-gradient(90deg, {THEME_COLD}, #6dc1f0); }}
.st-key-navcard-spaziale::before  {{ background: linear-gradient(90deg, {THEME_MID}, #f7c15c); }}
.st-key-navcard-ondate::before    {{ background: linear-gradient(90deg, {THEME_HOT}, #ff8064); }}

[class*="st-key-navcard-"] .hw-card-head {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
}}
/* min/max-height espliciti: un elemento flex ha di default
   `min-height: auto`, che sul contenuto (l'emoji) può vincere sull'
   `height: 34px` se il line-box dell'emoji è più alto di 34px nel font di
   sistema dell'utente - la card si "stirava" più delle altre due,
   spingendo giù tutto il testo sotto (icona 📈, segnalato dall'utente,
   2026-07-19: non riproducibile in locale, ma coerente con questo bug
   flexbox noto). overflow:hidden rifila il glifo invece di farlo
   traboccare quando viene forzato nel riquadro. */
[class*="st-key-navcard-"] .hw-card-icon {{
    width: 34px; height: 34px;
    min-height: 34px; max-height: 34px;
    overflow: hidden;
    flex: none;
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.05rem;
    line-height: 1;
    background: {tokens["surface_raised"]};
    border: 1px solid {tokens["border"]};
}}
[class*="st-key-navcard-"] h3 {{
    font-family: {FONT_DISPLAY} !important;
    font-size: 1.12rem !important;
    font-weight: 600 !important;
    color: {tokens["text"]} !important;
    margin: 0 !important;
}}
[class*="st-key-navcard-"] p {{
    color: {tokens["text_muted"]} !important;
    font-size: 0.86rem !important;
    margin: 0 0 12px !important;
}}
[class*="st-key-navcard-"] [data-testid="stPageLink"] {{
    font-family: {FONT_BODY};
    font-weight: 600;
    transition: transform 0.2s ease;
}}
[class*="st-key-navcard-"]:hover [data-testid="stPageLink"] {{
    transform: translateX(4px);
}}

/* Striscia "numeri chiave" */
.hw-stats {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1px;
    background: {tokens["border"]};
    border: 1px solid {tokens["border"]};
    border-radius: 14px;
    overflow: hidden;
    margin-bottom: 0.25rem;
}}
@media (max-width: 760px) {{ .hw-stats {{ grid-template-columns: repeat(2,1fr); }} }}
.hw-stat {{
    background: {tokens["surface"]};
    padding: 18px 20px;
    transition: background 0.2s ease;
}}
.hw-stat:hover {{ background: {tokens["surface_raised"]}; }}
.hw-stat-label {{
    font-size: 0.7rem;
    color: {tokens["text_faint"]};
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 8px;
}}
.hw-stat-value {{
    font-family: {FONT_MONO};
    font-variant-numeric: tabular-nums;
    font-size: 1.55rem;
    font-weight: 600;
    color: {tokens["text"]};
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 6px;
}}
.hw-stat-value .hw-unit {{ font-size: 0.8rem; color: {tokens["text_muted"]}; font-weight: 500; }}
/* Unità lunghe ("Open-Meteo + ARPA", "27 anni") vanno a capo sotto il
   valore invece di stargli affiancate: in riga, senza spazio a
   sufficienza, l'affiancamento in flex le spezzava a metà parola
   (feedback utente, 2026-07-19). `flex-basis: 100%` in un flex-wrap forza
   l'a-capo a prescindere dallo spazio residuo, senza toccare le unità
   corte ("/ 1180", "eventi") che restano affiancate al valore. */
.hw-stat-value .hw-unit--wrap {{
    flex-basis: 100%;
    margin-top: 2px;
}}
.hw-stat-spark {{ margin-top: 10px; display: block; }}
.hw-stat-spark path.hw-fill {{ opacity: 0.18; }}
</style>
"""


def inject_custom_css() -> None:
    """Da richiamare una volta per pagina, subito dopo st.set_page_config().

    Sceglie i token chiaro/scuro in base a `st.context.theme.type`
    (rilevato dal tema nativo attivo, non da una preferenza salvata a
    parte) così hero/card/stats restano coerenti con qualunque modo
    l'utente abbia scelto dal menu impostazioni di Streamlit.
    """
    theme_type = st.context.theme.type if st.context.theme.type in THEME_TOKENS else "dark"
    st.markdown(_build_custom_css(THEME_TOKENS[theme_type]), unsafe_allow_html=True)


_SIDEBAR_LOGO_PATHS = {
    "dark": PROJECT_ROOT / "dashboard" / "assets" / "logo-dark-theme.svg",
    "light": PROJECT_ROOT / "dashboard" / "assets" / "logo-light-theme.svg",
}


def render_sidebar_branding() -> None:
    """Logo di brand sopra la nav della sidebar, contatti dell'autrice in fondo.

    Da richiamare una volta per pagina, subito dopo `inject_custom_css()`.
    Il logo è un `st.logo()` (unico modo per comparire sopra la nav
    automatica delle pagine) che punta a un SVG col testo già convertito in
    tracciati (non font live, vedi commento in `_build_custom_css`), scelto
    in base al tema attivo. I contatti sono ancorati al bordo inferiore
    della finestra via `position: fixed` in CSS.
    """
    theme_type = st.context.theme.type if st.context.theme.type in _SIDEBAR_LOGO_PATHS else "dark"
    st.logo(str(_SIDEBAR_LOGO_PATHS[theme_type]), size="large", icon_image="🌡️")
    with st.sidebar:
        st.markdown(
            '<div class="hw-sidebar-footer">'
            'Anna Digiglio<br>'
            '<a href="mailto:anna.digiglio97@gmail.com">anna.digiglio97@gmail.com</a>'
            '</div>',
            unsafe_allow_html=True,
        )


def render_hero(eyebrow: str, title: str, lede: str, meta: list[tuple[str, str]]) -> None:
    """Hero termico: eyebrow + titolo in Fraunces + testo + micro-metadati."""
    meta_html = "".join(f'<span>{label} <b>{value}</b></span>' for label, value in meta)
    # Nessun a-capo/indentazione nell'HTML: CommonMark tratta una riga
    # indentata di 4+ spazi (anche dentro un blocco HTML) come blocco di
    # codice letterale, non HTML - un'indentazione "leggibile" qui
    # renderizzava il markup come testo invece che come pagina (bug reale,
    # vedi docs/log.md 2026-07-17).
    st.markdown(
        f'<div class="hw-hero">'
        f'<div class="hw-eyebrow"><span class="hw-rule"></span>{eyebrow}</div>'
        f'<h1>{title}</h1>'
        f'<p class="hw-lede">{lede}</p>'
        f'<div class="hw-hero-meta">{meta_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_nav_card_header(icon: str, title: str, description: str) -> None:
    """
    Contenuto HTML di una card di navigazione (icona/titolo/descrizione).

    Va richiamato **dentro** un `st.container(key="navcard-<slug>")`, dove
    `<slug>` deve corrispondere a uno dei selettori CSS sopra
    (`temporale` / `spaziale` / `ondate`) per ottenere il bordo a gradiente
    giusto. Il link vero e proprio resta un `st.page_link` nativo, chiamato
    subito dopo (fuori da questa funzione) nello stesso container: un `<a>`
    costruito a mano qui romperebbe la navigazione SPA di Streamlit.
    """
    st.markdown(
        f'<div class="hw-card-head"><div class="hw-card-icon">{icon}</div><h3>{title}</h3></div>'
        f'<p>{description}</p>',
        unsafe_allow_html=True,
    )


def render_stats_row(stats: list[dict]) -> None:
    """
    Striscia di tile "numeri chiave" con sparkline decorativa.

    Ogni elemento di `stats` è un dict con chiavi 'label', 'value', 'unit',
    'color', 'spark' (lista di y normalizzati 0-1). Lo sparkline è
    illustrativo — comunica il tono cromatico della metrica (fresco/caldo),
    non è calcolato dalla serie storica reale.
    """
    tiles = "".join(_stat_tile_html(**s) for s in stats)
    st.markdown(f'<div class="hw-stats">{tiles}</div>', unsafe_allow_html=True)


def _stat_tile_html(label: str, value: str, unit: str, color: str, spark: list, unit_wrap: bool = False) -> str:
    width, height = 160, 22
    n = len(spark)
    xs = [round(i * width / (n - 1), 1) for i in range(n)] if n > 1 else [0.0, float(width)]
    ys = [round(height - 2 - v * (height - 6), 1) for v in spark]
    points = list(zip(xs, ys))
    line_points = " ".join(f"{x},{y}" for x, y in points)
    fill_path = f"M0,{height} L" + " ".join(f"{x},{y}" for x, y in points) + f" L{width},{height} Z"
    unit_class = "hw-unit hw-unit--wrap" if unit_wrap else "hw-unit"
    # Single-line: vedi commento in render_hero sul bug indentazione = code block.
    return (
        f'<div class="hw-stat">'
        f'<div class="hw-stat-label">{label}</div>'
        f'<div class="hw-stat-value">{value}<span class="{unit_class}">{unit}</span></div>'
        f'<svg class="hw-stat-spark" width="100%" height="{height}" viewBox="0 0 {width} {height}" preserveAspectRatio="none">'
        f'<path class="hw-fill" d="{fill_path}" fill="{color}"></path>'
        f'<polyline points="{line_points}" fill="none" stroke="{color}" stroke-width="1.5"></polyline>'
        f'</svg>'
        f'</div>'
    )
