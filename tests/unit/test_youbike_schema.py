import uuid
from datetime import datetime
import zoneinfo
from psycopg.errors import NotNullViolation,UniqueViolation,CheckViolation,ForeignKeyViolation
import pytest
def test_schema(test_conn):
    batch_id =str(uuid.uuid4())
    station_id = str(uuid.uuid4())
    taipei_tz=zoneinfo.ZoneInfo("Asia/Taipei")
    slot_time=datetime.now(taipei_tz).astimezone(zoneinfo.ZoneInfo("UTC"))
    test_conn.execute("INSERT INTO raw_bytes (batch_id,body,slot_time) VALUES (%s,%s,%s)",(batch_id,b"[]",slot_time))
    test_conn.execute("INSERT INTO response (batch_id,quantity,station_id,station_name,station_area,latitude,longitude,available_rent_bikes,available_return_bikes,station_active,source_update_time,slot_time) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(batch_id,5,station_id,"station_name","station_area",0.0,0.0,0,0,"0",datetime.now(),slot_time))
    result_raw_bytes = test_conn.execute("SELECT batch_id FROM raw_bytes WHERE batch_id = %s", (batch_id,)).fetchone()
    result_response = test_conn.execute("SELECT batch_id FROM response WHERE batch_id = %s", (batch_id,)).fetchone()
    if result_raw_bytes is None:
        raise Exception("Batch ID not inserted successfully in raw_bytes table")
    if result_response is None:
        raise Exception("Batch ID not inserted successfully in response table")
    with pytest.raises(NotNullViolation):
        with test_conn.transaction():
            test_conn.execute(
            "INSERT INTO response"
            "(batch_id,quantity,station_id,station_name,station_area,latitude,longitude,available_rent_bikes," \
            "available_return_bikes,station_active,source_update_time,slot_time) " \
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (batch_id,None,station_id,"station_name","station_area",0.0,0.0,0,0,"0",datetime.now(),slot_time))
    with pytest.raises(CheckViolation):
        with test_conn.transaction():
            test_conn.execute("INSERT INTO response (batch_id,quantity,station_id,station_name,station_area,latitude,longitude,available_rent_bikes,available_return_bikes,station_active,source_update_time,slot_time) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (batch_id,-1,station_id,"station_name","station_area",0.0,0.0,0,0,"0",datetime.now(),slot_time))
    with pytest.raises(UniqueViolation):
        with test_conn.transaction():
            taipei_tz=zoneinfo.ZoneInfo("Asia/Taipei")
            source_update_time=datetime.now(taipei_tz).astimezone(zoneinfo.ZoneInfo("UTC"))
            test_conn.execute("INSERT INTO response (batch_id,quantity,station_id,station_name,station_area,latitude,longitude,available_rent_bikes,available_return_bikes,station_active,source_update_time,slot_time) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (batch_id,5,station_id,"station_name","station_area",0.0,0.0,0,0,"0",source_update_time,slot_time))
    batch_id_1 =str(uuid.uuid4())
    taipei_tz=zoneinfo.ZoneInfo("Asia/Taipei")
    slot_time_1=datetime.now(taipei_tz).astimezone(zoneinfo.ZoneInfo("UTC"))
    test_conn.execute("INSERT INTO raw_bytes (batch_id,body,slot_time) VALUES (%s,%s,%s)",(batch_id_1,b"[]",slot_time_1))
    
    batch_id_2 =str(uuid.uuid4())
    taipei_tz=zoneinfo.ZoneInfo("Asia/Taipei")
    slot_time_2=datetime.now(taipei_tz).astimezone(zoneinfo.ZoneInfo("UTC"))
    test_conn.execute("INSERT INTO raw_bytes (batch_id,body,slot_time) VALUES (%s,%s,%s)",(batch_id_2,b"[]",slot_time_2))
    with pytest.raises(ForeignKeyViolation):
        with test_conn.transaction():
            # Parent raw rows already exist; only the mismatched pair is needed.
            test_conn.execute(
                "INSERT INTO response (batch_id,quantity,station_id,station_name,station_area,latitude,longitude,available_rent_bikes,available_return_bikes,station_active,source_update_time,slot_time) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (batch_id_1,5,str(uuid.uuid4()),"station_name","station_area",0.0,0.0,0,0,"0",source_update_time,slot_time_2),
            )
