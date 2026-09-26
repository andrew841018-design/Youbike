CREATE TABLE raw_bytes (
    id SERIAL PRIMARY KEY,
    body BYTEA NOT NULL,
    batch_id UUID UNIQUE NOT NULL,
    fetched_start_at TIMESTAMPTZ UNIQUE NOT NULL
);
CREATE TABLE response (
    id SERIAL PRIMARY KEY,
    batch_id UUID NOT NULL REFERENCES raw_bytes (batch_id),
    station_id TEXT NOT NULL,
    station_name TEXT NOT NULL,
    station_area TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    quantity INTEGER Check(quantity >= 0),
    available_rent_bikes INTEGER Check(available_rent_bikes >= 0),
    available_return_bikes INTEGER Check(available_return_bikes >= 0),
    station_active TEXT Check(station_active in ('0','1')),
    source_update_time TIMESTAMPTZ NOT NULL,
    fetched_start_at TIMESTAMPTZ NOT NULL REFERENCES raw_bytes (fetched_start_at) 
);