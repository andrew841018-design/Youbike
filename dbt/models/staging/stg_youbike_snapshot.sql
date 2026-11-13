Select station_id, slot_time, available_rent_bikes, available_return_bikes, quantity,
       station_name, station_area, latitude, longitude, batch_id, station_active, ingested_at
from {{source('youbike','response')}}
