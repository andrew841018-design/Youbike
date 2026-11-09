from src.extract.youbike import load_youbike
def test_load_replay_and_reconcile(check_database_name):
    conn = check_database_name
    batch_id = "17ed1a5b-d1fd-4830-8826-acba159d89fd"
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
