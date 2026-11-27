import json
from datetime import datetime, timedelta

import psycopg
import pytest

from src.extract.weather import extract_weather, store_raw, store_weather_observation

CODES = {"-99", "X", "-98", "T"}


@pytest.fixture(scope="module")
def weather_body():
    return extract_weather()  # 每次真的去抓，整個檔只抓一次


def stations_of(data):
    return data["cwaopendata"]["dataset"]["Station"]


def clear_same_hour(conn, data):
    # 測試庫可能已經有同一小時的列（手動跑過最外層），先在這個測試的交易裡刪掉；測試結束 rollback 會還原
    hours = list({s["ObsTime"]["DateTime"] for s in stations_of(data)})
    conn.execute("delete from weather_observation where observe_time = any(%s::timestamptz[])", (hours,))


def count_rows(conn, raw_id):
    return conn.execute("select count(*) from weather_observation where raw_id = %s", (raw_id,)).fetchone()[0]


def test_load_keeps_count_codes_time_and_wgs84(test_conn, weather_body):
    data = json.loads(weather_body)
    stations = stations_of(data)
    missing = [s["StationId"] for s in stations if s["WeatherElement"]["AirTemperature"] == "-99"]
    assert missing, "這一小時沒有氣溫 -99 的站，缺值檢查沒東西可查"
    first = stations[0]
    wgs84 = next(c for c in first["GeoInfo"]["Coordinates"] if c["CoordinateName"] == "WGS84")
    clear_same_hour(test_conn, data)

    raw_id = store_raw(weather_body, test_conn)
    store_weather_observation(test_conn, raw_id)

    assert count_rows(test_conn, raw_id) == len(stations)
    kept = test_conn.execute(
        "select count(*) from weather_observation where raw_id = %s and station_id = any(%s)"
        " and temperature is null and temperature_code = '-99'", (raw_id, missing)).fetchone()[0]
    assert kept == len(missing)
    lat, lon, published = test_conn.execute(
        "select latitude, longitude, publish_time from weather_observation where raw_id = %s and station_id = %s",
        (raw_id, first["StationId"])).fetchone()
    assert (lat, lon) == (float(wgs84["StationLatitude"]), float(wgs84["StationLongitude"]))
    assert published == datetime.fromisoformat(data["cwaopendata"]["sent"])


def test_same_raw_twice_changes_nothing(test_conn, weather_body):
    clear_same_hour(test_conn, json.loads(weather_body))
    raw_id = store_raw(weather_body, test_conn)
    store_weather_observation(test_conn, raw_id)
    before = test_conn.execute("select * from weather_observation where raw_id = %s order by station_id", (raw_id,)).fetchall()

    store_weather_observation(test_conn, raw_id)

    after = test_conn.execute("select * from weather_observation where raw_id = %s order by station_id", (raw_id,)).fetchall()
    assert after == before


def test_older_copy_does_not_overwrite_newer(test_conn, weather_body):
    data = json.loads(weather_body)
    clear_same_hour(test_conn, data)
    target = next(s for s in stations_of(data) if s["WeatherElement"]["AirTemperature"] not in CODES)
    real = float(target["WeatherElement"]["AirTemperature"])
    new_id = store_raw(weather_body, test_conn)
    store_weather_observation(test_conn, new_id)

    data["cwaopendata"]["sent"] = (datetime.fromisoformat(data["cwaopendata"]["sent"]) - timedelta(minutes=10)).isoformat()
    target["WeatherElement"]["AirTemperature"] = str(real + 1)
    old_id = store_raw(json.dumps(data).encode(), test_conn)
    store_weather_observation(test_conn, old_id)

    row = test_conn.execute(
        "select raw_id, temperature from weather_observation where station_id = %s and observe_time = %s",
        (target["StationId"], target["ObsTime"]["DateTime"])).fetchone()
    assert row == (new_id, real)


def test_broken_station_writes_nothing_but_keeps_raw(test_conn, weather_body):
    data = json.loads(weather_body)
    clear_same_hour(test_conn, data)
    for c in stations_of(data)[-1]["GeoInfo"]["Coordinates"]:  # 最後一站壞掉：前面的站都寫過了才出錯
        if c["CoordinateName"] == "WGS84":
            c["StationLatitude"] = "91"
    raw_id = store_raw(json.dumps(data).encode(), test_conn)

    with pytest.raises(psycopg.errors.CheckViolation):
        store_weather_observation(test_conn, raw_id)

    assert count_rows(test_conn, raw_id) == 0
    assert test_conn.execute("select count(*) from weather where id = %s", (raw_id,)).fetchone()[0] == 1
