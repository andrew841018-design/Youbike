import os,uuid,random,pytest,psycopg,socket,requests
from datetime import datetime,timezone
from psycopg.conninfo import make_conninfo
from dotenv import dotenv_values 
from src.extract.youbike import extract_youbike,check_json
from unittest.mock import MagicMock
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from psycopg.errors import UniqueViolation


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

@pytest.mark.parametrize("row,type,col,should_raise",
    [
        ({"Quantity": 0},int,"Quantity",False),
        ({"Quantity": 10},int,"Quantity",False),
        ({"Quantity": -1},int,"Quantity",True),
        ({"Quantity": True},int,"Quantity",True),
        ({"Quantity": 1.5},int,"Quantity",True)
    ]
)
def test_check_json(row,type,col,should_raise):
    if should_raise:
        with pytest.raises(ValueError):
            check_json(row,type,col)
    else:
        check_json(row,type,col)
@pytest.fixture
def local_server(failure_test_env):
    class handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(503)
            self.end_headers()
    with HTTPServer(("127.0.0.1", 0), handler) as server:
        thread = Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/"
        finally:
            server.shutdown()
            thread.join()
def test_web_scrapping_503_error(local_server):
    with psycopg.connect(os.environ["YOUBIKE_DATABASE_URL"]) as conn:
        raw_bytes_count_before=conn.execute("SELECT COUNT(*) FROM raw_bytes").fetchone()[0]
        response_count_before=conn.execute("SELECT COUNT(*) FROM response").fetchone()[0]
        with pytest.raises(Exception, match=r"^Request failed with status code: 503$"):
            extract_youbike(url=local_server)
        raw_bytes_count_after=conn.execute("SELECT COUNT(*) FROM raw_bytes").fetchone()[0]
        response_count_after=conn.execute("SELECT COUNT(*) FROM response").fetchone()[0]
        assert raw_bytes_count_after==raw_bytes_count_before
        assert response_count_after==response_count_before