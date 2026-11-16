CREATE TABLE farms (
  id   TEXT PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE crops (
  id   TEXT PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE soils (
  id                         TEXT PRIMARY KEY,
  name                       TEXT NOT NULL,
  available_water_mm_per_m   INTEGER NOT NULL
);

CREATE TABLE emitters (
  id       TEXT PRIMARY KEY,
  name     TEXT NOT NULL,
  flow_lph DOUBLE PRECISION NOT NULL
);

CREATE TABLE plots (
  id                 TEXT PRIMARY KEY,
  farm_id            TEXT NOT NULL REFERENCES farms(id),
  name               TEXT NOT NULL,
  area_m2            DOUBLE PRECISION NOT NULL,
  crop_id            TEXT NOT NULL REFERENCES crops(id),
  planting_date      TEXT NOT NULL,
  soil_id            TEXT NOT NULL REFERENCES soils(id),
  row_spacing_m      DOUBLE PRECISION NOT NULL,
  emitter_spacing_m  DOUBLE PRECISION NOT NULL,
  emitter_id         TEXT NOT NULL REFERENCES emitters(id),
  lat                DOUBLE PRECISION NOT NULL,
  lon                DOUBLE PRECISION NOT NULL,
  UNIQUE (farm_id, name)
);
