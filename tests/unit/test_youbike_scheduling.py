import pytest
import json

import os
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
import src.extract.youbike as youbike_module
import subprocess
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

@pytest.fixture
def controlled_raw_http_server():
    """Serve stored raw bytes with request counting and response control."""
    items=[{"sno":"1","sna":"D2-1","sarea":"fixture","latitude":25.03,"longitude":121.56,"Quantity":6,
            "available_rent_bikes":7,"available_return_bikes":20,"act":"1","srcUpdateTime":"2023-08-01 00:00:00"}]
    body = json.dumps(items).encode("utf-8")
    control = {"get_count": 0, "received": Event(), "release": Event()}
    control["release"].set()  # requests can respond immediately.

    class ControlledHTTPRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            control["get_count"] += 1
            control["received"].set()
            if not control["release"].wait(timeout=5):
                self.send_error(504, "Test did not release the HTTP response")
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with HTTPServer(("127.0.0.1", 0), ControlledHTTPRequestHandler) as server:
        control["url"] = f"http://127.0.0.1:{server.server_port}/"
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            yield control
        finally:
            control["release"].set()  # next time requests initiate
            server.shutdown()
            thread.join()

@pytest.fixture
def existing_raw(test_conn):
    batch_id = "a10a2ce6-b198-42fb-9cd6-2c0a629633f5"
    row = test_conn.execute("SELECT batch_id, slot_time, body FROM raw_bytes WHERE batch_id = %s", (batch_id,)).fetchone()
    if row is None:
        raise RuntimeError(f"Batch ID {batch_id} not found in raw_bytes table")
    batch_id, slot_time, body = row
    dict = {
        "batch_id": batch_id,
        "slot_time": slot_time,
        "body": body
    }
    return dict


def start_youbike_worker(url, slot_time, now):
    project_root = Path(__file__).resolve().parents[2]
    child_env = os.environ.copy()
    child_env["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(project_root), child_env.get("PYTHONPATH", "")) if path
    )
    return subprocess.Popen(
        [sys.executable, str(project_root / "tests/helpers/youbike_worker.py"),
         "--url", url, "--slot_time", slot_time, "--now", now],
        env=child_env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )

def test_two_youbike_workers_enter_at_same_time(controlled_raw_http_server,test_conn):
    with test_conn.cursor() as cursor:
        slot_time = cursor.execute("SELECT date_trunc('hour', COALESCE(MIN(slot_time),NOW()),'UTC') - INTERVAL '60 minutes' AS slot_time FROM raw_bytes").fetchone()[0]
    slot_time_iso = slot_time.isoformat()
    controlled_raw_http_server["release"].clear()
    try:
        a=start_youbike_worker(controlled_raw_http_server["url"], slot_time_iso, slot_time_iso)# A
        assert controlled_raw_http_server["received"].wait(timeout=5)## A get will release this also make sure A stuck in http request can't response
        b=start_youbike_worker(controlled_raw_http_server["url"], slot_time_iso, slot_time_iso)# B
        b.communicate(timeout=5)# wait for B to finish.
        assert b.returncode == 0 # make sure B finished successfully
        assert a.poll() is None # A is still running
        controlled_raw_http_server["release"].set()# release both A and B from http request
        a.communicate(timeout=5)

        assert a.returncode == 0
        assert controlled_raw_http_server["get_count"] == 1
        with test_conn.cursor() as cursor:
            row = cursor.execute("SELECT count(*) FROM raw_bytes WHERE slot_time = %s", (slot_time,)).fetchone()
            row_1 = cursor.execute("SELECT count(*) FROM response WHERE slot_time = %s", (slot_time,)).fetchone()
        assert row[0] == 1
        assert row_1[0] == 1
    except: # if B crash
        if b.returncode != 0:
            b.kill()
            assert a.poll() is None
            controlled_raw_http_server["release"].set()
            a.communicate(timeout=5)
        raise




def test_existing_raw_replays_without_http(existing_raw,controlled_raw_http_server,monkeypatch):
    loaded_batch_ids = []
    load_youbike = youbike_module.load_youbike
    def recording_load_youbike(batch_id):
        loaded_batch_ids.append(batch_id)
        return load_youbike(batch_id)
    monkeypatch.setattr(youbike_module, "load_youbike", recording_load_youbike)

    youbike_module.extract_youbike(url=controlled_raw_http_server["url"],slot_time=existing_raw["slot_time"].isoformat())
    assert controlled_raw_http_server["get_count"] == 0
    assert existing_raw["batch_id"] in loaded_batch_ids


def test_expired_without_raw_is_missing(caplog,test_conn,controlled_raw_http_server,monkeypatch):
    with test_conn.cursor() as cursor:
        slot_time = cursor.execute("SELECT date_trunc('hour', COALESCE(MIN(slot_time),NOW()),'UTC') - INTERVAL '60 minutes' FROM raw_bytes").fetchone()[0]
        # 產品呼叫 DateTime.now(...) 時固定回傳 slot_end（slot 剛好到期的那一刻）
        slot_end = slot_time + timedelta(minutes=30)
        class NewDateTime(datetime):
            @staticmethod
            def now(tz=None):
                return slot_end.astimezone(tz) if tz else slot_end

        monkeypatch.setattr(youbike_module, "DateTime", NewDateTime)
        youbike_module.extract_youbike(url=controlled_raw_http_server["url"],slot_time=slot_time.isoformat())
        count = cursor.execute("SELECT count(*) FROM raw_bytes WHERE slot_time = %s", (slot_time,)).fetchone()[0]
        assert controlled_raw_http_server["get_count"] == 0
        assert count == 0
        assert "missing" in caplog.text
        assert str(slot_time.astimezone(timezone.utc)) in caplog.text

    