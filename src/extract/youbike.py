import requests
import psycopg
import os
from time import monotonic
from zoneinfo import ZoneInfo
from datetime import datetime as DateTime,timezone
from dotenv import load_dotenv
import uuid
from json import loads

import argparse

load_dotenv("/Users/andrew/Desktop/andrew/Data_engineer/Youbike/.env")

def check_json(row,type_,col):
    allowed_types = (int, float) if type_ is float else (type_,)
    if type(row[col]) not in allowed_types:
        raise ValueError(f"{col} must be {allowed_types}")
    if col not in row:
        raise ValueError(f"Missing column: {col}")
    if type_==int and row[col]<0:
        raise ValueError(f"{col} cannot be negative")
# isinstance(row[col],bool) 可以把row[col]=true/false抓出來，所以就可以過濾type=int,row[col]=true這種測資
    if isinstance(row[col],bool) and type_ == int:
        raise ValueError(f"{row[col]} cannot be boolean")
    if type_ == str:
        if not row[col].strip():
            raise ValueError(f"{col} cannot be empty")
def parse_station(row):
    check_json(row,str,"sno")
    check_json(row,str,"sna")
    check_json(row,str,"sarea")
    check_json(row,float,"latitude")
    check_json(row,float,"longitude")
    check_json(row,int,"Quantity")
    check_json(row,int,"available_rent_bikes")
    check_json(row,int,"available_return_bikes")
    check_json(row,str,"act")
    check_json(row,str,"srcUpdateTime")
    station_id = row["sno"]
    station_name = row["sna"]
    station_area = row["sarea"]
    latitude = row["latitude"]
    longitude = row["longitude"]
    quantity = row["Quantity"]
    available_rent_bikes = row["available_rent_bikes"]
    available_rent_bikes = row["available_rent_bikes"]
    available_return_bikes = row["available_return_bikes"]
    station_active = row["act"]
    """"deal with timezone"""
    time=row["srcUpdateTime"]
    parsed=DateTime.strptime(time,"%Y-%m-%d %H:%M:%S")
    taipei_time=parsed.replace(tzinfo=ZoneInfo("Asia/Taipei"))
    utc_time=taipei_time.astimezone(timezone.utc)
    source_update_time = utc_time
    return station_id,station_name,station_area,latitude,longitude,quantity,available_rent_bikes,available_return_bikes,station_active,source_update_time
def load_youbike(batch_id):
    database_url = os.environ["YOUBIKE_DATABASE_URL"]
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cursor:
            row  = cursor.execute("SELECT body,batch_id,fetched_start_at FROM raw_bytes WHERE batch_id = %s", (batch_id,)).fetchone()
            if row is None:
                raise ValueError(f"Batch ID {batch_id} not found")
            body,batch_id,fetch_start_at = row
            json=loads(body)
            if json==[] or json=={} or isinstance(json,list)==False:
                raise ValueError("Response is empty")
            record = cursor.execute("SELECT batch_id,station_id,station_name,station_area,latitude,longitude,quantity,available_rent_bikes,available_return_bikes,station_active,source_update_time FROM response WHERE fetched_start_at = %s", (fetch_start_at,)).fetchall()
            existing = {row[1]: row for row in record} # {"station_id":(batch_id,station_id,station_name....)}
        for row in json:
            if not isinstance(row,dict):
                raise ValueError("Response is not a dictionary/json")#json is api format=dict in python
            parsed = parse_station(row)
            if row["sno"] in existing:
                db_row = existing[row["sno"]]  # DB 查回的整列，第一項是 batch_id
                db_values = db_row[1:]  # 去掉 batch_id，剩下的十欄與 parsed 順序相同
                if db_values != parsed:
                    raise ValueError("DB and parsed data not match")
                if db_row[0] != batch_id:
                    raise ValueError("DB and raw batch_id not match")
                continue  # 內容與 batch 都相同，跳過下方 INSERT

            with conn.cursor() as cursor:
                cursor.execute(
                """
                INSERT INTO response
                (batch_id,station_id,station_name,station_area,latitude,
                longitude,quantity,available_rent_bikes,
                available_return_bikes,station_active,source_update_time,fetched_start_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (batch_id,parsed[0],parsed[1],parsed[2],parsed[3],parsed[4],parsed[5],parsed[6],parsed[7],parsed[8],parsed[9],fetch_start_at))




def extract_youbike(url="https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json",scrape_time=None):
    if scrape_time is None:
        request_time = DateTime.now(timezone.utc)
    else:
        request_time = scrape_time
    batch_id = str(uuid.uuid4())
    budget_second = 30
    size_limit = 5*1024*1024
    start_time = monotonic()
    buffer = bytearray()
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
    assert os.environ.get("YOUBIKE_DATABASE_URL")
    with psycopg.connect(os.environ["YOUBIKE_DATABASE_URL"]) as conn:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO raw_bytes (body,fetched_start_at,batch_id) VALUES (%s,%s,%s)", (body,request_time,batch_id))
    load_youbike(batch_id)
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scrape_time", type=DateTime.fromisoformat)
    args = parser.parse_args()
    extract_youbike(scrape_time=args.scrape_time)
