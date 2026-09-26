import os
import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from dotenv import dotenv_values
from src.extract.youbike import extract_youbike
import socket
import pytest
import requests
from unittest.mock import MagicMock

def test_extract_raw_body(monkeypatch):
    config=dotenv_values("/Users/andrew/Desktop/andrew/Data_engineer/Youbike/.env")
    test_dsn=config["YOUBIKE_TEST_DATABASE_URL"]
    if not test_dsn:
        raise RuntimeError("YOUBIKE_TEST_DATABASE_URL not found in .env")
    monkeypatch.setenv("YOUBIKE_DATABASE_URL",test_dsn)# switch database
    with psycopg.connect(os.environ["YOUBIKE_DATABASE_URL"]) as conn:
        database=conn.execute("SELECT current_database()").fetchone()[0]
        if database != "youbike_test":
            raise RuntimeError("Database name is not youbike_test")
        before = conn.execute("SELECT count(DISTINCT batch_id) FROM raw_bytes").fetchone()[0]
        extract_youbike()
        after = conn.execute("SELECT count(DISTINCT batch_id) FROM raw_bytes").fetchone()[0]
        assert after == before + 1
def test_db_failure(monkeypatch):
    config=dotenv_values("/Users/andrew/Desktop/andrew/Data_engineer/Youbike/.env")
    test_dsn=config["YOUBIKE_TEST_DATABASE_URL"]
    if not test_dsn:
        raise RuntimeError("YOUBIKE_TEST_DATABASE_URL not found in .env")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        unused_port = sock.getsockname()[1]
        bad_dsn = make_conninfo(
            test_dsn,
            host="127.0.0.1",
            port=unused_port,
            hostaddr = "127.0.0.1",
            connect_timeout=3
        )
    monkeypatch.setenv("YOUBIKE_DATABASE_URL",bad_dsn)# switch database
    with pytest.raises(psycopg.OperationalError) as errinfo:
        extract_youbike()
    message = str(errinfo.value)
    assert "Connection refused" in message
    assert str(unused_port) in message
def test_http_404(monkeypatch):
    config=dotenv_values("/Users/andrew/Desktop/andrew/Data_engineer/Youbike/.env")
    test_dsn=config["YOUBIKE_TEST_DATABASE_URL"]
    if not test_dsn:
        raise RuntimeError("YOUBIKE_TEST_DATABASE_URL not found in .env")
    monkeypatch.setenv("YOUBIKE_DATABASE_URL",test_dsn)
    with pytest.raises(Exception, match=r"^Request failed with status code: 404$"):
        extract_youbike(url="https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate_missing.json")


@pytest.fixture
def failure_test_env(monkeypatch):
    config = dotenv_values("/Users/andrew/Desktop/andrew/Data_engineer/Youbike/.env")
    test_dsn = config.get("YOUBIKE_TEST_DATABASE_URL")
    if not test_dsn:
        raise RuntimeError("YOUBIKE_TEST_DATABASE_URL not found in .env")
    monkeypatch.setenv("YOUBIKE_DATABASE_URL", test_dsn)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")


@pytest.fixture
def http_200_response(monkeypatch):
    """Provide HTTP chunks directly for the size/time logic tests."""
    response = MagicMock()
    response.status_code = 200
    response.__enter__.return_value = response
    monkeypatch.setattr("src.extract.youbike.requests.get", lambda *args, **kwargs: response)
    return response


def test_http_read_timeout(failure_test_env):
    # TCP connects, but no HTTP response is sent. Keep the listener open.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        with pytest.raises(requests.exceptions.ReadTimeout):
            extract_youbike(url=f"http://127.0.0.1:{port}/")


def test_response_size_limit(failure_test_env, http_200_response):
    # 80 chunks total 5 MiB; the final byte exceeds the limit.
    http_200_response.iter_content.return_value = [b"x" * (64 * 1024)] * 80 + [b"x"]# 5MiB
    with pytest.raises(ValueError, match=r"^Response size limit exceeded$"):
        extract_youbike()


def test_stream_time_budget(failure_test_env, http_200_response, monkeypatch):
    http_200_response.iter_content.return_value = [b"x"]
    # The product sees 31 seconds elapsed without making the test wait.
    monkeypatch.setattr("src.extract.youbike.monotonic", MagicMock(side_effect=[0, 31]))
    with pytest.raises(TimeoutError, match=r"^Time limit exceeded$"):
        extract_youbike()
