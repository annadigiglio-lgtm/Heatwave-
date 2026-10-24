-- ============================================================================
-- HEATWAVE PIEMONTE - NDVI (verde da satellite, Copernicus Global Land Service)
-- Aggiunta 2026-07-17 per il paper scientifico (vedi docs/pages/paper-scientifico.md)
-- ============================================================================

-- NDVI (Normalized Difference Vegetation Index) medio per comune, da un
-- composito 10-giornaliero Copernicus Global Land Service NDVI 300m V3
-- (raster globale, EPSG:4326, DN 0-250 -> NDVI reale via DN*0.004-0.08;
-- DN 251-255 sono flag: missing/cloud/snow/sea/background - esclusi dalla
-- zonal stats, vedi src/data_acquisition/process_ndvi.py). Copertura
-- continua, complementare alle classi discrete di
-- municipality_land_cover (CORINE) - stesso motivo per cui e' una tabella
-- satellite 1:1 con municipalities invece di colonne su quella tabella.
CREATE TABLE IF NOT EXISTS municipality_ndvi (
    municipality_id INTEGER PRIMARY KEY REFERENCES municipalities(municipality_id) ON DELETE CASCADE,
    ndvi_mean NUMERIC(5, 4) NOT NULL,
    ndvi_min NUMERIC(5, 4),
    ndvi_max NUMERIC(5, 4),
    ndvi_stddev NUMERIC(5, 4),
    pct_valid_pixels NUMERIC(5, 2) NOT NULL,  -- % pixel del comune non mascherati (cloud/snow/sea/missing)
    vegetation_class VARCHAR(20) NOT NULL,     -- bucket da ndvi_mean, vedi process_ndvi.py
    acquisition_period VARCHAR(20) NOT NULL,   -- composito 10-giornaliero, es. '2026-07-01'
    source_product VARCHAR(60) NOT NULL DEFAULT 'CGLS NDVI 300m V3',
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ndvi_vegetation_class ON municipality_ndvi(vegetation_class);
