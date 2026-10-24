-- ============================================================================
-- HEATWAVE PIEMONTE - ARPA_TEMPERATURE (osservazioni di stazione reali)
-- Aggiunta 2026-07-18 per la validazione delle stime Open-Meteo (fase 1 del
-- piano paper, vedi docs/pages/paper-scientifico.md)
-- ============================================================================

-- Temperature giornaliere osservate da stazioni ARPA Piemonte (non dati di
-- rianalisi/modello come `temperature`), usate per validare le stime
-- Open-Meteo sullo stesso (comune, data). Vedi docs/pages/data-sources.md e
-- src/data_acquisition/download_arpa.py.
CREATE TABLE IF NOT EXISTS arpa_temperature (
    arpa_temperature_id BIGSERIAL PRIMARY KEY,
    municipality_id INTEGER NOT NULL REFERENCES municipalities(municipality_id),
    station_code VARCHAR(20) NOT NULL,
    station_name VARCHAR(100),
    date DATE NOT NULL,
    temp_mean FLOAT,
    temp_max FLOAT,
    temp_min FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (station_code, date)
);

CREATE INDEX IF NOT EXISTS idx_arpa_temperature_municipality_date ON arpa_temperature(municipality_id, date);
CREATE INDEX IF NOT EXISTS idx_arpa_temperature_date ON arpa_temperature(date);
