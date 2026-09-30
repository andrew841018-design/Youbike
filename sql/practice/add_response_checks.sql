alter table raw_bytes
add constraint raw_batch_time_unique unique(batch_id,fetched_start_at);

alter table response
add constraint check_latitude check(latitude >= -90 and latitude <= 90),
add constraint check_longitude check(longitude >= -180 and longitude <= 180),
add constraint check_station_id unique(station_id,batch_id),
add constraint check_fetched_start_at unique(station_id,fetched_start_at),
add constraint check_station_id_ check(btrim(station_id) <> ''),
add constraint check_station_name check(btrim(station_name) <> ''),
add constraint check_station_area check(btrim(station_area) <> ''),
add column ingested_at timestamptz,
alter column quantity set not null,
add constraint response_raw_pair_fkey foreign key (batch_id,fetched_start_at) references raw_bytes(batch_id,fetched_start_at),
alter column available_rent_bikes set not null,
alter column available_return_bikes set not null;

alter table response
alter column ingested_at set default now(),
add constraint check_ingested_at_not_null check(ingested_at is not null) not valid;
