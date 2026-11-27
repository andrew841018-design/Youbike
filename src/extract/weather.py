import requests
import psycopg
from time import monotonic
from config import get_env_variable
from src.extract.weather_model import Weather_Response
    
def extract_weather(url="https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0001-001.json"):
    size_limit = 10*1024*1024
    download_start = monotonic()
    budget_second = 30
    buffer = bytearray()
    with requests.get(url,stream=True,timeout=(5,30)) as response:#5秒連線逾時，30秒讀取逾時
        if response.status_code != 200:
            raise requests.HTTPError(f"Request failed with status code: {response.status_code}", response=response)
        for chunk in response.iter_content(chunk_size=1024*64):
            if len(buffer)+len(chunk)>size_limit:
                raise ValueError("Response size limit exceeded")
            if monotonic()-download_start>=budget_second:
                raise TimeoutError("Time limit exceeded")
            buffer.extend(chunk)
        body = bytes(buffer)
    return body

def store_raw(body,conn):
    row = conn.execute("insert into weather(body) values (%s) returning id",(body,)).fetchone()
    id = row[0]
    return id
def store_weather_observation(conn, raw_id):
    raw = conn.execute("select body from weather where id= %s",(raw_id,)).fetchone()
    if raw is None:
        raise ValueError(f"找不到 id={raw_id} 的 weather 原始資料")
    body = raw[0]
    r=Weather_Response.model_validate_json(body)
    with conn.transaction():
        for station in r.stations:
            conn.execute(
            """
            INSERT INTO weather_observation
            (raw_id,station_id,latitude,longitude,publish_time,observe_time,
            temperature,temperature_code,humidity,humidity_code,
            wind_speed,wind_speed_code,pressure,pressure_code,
            precipitation,precipitation_code)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (station_id,observe_time) DO UPDATE SET
            raw_id = excluded.raw_id,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            publish_time = excluded.publish_time,
            temperature = excluded.temperature,
            temperature_code = excluded.temperature_code,
            humidity = excluded.humidity,
            humidity_code = excluded.humidity_code,
            wind_speed = excluded.wind_speed,
            wind_speed_code = excluded.wind_speed_code,
            pressure = excluded.pressure,
            pressure_code = excluded.pressure_code,
            precipitation = excluded.precipitation,
            precipitation_code = excluded.precipitation_code,
            ingested_at = now()
            WHERE excluded.publish_time > weather_observation.publish_time
            """, (raw_id,station.station_id,station.Latitude,station.Longitude,r.published_at,station.observe_time,
                  station.Temperature,station.Temperature_code,station.Humidity,station.Humidity_code,
                  station.WindSpeed,station.WindSpeed_code,station.Pressure,station.Pressure_code,
                  station.Precipitation,station.Precipitation_code))

        
if __name__ == "__main__":
    dsn = get_env_variable("YOUBIKE_TEST_DATABASE_URL")
    body = extract_weather()
    with psycopg.connect(dsn,autocommit = True) as conn:
        id = store_raw(body,conn)
        store_weather_observation(conn,id)
