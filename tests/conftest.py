from config import get_env_variable
import pytest
import psycopg

@pytest.fixture
def test_dsn(monkeypatch):
    dsn = get_env_variable("YOUBIKE_TEST_DATABASE_URL")
    if not dsn:
        raise RuntimeError("YOUBIKE_TEST_DATABASE_URL not found in .env")
    monkeypatch.setenv("YOUBIKE_DATABASE_URL", dsn)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    yield dsn

@pytest.fixture
def test_conn(test_dsn):
    with psycopg.connect(test_dsn) as conn:
        database = conn.execute("SELECT current_database()").fetchone()[0]
        if database != "youbike_test":
            raise RuntimeError("Database name is not youbike_test")
        try:
            yield conn
        finally:
            conn.rollback()

