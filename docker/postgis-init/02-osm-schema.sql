-- Pre-create the OSM schema used by the dashboard's PostGIS Summary
-- panel. Without these tables present, the panel's SELECT against
-- `osm_import_log` fails with "relation does not exist" and the panel
-- renders the misleading "could not connect to the database" banner.
--
-- The fwh_osm runner's import handler also creates these tables
-- (CREATE TABLE IF NOT EXISTS) the first time it runs, so this init
-- file just makes the empty-state work — an empty regions list is
-- the correct "no imports yet" rendering.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS osm_import_log (
    id              SERIAL PRIMARY KEY,
    region          TEXT,
    node_count      BIGINT,
    way_count       BIGINT,
    imported_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS osm_nodes (
    osm_id          BIGINT PRIMARY KEY,
    region          TEXT,
    tags            JSONB,
    geom            GEOMETRY(Point, 4326)
);

CREATE TABLE IF NOT EXISTS osm_ways (
    osm_id          BIGINT PRIMARY KEY,
    region          TEXT,
    tags            JSONB,
    geom            GEOMETRY(LineString, 4326)
);

CREATE INDEX IF NOT EXISTS idx_osm_nodes_geom ON osm_nodes USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_osm_nodes_tags ON osm_nodes USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_osm_nodes_region ON osm_nodes (region);
CREATE INDEX IF NOT EXISTS idx_osm_ways_geom  ON osm_ways  USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_osm_ways_tags  ON osm_ways  USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_osm_ways_region ON osm_ways (region);
