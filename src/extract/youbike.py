import requests
import psycopg
import os
from time import monotonic
from zoneinfo import ZoneInfo
from datetime import datetime as DateTime,timezone
from dotenv import load_dotenv
import uuid
from json import loads

load_dotenv("/Users/andrew/Desktop/andrew/Data_engineer/Youbike/.env")
def check_json(row,type,col):
    if col not in row:
        raise ValueError(f"Missing column: {col}")
    if not isinstance(row[col],type):
        raise ValueError(f"{col} must be {type}")
    if type == str:
        if not row[col].strip():
            raise ValueError(f"{col} cannot be empty")

def extract_youbike(url="https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json"):
    request_time= DateTime.now(timezone.utc)
    start_time = monotonic()
    budget_second = 30
    batch_id = str(uuid.uuid4())
    buffer = bytearray()
    size_limit = 5*1024*1024
    with requests.get(url,stream=True,timeout=(5,10)) as response:#5秒連線逾時，10秒下載逾時
        if response.status_code != 200:
            raise Exception(f"Request failed with status code: {response.status_code}")
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
            
    with psycopg.connect(os.environ["YOUBIKE_DATABASE_URL"]) as conn:
        json=loads(body)
        if json==[] or json=={} or isinstance(json,list)==False:
            raise ValueError("Response is empty")
        for row in json:
            if not isinstance(row,dict):
                raise ValueError("Response is not a dictionary/json")#json is api format=dict in python
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
            with conn.cursor() as cursor:
                cursor.execute(
                """
                INSERT INTO response
                (batch_id,station_id,station_name,station_area,latitude,
                longitude,quantity,available_rent_bikes,
                available_return_bikes,station_active,source_update_time,fetched_start_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (batch_id,station_id,station_name,station_area,
                latitude,longitude,quantity,available_rent_bikes,
                available_return_bikes,station_active,source_update_time,request_time))
