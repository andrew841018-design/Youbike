CREATE TABLE weather (
    id SERIAL PRIMARY KEY,
    body BYTEA NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL default now()
);
CREATE TABLE weather_observation (
    raw_id INTEGER NOT NULL REFERENCES weather (id),
    station_id TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL CHECK(latitude >= -90 AND latitude <= 90),
    longitude DOUBLE PRECISION NOT NULL CHECK(longitude >= -180 AND longitude <= 180),
    publish_time TIMESTAMPTZ NOT NULL,
    observe_time TIMESTAMPTZ NOT NULL,
    temperature DOUBLE PRECISION,
    temperature_code TEXT,
    humidity DOUBLE PRECISION,
    humidity_code TEXT,
    wind_speed DOUBLE PRECISION,
    wind_speed_code TEXT,
    pressure DOUBLE PRECISION,
    pressure_code TEXT,
    precipitation DOUBLE PRECISION,
    precipitation_code TEXT,
    ingested_at TIMESTAMPTZ NOT NULL default now(),
    -- 一站一個觀測時間只有一列
    PRIMARY KEY(station_id, observe_time)
);