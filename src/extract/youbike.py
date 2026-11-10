import requests
import psycopg
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

def parse_station(station):
    station_id = station.station_id
    station_name = station.station_name
    station_area = station.station_area
    latitude = station.latitude
    longitude = station.longitude
    quantity = station.quantity
    available_rent_bikes = station.available_rent_bikes
    available_return_bikes = station.available_return_bikes
    station_active = station.station_active
    """"deal with timezone"""
    source_update_time = DateTime.strptime(station.source_update_time,"%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("Asia/Taipei")).astimezone(timezone.utc)
    return station_id,station_name,station_area,latitude,longitude,quantity,available_rent_bikes,available_return_bikes,station_active,source_update_time
def load_youbike(batch_id):
    inserted_count = 0
    skipped_count = 0
    dsn = get_env_variable("YOUBIKE_DATABASE_URL")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cursor:
            raw = cursor.execute("SELECT body,batch_id,slot_time FROM raw_bytes WHERE batch_id = %s", (batch_id,)).fetchone()
            if raw is None:
                raise ValueError(f"Batch ID {batch_id} not found")
            body,batch_id,slot_time = raw
            stations = YoubikeStations.validate_python(loads(body))
            existing_rows = cursor.execute("SELECT batch_id,station_id,station_name,station_area,latitude,longitude,quantity,available_rent_bikes,available_return_bikes,station_active,source_update_time FROM response WHERE slot_time = %s", (slot_time,)).fetchall()
            existing_by_station = {db_row[1]: db_row for db_row in existing_rows} # {"station_id":(batch_id,station_id,station_name....)}
        for station in stations:
            station_detail = parse_station(station)
            if station.station_id in existing_by_station:
                db_row = existing_by_station[station.station_id]  # DB 查回的整列，第一項是 batch_id
                db_values = db_row[1:]  # 去掉 batch_id，剩下的十欄與 station_detail 順序相同
                if db_values != station_detail:
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
                available_return_bikes,station_active,source_update_time,slot_time)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (batch_id,station_detail[0],station_detail[1],station_detail[2],station_detail[3],station_detail[4],station_detail[5],station_detail[6],station_detail[7],station_detail[8],station_detail[9],slot_time))
    return inserted_count, skipped_count


def record_missing(conn, slot_time, retry_count=0):
    conn.execute("INSERT INTO run_status (run_id, source, slot_time, status, retry_count, finished_at, duration) VALUES (%s, 'youbike', %s, 'missing', %s, now(), interval '0 seconds')", (str(uuid.uuid4()), slot_time, int(retry_count)))


def extract_youbike(retry_count=0,url="https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json",slot_time="2099-01-01T00:00:00+08:00"):
    inserted_count = 0
    skipped_count = 0
    if slot_time is None:
        slot_time = DateTime.now(timezone.utc)
        ### 30 min align ###
        slot_time = slot_time.replace(
            minute=(slot_time.minute // 30) * 30, second=0, microsecond=0
        )
    else:
        if isinstance(slot_time, str):
            slot_time = DateTime.fromisoformat(slot_time.replace("Z", "+00:00"))
        if slot_time.utcoffset() is None:
            raise ValueError("slot_time must include timezone information")
        slot_time = slot_time.astimezone(timezone.utc)
    slot_id = int(slot_time.timestamp() // 60 // 30) ## unit: 30 min
    slot_key = (Source.YOUBIKE.value, slot_id)
    batch_id = str(uuid.uuid4())
    budget_second = 30
    size_limit = 5*1024*1024
    download_start = monotonic()
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
                raw_row = cursor.execute("SELECT batch_id FROM raw_bytes WHERE slot_time = %s", (slot_time,)).fetchone()
                # expired and nothing in raw_bytes
                slot_end = slot_time + timedelta(minutes=30)
                if raw_row is None and DateTime.now(timezone.utc) >= slot_end:
                    logger = logging.getLogger(__name__)
                    logger.warning("missing: no raw for slot %s (expired at %s). Exiting.", slot_time, slot_end)
                    record_missing(conn, slot_time, retry_count)
                    return
                run_id = str(uuid.uuid4())
                cursor.execute("INSERT INTO run_status (run_id, source, slot_time, status,retry_count) VALUES (%s, 'youbike', %s, 'running', %s)", (run_id, slot_time, int(retry_count)))
                if raw_row is not None:
                    inserted_count, skipped_count = load_youbike(raw_row[0])# replay
                    cursor.execute(finish_sql_cmd, ("succeeded", inserted_count, skipped_count, int(retry_count), run_id))

                    release_lock = cursor.execute("SELECT pg_advisory_unlock(%s, %s)", slot_key).fetchone()[0]
                    if release_lock == False:
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to release advisory lock for slot {slot_key}.")
                        raise RuntimeError(f"Failed to release advisory lock for slot {slot_key}")
                    return
            with requests.get(url,stream=True,timeout=(5,10)) as response:#5秒連線逾時，10秒下載逾時
                if response.status_code != 200:
                    raise requests.HTTPError(f"Request failed with status code: {response.status_code}", response=response)
                for chunk in response.iter_content(chunk_size=1024*64):
                    if len(buffer)+len(chunk)>size_limit:
                        raise ValueError("Response size limit exceeded")
                    if monotonic()-download_start>=budget_second:
                        raise TimeoutError("Time limit exceeded")
                    buffer.extend(chunk)
                body = bytes(buffer)
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO raw_bytes (body,slot_time,batch_id) VALUES (%s,%s,%s)", (body,slot_time,batch_id))
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
    parser.add_argument("--slot_time", type=DateTime.fromisoformat)
    args = parser.parse_args()
    extract_youbike(slot_time=args.slot_time)
