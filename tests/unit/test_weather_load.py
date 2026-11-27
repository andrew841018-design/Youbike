import json
import psycopg
import pytest
from src.extract.weather import extract_weather, store_raw, store_weather_observation

@pytest.fixture(scope="module")
def weather_body():
    return extract_weather()  # 每次真的去抓，整個檔只抓一次

def clear_same_hour(conn, data):
    # 測試庫可能已經有同一小時的列（手動跑過最外層），先在這個測試的交易裡刪掉；測試結束 rollback 會還原
    stations = data["cwaopendata"]["dataset"]["Station"]
    hours = list({s["ObsTime"]["DateTime"] for s in stations})
    conn.execute("delete from weather_observation where observe_time = any(%s::timestamptz[])", (hours,))

def test_same_table_update_twice(test_conn, weather_body):
    clear_same_hour(test_conn, json.loads(weather_body))
    raw_id = store_raw(weather_body, test_conn)
    store_weather_observation(test_conn, raw_id)
    before = test_conn.execute("select * from weather_observation where raw_id = %s order by station_id", (raw_id,)).fetchall()
    store_weather_observation(test_conn, raw_id)
    after = test_conn.execute("select * from weather_observation where raw_id = %s order by station_id", (raw_id,)).fetchall()
    assert after == before

def test_broken_station_writes_nothing_but_keeps_raw(test_conn, weather_body):
    data = json.loads(weather_body)
    clear_same_hour(test_conn, data)
    stations = data["cwaopendata"]["dataset"]["Station"]
    for c in stations[-1]["GeoInfo"]["Coordinates"]:  # 最後一站壞掉：前面的站都寫過了才出錯
        if c["CoordinateName"] == "WGS84":
            c["StationLatitude"] = "91"
    raw_id = store_raw(json.dumps(data).encode(), test_conn) # record origin data including error data
    with pytest.raises(psycopg.errors.CheckViolation):
        store_weather_observation(test_conn, raw_id)
    row = test_conn.execute("select count(*) from weather_observation where raw_id = %s", (raw_id,)).fetchone()
    row_1 = test_conn.execute("select count(*) from weather where id = %s", (raw_id,)).fetchone()
    observation_count = row[0]
    raw_count = row_1[0]
    assert observation_count == 0
    assert raw_count == 1
