
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS vessels (
  mmsi INTEGER PRIMARY KEY,
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  location GEOGRAPHY(POINT, 4326) NOT NULL,
  course REAL,
  speed REAL,
  ship_type INTEGER,
  geohash VARCHAR(12),
  geohash_5 VARCHAR(5),
  last_updated TIMESTAMPTZ NOT NULL,
  received_at TIMESTAMPTZ DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS idx_vessels_location 
ON vessels USING GIST(location);

CREATE INDEX IF NOT EXISTS idx_vessels_geohash5 
ON vessels(geohash_5);

CREATE INDEX IF NOT EXISTS idx_vessels_updated 
ON vessels(last_updated);

CREATE INDEX IF NOT EXISTS idx_vessels_geohash5_updated 
ON vessels(geohash_5, last_updated);

CREATE INDEX IF NOT EXISTS idx_vessels_mmsi 
ON vessels(mmsi);

CREATE INDEX IF NOT EXISTS idx_vessels_fresh_bbox 
ON vessels(last_updated DESC, latitude, longitude);


CREATE OR REPLACE FUNCTION delete_stale_vessels()
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM vessels 
  WHERE last_updated < NOW() - INTERVAL '2 minutes';
  
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE VIEW fresh_vessels AS
SELECT 
  mmsi,
  latitude,
  longitude,
  location,
  course,
  speed,
  ship_type,
  geohash,
  geohash_5,
  last_updated,
  received_at
FROM vessels
WHERE last_updated > NOW() - INTERVAL '2 minutes';

GRANT ALL PRIVILEGES ON TABLE vessels TO ais_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ais_user;
