import psycopg
from src.extract.youbike import record_missing
from config import get_env_variable

dsn = get_env_variable("YOUBIKE_DATABASE_URL")
with psycopg.connect(dsn,autocommit=True) as conn:
    for (slot_time,) in conn.execute("""
    SELECT expect.slot_time 
    FROM generate_series('2026-11-03 17:30:00+08',NOW()-INTERVAL '30 minutes','30 minutes') as expect(slot_time)
    WHERE NOT EXISTS (SELECT 1 FROM raw_bytes WHERE slot_time = expect.slot_time) 
    AND NOT EXISTS (SELECT 1 FROM run_status WHERE slot_time = expect.slot_time)
    ORDER BY expect.slot_time
    """):
        record_missing(conn, slot_time)

    raw_without_run_status = conn.execute("""
    SELECT expect.slot_time 
    FROM generate_series('2026-11-03 17:30:00+08',NOW()-INTERVAL '30 minutes','30 minutes') as expect(slot_time)
    WHERE EXISTS (SELECT 1 FROM raw_bytes WHERE slot_time = expect.slot_time) 
    AND NOT EXISTS (SELECT 1 FROM run_status WHERE slot_time = expect.slot_time)
    ORDER BY expect.slot_time
    """).fetchone()
    if raw_without_run_status is not None:
        raise RuntimeError(f"Missing slot in response and raw_bytes table: {raw_without_run_status[0]}")

    