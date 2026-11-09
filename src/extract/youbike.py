import requests
import psycopg
import os
from time import monotonic
from zoneinfo import ZoneInfo
from datetime import datetime as DateTime,timezone,timedelta
from src.source_id import Source
from config import get_env_variable
from src.extract.youbike_model import YoubikeStations
import logging
import uuid
from json import loads
import argparse

load_count=[]
def parse_station(station):
    station_id = station.sno
    station_name = station.sna
    station_area = station.sarea
    latitude = station.latitude
    longitude = station.longitude
    quantity = station.Quantity
    available_rent_bikes = station.available_rent_bikes
    available_return_bikes = station.available_return_bikes
    station_active = station.act
    """"deal with timezone"""
    time=station.srcUpdateTime
    parsed=DateTime.strptime(time,"%Y-%m-%d %H:%M:%S")
    taipei_time=parsed.replace(tzinfo=ZoneInfo("Asia/Taipei"))
    utc_time=taipei_time.astimezone(timezone.utc)
    source_update_time = utc_time
    return station_id,station_name,station_area,latitude,longitude,quantity,available_rent_bikes,available_return_bikes,station_active,source_update_time
def load_youbike(batch_id):
    inserted_count = 0
    skipped_count = 0
    database_url = get_env_variable("YOUBIKE_DATABASE_URL")
    global load_count
    load_count.append(batch_id)
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cursor:
            row  = cursor.execute("SELECT body,batch_id,fetched_start_at FROM raw_bytes WHERE batch_id = %s", (batch_id,)).fetchone()
            if row is None:
                raise ValueError(f"Batch ID {batch_id} not found")
            body,batch_id,fetch_start_at = row
            stations = YoubikeStations.validate_python(loads(body))
            record = cursor.execute("SELECT batch_id,station_id,station_name,station_area,latitude,longitude,quantity,available_rent_bikes,available_return_bikes,station_active,source_update_time FROM response WHERE fetched_start_at = %s", (fetch_start_at,)).fetchall()
            existing = {row[1]: row for row in record} # {"station_id":(batch_id,station_id,station_name....)}
        for station in stations:
            parsed = parse_station(station)
            if station.sno in existing:
                db_row = existing[station.sno]  # DB 查回的整列，第一項是 batch_id
                db_values = db_row[1:]  # 去掉 batch_id，剩下的十欄與 parsed 順序相同
                if db_values != parsed:
                    raise ValueError("DB and parsed data not match")
                if db_row[0] != batch_id:
                    raise ValueError("DB and raw batch_id not match")
                skipped_count += 1
                continue  # 內容與 batch 都相同，跳過下方 INSERT
            inserted_count += 1

            with conn.cursor() as cursor:
                cursor.execute(
                """
                INSERT INTO response
                (batch_id,station_id,station_name,station_area,latitude,
                longitude,quantity,available_rent_bikes,
                available_return_bikes,station_active,source_update_time,fetched_start_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (batch_id,parsed[0],parsed[1],parsed[2],parsed[3],parsed[4],parsed[5],parsed[6],parsed[7],parsed[8],parsed[9],fetch_start_at))
    return inserted_count, skipped_count


def extract_youbike(retry_count=0,url="https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json",scrape_time="2099-01-01T00:00:00+08:00"):
    inserted_count = 0
    skipped_count = 0
    if scrape_time is None:
        request_time = DateTime.now(timezone.utc)
        ### 30 min align ###
        request_time = request_time.replace(
            minute=(request_time.minute // 30) * 30, second=0, microsecond=0
        )
    else:
        if isinstance(scrape_time, str):
            scrape_time = DateTime.fromisoformat(scrape_time.replace("Z", "+00:00"))
        if scrape_time.utcoffset() is None:
            raise ValueError("scrape_time must include timezone information")
        request_time = scrape_time.astimezone(timezone.utc)
    ## normalize reuquest time
    event_time = DateTime(
    request_time.year, request_time.month, request_time.day, request_time.hour, request_time.minute,
    tzinfo=timezone.utc
    )
    seconds = event_time.timestamp()
    half_hour_slot_id = int(seconds // 60 // 30) ## unit: 30 min
    slot_key = (Source.YOUBIKE.value, half_hour_slot_id)
    batch_id = str(uuid.uuid4())
    budget_second = 30
    size_limit = 5*1024*1024
    start_time = monotonic()
    buffer = bytearray()
    finish_sql_cmd = "UPDATE run_status SET status = %s, finished_at = now(), duration = now() - started_at,inserted_count = %s, skipped_count = %s, retry_count = %s WHERE run_id = %s"
    fail_sql_cmd = "UPDATE run_status SET status = %s, finished_at = now(), duration = now() - started_at, error_code = %s, inserted_count = %s, skipped_count = %s, retry_count = %s WHERE run_id = %s"
    with psycopg.connect(get_env_variable("YOUBIKE_DATABASE_URL"), autocommit=True) as conn:
        run_id = None
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s, %s)", slot_key)
                if cursor.fetchone()[0] == False:
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Another process is already running for slot {slot_key}. Exiting.")
                    return
                run_id = str(uuid.uuid4())
                cursor.execute("INSERT INTO run_status (run_id, source, scheduled_at, status,retry_count) VALUES (%s, 'youbike', %s, 'running', %s)", (run_id, request_time, int(retry_count)))
                raw_row = cursor.execute("SELECT batch_id FROM raw_bytes WHERE fetched_start_at = %s", (request_time,)).fetchone()
                if raw_row is not None:
                    inserted_count, skipped_count = load_youbike(raw_row[0])# replay
                    cursor.execute(finish_sql_cmd, ("succeeded", inserted_count, skipped_count, int(retry_count), run_id))

                    release_lock = cursor.execute("SELECT pg_advisory_unlock(%s, %s)", slot_key).fetchone()[0]
                    if release_lock == False:
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to release advisory lock for slot {slot_key}.")
                        raise RuntimeError(f"Failed to release advisory lock for slot {slot_key}")
                    return
                # expired and nothing in raw_bytes
                expire_at = request_time + timedelta(minutes=30)
                if DateTime.now(timezone.utc) >= expire_at:
                    logger = logging.getLogger(__name__)
                    logger.warning("missing: no raw for slot %s (expired at %s). Exiting.", request_time, expire_at)
                    cursor.execute(finish_sql_cmd, ("missing", inserted_count, skipped_count, int(retry_count), run_id))
                    return
            with requests.get(url,stream=True,timeout=(5,10)) as response:#5秒連線逾時，10秒下載逾時
                if response.status_code != 200:
                    raise requests.HTTPError(f"Request failed with status code: {response.status_code}", response=response)
                for chunk in response.iter_content(chunk_size=1024*64):
                    if len(buffer)+len(chunk)>size_limit:
                        raise ValueError("Response size limit exceeded")
                    if monotonic()-start_time>=budget_second:
                        raise TimeoutError("Time limit exceeded")
                    buffer.extend(chunk)
                body = bytes(buffer)
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO raw_bytes (body,fetched_start_at,batch_id) VALUES (%s,%s,%s)", (body,request_time,batch_id))
                inserted_count, skipped_count = load_youbike(batch_id)
                cursor.execute(finish_sql_cmd, ("succeeded", inserted_count, skipped_count, int(retry_count), run_id))
                release_lock = cursor.execute("SELECT pg_advisory_unlock(%s, %s)", slot_key).fetchone()[0]
                if release_lock == False:
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to release advisory lock for slot {slot_key}.")
                    raise RuntimeError(f"Failed to release advisory lock for slot {slot_key}")
        except Exception as error:
            if run_id is not None:
                conn.execute(fail_sql_cmd, ("failed", str(error), inserted_count, skipped_count, int(retry_count), run_id))
            raise error
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scrape_time", type=DateTime.fromisoformat)
    args = parser.parse_args()
    extract_youbike(scrape_time=args.scrape_time)
