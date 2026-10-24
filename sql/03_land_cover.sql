-- ============================================================================
-- HEATWAVE PIEMONTE - Uso del suolo (CORINE Land Cover)
-- Aggiunta 2026-07-16 per il paper scientifico (vedi docs/pages/paper-scientifico.md)
-- ============================================================================

-- Percentuali di uso del suolo per comune, aggregate alle 5 categorie di
-- Livello 1 di CORINE Land Cover (primo carattere del codice CLC a 3 cifre):
-- 1=Artificiale, 2=Agricolo, 3=Forestale/seminaturale, 4=Zone umide, 5=Corpi
-- idrici. Tabella satellite 1:1 con municipalities, non colonne aggiuntive
-- lì, per non appesantire la tabella principale con piu' colonne derivate.
CREATE TABLE IF NOT EXISTS municipality_land_cover (
    municipality_id INTEGER PRIMARY KEY REFERENCES municipalities(municipality_id) ON DELETE CASCADE,
    pct_urban NUMERIC(5, 2) NOT NULL,
    pct_agricultural NUMERIC(5, 2) NOT NULL,
    pct_forest_seminatural NUMERIC(5, 2) NOT NULL,
    pct_wetland NUMERIC(5, 2) NOT NULL,
    pct_water NUMERIC(5, 2) NOT NULL,
    pct_other NUMERIC(5, 2) NOT NULL DEFAULT 0,
    dominant_class VARCHAR(30) NOT NULL,
    source_year SMALLINT NOT NULL DEFAULT 2018,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_land_cover_dominant ON municipality_land_cover(dominant_class);

-- ============================================================================
-- Aggiunta 2026-07-16 (stessa sessione): scomposizione di pct_urban in
-- sotto-classi. Motivazione: l'idea originale del paper era correlare le
-- zone piu' calde a città/industria/riscaldamento - un unico "pct_urban"
-- confonde residenziale, industriale, trasporti e verde urbano, che hanno
-- proprieta' termiche molto diverse. Le 4 sotto-classi sommano a pct_urban
-- (a meno di arrotondamento).
-- ============================================================================
ALTER TABLE municipality_land_cover ADD COLUMN IF NOT EXISTS pct_residential NUMERIC(5, 2) NOT NULL DEFAULT 0;
ALTER TABLE municipality_land_cover ADD COLUMN IF NOT EXISTS pct_industrial_commercial NUMERIC(5, 2) NOT NULL DEFAULT 0;
ALTER TABLE municipality_land_cover ADD COLUMN IF NOT EXISTS pct_transport NUMERIC(5, 2) NOT NULL DEFAULT 0;
ALTER TABLE municipality_land_cover ADD COLUMN IF NOT EXISTS pct_urban_green NUMERIC(5, 2) NOT NULL DEFAULT 0;
ALTER TABLE municipality_land_cover ADD COLUMN IF NOT EXISTS pct_extraction_construction NUMERIC(5, 2) NOT NULL DEFAULT 0;
