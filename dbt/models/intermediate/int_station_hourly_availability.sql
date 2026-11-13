Select station_id, date_trunc('hour', slot_time, 'UTC') as slot_hour,
       min(available_rent_bikes) as min_rent_bikes, max(available_rent_bikes) as max_rent_bikes,
       avg(available_rent_bikes)::float as avg_rent_bikes, min(available_return_bikes) as min_return_bikes, max(available_return_bikes) as max_return_bikes,
       avg(available_return_bikes)::float as avg_return_bikes
from {{ref('stg_youbike_snapshot')}}
group by station_id, date_trunc('hour', slot_time, 'UTC')
