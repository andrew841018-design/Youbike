with start_time as (
    select max(last_ingested_at)-interval '2 days' as since
    from {{ref('int_station_hourly_availability')}}
),
mart_station_hourly as (
    select *
    from {{ref('mart_station_hourly')}}
    where last_ingested_at >= (select since from start_time)
),
stg_youbike_snapshot as (
    select *
    from {{ref('int_station_hourly_availability')}}
    where last_ingested_at >= (select since from start_time)
)
(select *
from mart_station_hourly m
except
select *
from stg_youbike_snapshot s
)
union all
(select *
from stg_youbike_snapshot s
except
select *
from mart_station_hourly m
)