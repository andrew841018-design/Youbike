CREATE TABLE raw_bytes (
    id SERIAL PRIMARY KEY,
    body BYTEA NOT NULL,
    batch_id UUID UNIQUE NOT NULL,
    fetched_start_at TIMESTAMPTZ UNIQUE NOT NULL,
    UNIQUE(batch_id, fetched_start_at)
);
CREATE TABLE response (
    id SERIAL PRIMARY KEY,
    batch_id UUID NOT NULL REFERENCES raw_bytes (batch_id),
    station_id TEXT NOT NULL CHECK(btrim(station_id) <> ''),
    foreign key (batch_id, fetched_start_at) references raw_bytes (batch_id, fetched_start_at),
    UNIQUE(station_id, batch_id),
    UNIQUE(station_id, fetched_start_at),
    station_name TEXT NOT NULL CHECK(btrim(station_name) <> ''),
    station_area TEXT NOT NULL CHECK(btrim(station_area) <> ''),
    latitude DOUBLE PRECISION NOT NULL CHECK(latitude >= -90 AND latitude <= 90),
    longitude DOUBLE PRECISION NOT NULL CHECK(longitude >= -180 AND longitude <= 180),
    quantity INTEGER Check(quantity >= 0) NOT NULL,
    available_rent_bikes INTEGER Check(available_rent_bikes >= 0) NOT NULL,
    available_return_bikes INTEGER Check(available_return_bikes >= 0) NOT NULL,
    station_active TEXT Check(station_active in ('0','1')),
    source_update_time TIMESTAMPTZ NOT NULL,
    fetched_start_at TIMESTAMPTZ NOT NULL REFERENCES raw_bytes (fetched_start_at),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
