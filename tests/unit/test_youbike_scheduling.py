import pytest
import json
import logging

import os
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
import psycopg
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
def existing_raw(check_database_name):
    conn = check_database_name
    batch_id = "a10a2ce6-b198-42fb-9cd6-2c0a629633f5"
    row = conn.execute("SELECT batch_id, fetched_start_at, body FROM raw_bytes WHERE batch_id = %s", (batch_id,)).fetchone()
    if row is None:
        raise RuntimeError(f"Batch ID {batch_id} not found in raw_bytes table")
    batch_id, fetched_start_at, body = row
    dict = {
        "batch_id": batch_id,
        "fetched_start_at": fetched_start_at,
        "body": body
    }
    return dict


def start_youbike_worker(url, slot, now):
    project_root = Path(__file__).resolve().parents[2]
    child_env = os.environ.copy()
    child_env["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(project_root), child_env.get("PYTHONPATH", "")) if path
    )
    return subprocess.Popen(
        [sys.executable, str(project_root / "tests/helpers/youbike_worker.py"),
         "--url", url, "--slot", slot, "--now", now],
        env=child_env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )

def test_two_youbike_workers_enter_at_same_time(controlled_raw_http_server,check_database_name):
    cnn = check_database_name
    control = controlled_raw_http_server
    with cnn.cursor() as cursor:
        scrape_time = cursor.execute("SELECT date_trunc('hour', COALESCE(MIN(fetched_start_at),NOW()),'UTC') - INTERVAL '60 minutes' AS scrape_time FROM raw_bytes").fetchone()[0]
    slot = scrape_time.isoformat()
    control["release"].clear()
    try:
        a=start_youbike_worker(control["url"], slot, slot)# A
        assert control["received"].wait(timeout=5)## A get will release this also make sure A stuck in http request can't response
        b=start_youbike_worker(control["url"], slot, slot)# B
        b.communicate(timeout=5)# wait for B to finish.
        assert b.returncode == 0 # make sure B finished successfully
        assert a.poll() is None # A is still running
        control["release"].set()# release both A and B from http request
        a.communicate(timeout=5)

        assert a.returncode == 0
        assert control["get_count"] == 1
        with cnn.cursor() as cursor:
            row = cursor.execute("SELECT count(*) FROM raw_bytes WHERE fetched_start_at = %s", (scrape_time,)).fetchone()
            row_1 = cursor.execute("SELECT count(*) FROM response WHERE fetched_start_at = %s", (scrape_time,)).fetchone()
        assert row[0] == 1
        assert row_1[0] == 1
    except: # if B crash
        if b.returncode != 0:
            b.kill()
            assert a.poll() is None
            control["release"].set()
            a.communicate(timeout=5)
        raise




def test_existing_raw_replays_without_http(existing_raw,controlled_raw_http_server):
    raw = existing_raw
    control = controlled_raw_http_server

    youbike_module.extract_youbike(url=control["url"],scrape_time=raw["fetched_start_at"].isoformat())
    assert control["get_count"] == 0
    assert raw["batch_id"] in youbike_module.load_count


def test_expired_without_raw_is_missing(caplog,check_database_name,controlled_raw_http_server,monkeypatch):
    control = controlled_raw_http_server
    conn = check_database_name
    with conn.cursor() as cursor:
        slot = cursor.execute("SELECT date_trunc('hour', COALESCE(MIN(fetched_start_at),NOW()),'UTC') - INTERVAL '60 minutes' FROM raw_bytes").fetchone()[0]
        # 產品呼叫 DateTime.now(...) 時固定回傳 expire_time（slot 剛好到期的那一刻）
        expire_time = slot + timedelta(minutes=30)
        class NewDateTime(datetime):
            @staticmethod
            def now(tz=None):
                return expire_time.astimezone(tz) if tz else expire_time

        monkeypatch.setattr(youbike_module, "DateTime", NewDateTime)
        youbike_module.extract_youbike(url=control["url"],scrape_time=slot.isoformat())
        count = cursor.execute("SELECT count(*) FROM raw_bytes WHERE fetched_start_at = %s", (slot,)).fetchone()[0]
        assert control["get_count"] == 0
        assert count == 0
        assert "missing" in caplog.text
        assert str(slot.astimezone(timezone.utc)) in caplog.text

    