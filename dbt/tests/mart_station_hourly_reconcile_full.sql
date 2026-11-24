{{config(tags=['monthly'])}}
with mart_station_hourly as (
    select *
    from {{ref('mart_station_hourly')}}
),
stg_youbike_snapshot as (
    select *
    from {{ref('int_station_hourly_availability')}}
)
-- if return 0 means pass
(select *
from mart_station_hourly m
except
select *
from stg_youbike_snapshot s
)
union all
(
select *
from stg_youbike_snapshot s
except
select *
from mart_station_hourly m
)
