from dotenv import dotenv_values
import psycopg
from src.extract.youbike import extract_youbike

dsn = dotenv_values(".env")["YOUBIKE_DATABASE_URL"]
with psycopg.connect(dsn,autocommit=True) as conn:
    for slot in conn.execute("""
    SELECT expect.slot 
    FROM generate_series('2026-11-03 17:30:00+08',NOW()-INTERVAL '30 minutes','30 minutes') as expect(slot)
    WHERE NOT EXISTS (SELECT 1 FROM raw_bytes WHERE fetched_start_at = expect.slot) 
    AND NOT EXISTS (SELECT 1 FROM run_status WHERE scheduled_at = expect.slot)
    ORDER BY expect.slot
    """):
        extract_youbike(scrape_time=slot[0])

    slot = conn.execute("""
    SELECT expect.slot 
    FROM generate_series('2026-11-03 17:30:00+08',NOW()-INTERVAL '30 minutes','30 minutes') as expect(slot)
    WHERE EXISTS (SELECT 1 FROM raw_bytes WHERE fetched_start_at = expect.slot) 
    AND NOT EXISTS (SELECT 1 FROM run_status WHERE scheduled_at = expect.slot)
    ORDER BY expect.slot
    """).fetchone()
    if slot is not None:
        raise RuntimeError(f"Missing slot in response and raw_bytes table: {slot[0]}")

    