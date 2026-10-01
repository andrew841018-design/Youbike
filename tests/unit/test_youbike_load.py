from src.extract.youbike import load_youbike
import psycopg
from dotenv import dotenv_values
import os
def test_load_replay_and_reconcile(monkeypatch):
    config=dotenv_values("/Users/andrew/Desktop/andrew/Data_engineer/Youbike/.env")
    test_dsn=config["YOUBIKE_TEST_DATABASE_URL"]
    if not test_dsn:
        raise RuntimeError("YOUBIKE_TEST_DATABASE_URL not found in .env")
    monkeypatch.setenv("YOUBIKE_DATABASE_URL",test_dsn)
    batch_id = "17ed1a5b-d1fd-4830-8826-acba159d89fd"
    with psycopg.connect(os.environ["YOUBIKE_DATABASE_URL"]) as conn:
        database = conn.execute("SELECT current_database()").fetchone()[0]
        if database != "youbike_test":
            raise RuntimeError("Database name is not youbike_test")
        load_youbike(batch_id)
        rows_before = conn.execute("SELECT * FROM response WHERE batch_id = %s ORDER BY station_id", (batch_id,)).fetchall()
        load_youbike(batch_id)
        rows_after = conn.execute("SELECT * FROM response WHERE batch_id = %s ORDER BY station_id", (batch_id,)).fetchall()
        assert rows_after == rows_before
        assert len(rows_after) == 2
        batch_id = "b3056c50-9471-4349-9a3c-32859e981058"
        load_youbike(batch_id)
        rows_before = conn.execute("SELECT * FROM response WHERE batch_id = %s ORDER BY station_id", (batch_id,)).fetchall()
        load_youbike(batch_id)
        rows_after = conn.execute("SELECT * FROM response WHERE batch_id = %s ORDER BY station_id", (batch_id,)).fetchall()
        assert rows_after == rows_before
        assert len(rows_after) == 2
