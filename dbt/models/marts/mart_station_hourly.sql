{{config(
    materialized='incremental',
    unique_key=['station_id','slot_hour'],
    incremental_strategy='delete+insert'
)}}
Select station_id,slot_hour,max_rent_bikes,min_return_bikes, max_return_bikes,avg_return_bikes,avg_rent_bikes,
       min_rent_bikes,last_ingested_at
from {{ref('int_station_hourly_availability')}}
{% if is_incremental() %}
where 
    last_ingested_at >= (select max(last_ingested_at) from {{this}})
{% endif %}