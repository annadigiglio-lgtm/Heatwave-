"""
data_source.py - Selettore fonte dati (Open-Meteo / ARPA / confronto),
riusabile tra le pagine che supportano entrambe le fonti.

Contesto: la copertura ARPA (218 comuni, completata il 2026-07-23, vedi
docs/pages/data-sources.md) e quella Open-Meteo (599 comuni dal 2026-07-23)
si sovrappongono quasi per intero - tutti i 218 comuni ARPA hanno anche
Open-Meteo, 381 hanno solo Open-Meteo.
Questo componente adatta le opzioni mostrate a quali fonti sono davvero
disponibili per il comune/insieme di comuni selezionato, invece di lasciare
scegliere un'opzione che poi risulterebbe vuota.
"""

import streamlit as st

SOURCE_OPENMETEO = 'openmeteo'
SOURCE_ARPA = 'arpa'
SOURCE_BOTH = 'both'

_LABELS = {
    SOURCE_BOTH: 'Open-Meteo + ARPA',
    SOURCE_OPENMETEO: 'Open-Meteo',
    SOURCE_ARPA: 'ARPA',
}


def render_source_selector(key: str, has_om: bool, has_arpa: bool, horizontal: bool = True) -> str:
    """
    Radio Open-Meteo + ARPA / Open-Meteo / ARPA, con le opzioni ridotte a
    quelle disponibili davvero (`has_om`/`has_arpa` riferite al comune o
    all'insieme di comuni correntemente selezionato). Default su "Open-Meteo
    + ARPA" (la vista combinata, coerente con la Home) invece della singola
    fonte Open-Meteo.

    Se solo una fonte è disponibile, non mostra un radio con opzioni
    disabilitate ma un'informazione testuale e restituisce direttamente
    l'unica fonte valida - il chiamante non deve mai gestire il caso "fonte
    scelta ma assente".
    """
    if has_om and has_arpa:
        options = [SOURCE_BOTH, SOURCE_OPENMETEO, SOURCE_ARPA]
        choice = st.radio(
            "Fonte dati",
            options,
            index=0,
            format_func=lambda s: _LABELS[s],
            key=key,
            horizontal=horizontal,
        )
        return choice
    if has_om:
        st.caption("ℹ️ Nessuna stazione ARPA attiva per questa selezione — disponibile solo Open-Meteo.")
        return SOURCE_OPENMETEO
    if has_arpa:
        st.caption("ℹ️ Nessun dato Open-Meteo per questa selezione — disponibile solo ARPA (stazione reale).")
        return SOURCE_ARPA
    return SOURCE_OPENMETEO
