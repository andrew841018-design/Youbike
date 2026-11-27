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
    -- 數值欄：不能是官方記號（-99、-98），記號沒被轉成 NULL、被當成數字存進來時擋下
    -- 記號欄：數值和記號剛好一個有值，數值是 NULL 時一定要有記號，有數值時記號要是 NULL
    temperature DOUBLE PRECISION CHECK (temperature NOT IN (-99, -98)),
    temperature_code TEXT CHECK ((temperature IS NULL) <> (temperature_code IS NULL)),
    humidity DOUBLE PRECISION CHECK (humidity NOT IN (-99, -98)),
    humidity_code TEXT CHECK ((humidity IS NULL) <> (humidity_code IS NULL)),
    wind_speed DOUBLE PRECISION CHECK (wind_speed NOT IN (-99, -98)),
    wind_speed_code TEXT CHECK ((wind_speed IS NULL) <> (wind_speed_code IS NULL)),
    pressure DOUBLE PRECISION CHECK (pressure NOT IN (-99, -98)),
    pressure_code TEXT CHECK ((pressure IS NULL) <> (pressure_code IS NULL)),
    precipitation DOUBLE PRECISION CHECK (precipitation NOT IN (-99, -98)),
    precipitation_code TEXT CHECK ((precipitation IS NULL) <> (precipitation_code IS NULL)),
    ingested_at TIMESTAMPTZ NOT NULL default now(),
    -- 一站一個觀測時間只有一列
    PRIMARY KEY(station_id, observe_time)
);