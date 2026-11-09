from config import get_env_variable
import pytest
import psycopg

@pytest.fixture
def switch_env(monkeypatch):
    test_dsn = get_env_variable("YOUBIKE_TEST_DATABASE_URL")
    if not test_dsn:
        raise RuntimeError("YOUBIKE_TEST_DATABASE_URL not found in .env")
    monkeypatch.setenv("YOUBIKE_DATABASE_URL", test_dsn)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    yield test_dsn

@pytest.fixture
def check_database_name(switch_env):
    dsn = switch_env
    with psycopg.connect(dsn) as conn:
        database = conn.execute("SELECT current_database()").fetchone()[0]
        if database != "youbike_test":
            raise RuntimeError("Database name is not youbike_test")
        try:
            yield conn
        finally:
            conn.rollback()

