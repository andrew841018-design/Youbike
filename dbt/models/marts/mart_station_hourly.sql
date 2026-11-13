Select station_id,slot_hour,max_rent_bikes,min_return_bikes, max_return_bikes,avg_return_bikes,avg_rent_bikes,
       min_rent_bikes
from {{ref('int_station_hourly_availability')}}
