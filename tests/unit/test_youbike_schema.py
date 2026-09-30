from dotenv import dotenv_values
import psycopg
import uuid
import os
from datetime import datetime
import zoneinfo
from psycopg.errors import NotNullViolation,UniqueViolation,CheckViolation,ForeignKeyViolation
import pytest
@pytest.fixture
def test_env():
    test_db = os.environ.get("YOUBIKE_TEST_DATABASE_URL") or dotenv_values(".env")["YOUBIKE_TEST_DATABASE_URL"]
    with psycopg.connect(test_db) as conn:
        database=conn.execute("SELECT current_database()").fetchone()[0]
        if database != "youbike_test":
            raise RuntimeError("Database name is not youbike_test")
        try:
            yield conn
        finally:
            conn.rollback()
def test_schema(test_env):
    batch_id =str(uuid.uuid4())
    station_id = str(uuid.uuid4())
    taipei_tz=zoneinfo.ZoneInfo("Asia/Taipei")
    fetched_start_at=datetime.now(taipei_tz).astimezone(zoneinfo.ZoneInfo("UTC"))
    test_env.execute("INSERT INTO raw_bytes (batch_id,body,fetched_start_at) VALUES (%s,%s,%s)",(batch_id,b"[]",fetched_start_at))
    test_env.execute("INSERT INTO response (batch_id,quantity,station_id,station_name,station_area,latitude,longitude,available_rent_bikes,available_return_bikes,station_active,source_update_time,fetched_start_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(batch_id,5,station_id,"station_name","station_area",0.0,0.0,0,0,"0",datetime.now(),fetched_start_at))
    result_raw_bytes = test_env.execute("SELECT batch_id FROM raw_bytes WHERE batch_id = %s", (batch_id,)).fetchone()
    result_response = test_env.execute("SELECT batch_id FROM response WHERE batch_id = %s", (batch_id,)).fetchone()
    if result_raw_bytes is None:
        raise Exception("Batch ID not inserted successfully in raw_bytes table")
    if result_response is None:
        raise Exception("Batch ID not inserted successfully in response table")
    with pytest.raises(NotNullViolation):
        with test_env.transaction():
            test_env.execute(
            "INSERT INTO response"
            "(batch_id,quantity,station_id,station_name,station_area,latitude,longitude,available_rent_bikes," \
            "available_return_bikes,station_active,source_update_time,fetched_start_at) " \
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (batch_id,None,station_id,"station_name","station_area",0.0,0.0,0,0,"0",datetime.now(),fetched_start_at))
    with pytest.raises(CheckViolation):
        with test_env.transaction():
            test_env.execute("INSERT INTO response (batch_id,quantity,station_id,station_name,station_area,latitude,longitude,available_rent_bikes,available_return_bikes,station_active,source_update_time,fetched_start_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (batch_id,-1,station_id,"station_name","station_area",0.0,0.0,0,0,"0",datetime.now(),fetched_start_at))
    with pytest.raises(UniqueViolation):
        with test_env.transaction():
            taipei_tz=zoneinfo.ZoneInfo("Asia/Taipei")
            source_update_time=datetime.now(taipei_tz).astimezone(zoneinfo.ZoneInfo("UTC"))
            test_env.execute("INSERT INTO response (batch_id,quantity,station_id,station_name,station_area,latitude,longitude,available_rent_bikes,available_return_bikes,station_active,source_update_time,fetched_start_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (batch_id,5,station_id,"station_name","station_area",0.0,0.0,0,0,"0",source_update_time,fetched_start_at))
            test_env.execute("INSERT INTO response (batch_id,quantity,station_id,station_name,station_area,latitude,longitude,available_rent_bikes,available_return_bikes,station_active,source_update_time,fetched_start_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (batch_id,5,station_id,"station_name","station_area",0.0,0.0,0,0,"0",source_update_time,fetched_start_at))
    batch_id_1 =str(uuid.uuid4())
    taipei_tz=zoneinfo.ZoneInfo("Asia/Taipei")
    fetched_start_at_1=datetime.now(taipei_tz).astimezone(zoneinfo.ZoneInfo("UTC"))
    test_env.execute("INSERT INTO raw_bytes (batch_id,body,fetched_start_at) VALUES (%s,%s,%s)",(batch_id_1,b"[]",fetched_start_at_1))
    
    batch_id_2 =str(uuid.uuid4())
    taipei_tz=zoneinfo.ZoneInfo("Asia/Taipei")
    fetched_start_at_2=datetime.now(taipei_tz).astimezone(zoneinfo.ZoneInfo("UTC"))
    test_env.execute("INSERT INTO raw_bytes (batch_id,body,fetched_start_at) VALUES (%s,%s,%s)",(batch_id_2,b"[]",fetched_start_at_2))
    with pytest.raises(ForeignKeyViolation):
        with test_env.transaction():
            test_env.execute("INSERT INTO response (batch_id,quantity,station_id,station_name," \
            "station_area,latitude,longitude,available_rent_bikes,available_return_bikes,station_active," \
            "source_update_time,fetched_start_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (batch_id_1,5,station_id,"station_name","station_area",0.0,0.0,0,0,"0",source_update_time,
             fetched_start_at_1))
            
            test_env.execute("INSERT INTO response (batch_id,quantity,station_id,station_name," \
            "station_area,latitude,longitude,available_rent_bikes,available_return_bikes,station_active," \
            "source_update_time,fetched_start_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (batch_id_2,5,station_id,"station_name","station_area",0.0,0.0,0,0,"0",source_update_time,
                fetched_start_at_2))
            # error insertion
            test_env.execute(
                "INSERT INTO response (batch_id,quantity,station_id,station_name,station_area,latitude,longitude,available_rent_bikes,available_return_bikes,station_active,source_update_time,fetched_start_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (batch_id_1,5,str(uuid.uuid4()),"station_name","station_area",0.0,0.0,0,0,"0",source_update_time,fetched_start_at_2),
            )
