import os,pytest,psycopg,socket,requests
from psycopg.conninfo import make_conninfo
from src.extract.youbike import extract_youbike
from src.extract.youbike_model import YoubikeStation
from pydantic import ValidationError
from unittest.mock import MagicMock
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

def test_extract_raw_body(check_database_name):
    conn = check_database_name
    before = conn.execute("SELECT count(DISTINCT batch_id) FROM raw_bytes").fetchone()[0]
    slot = conn.execute("SELECT MAX(fetched_start_at)+ INTERVAL '60 minutes' FROM raw_bytes").fetchone()[0]
    extract_youbike(scrape_time=slot)
    after = conn.execute("SELECT count(DISTINCT batch_id) FROM raw_bytes").fetchone()[0]
    assert after == before + 1
def test_db_failure(monkeypatch, switch_env):
    test_dsn = switch_env
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
def http_200_response(monkeypatch):
    """Provide HTTP chunks directly for the size/time logic tests."""
    response = MagicMock()
    response.status_code = 200
    response.__enter__.return_value = response
    monkeypatch.setattr("src.extract.youbike.requests.get", lambda *args, **kwargs: response)
    return response


def test_http_read_timeout(switch_env):
    # TCP connects, but no HTTP response is sent. Keep the listener open.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        with pytest.raises(requests.exceptions.ReadTimeout):
            extract_youbike(url=f"http://127.0.0.1:{port}/")


def test_response_size_limit(switch_env, http_200_response):
    # 80 chunks total 5 MiB; the final byte exceeds the limit.
    http_200_response.iter_content.return_value = [b"x" * (64 * 1024)] * 80 + [b"x"]# 5MiB
    with pytest.raises(ValueError, match=r"^Response size limit exceeded$"):
        extract_youbike()


def test_stream_time_budget(switch_env, http_200_response, monkeypatch):
    http_200_response.iter_content.return_value = [b"x"]
    # The product sees 31 seconds elapsed without making the test wait.
    monkeypatch.setattr("src.extract.youbike.monotonic", MagicMock(side_effect=[0, 31]))
    with pytest.raises(TimeoutError, match=r"^Time limit exceeded$"):
        extract_youbike()

VALID_STATION = {"sno":"1","sna":"model check","sarea":"fixture","latitude":25.03,"longitude":121.56,"Quantity":6,
                 "available_rent_bikes":2,"available_return_bikes":4,"act":"1","srcUpdateTime":"2023-08-01 00:00:00"}
@pytest.mark.parametrize("quantity,should_raise",
    [
        (0,False),
        (10,False),
        (-1,True),
        (True,True),
        (1.5,True)
    ]
)
def test_station_model_quantity(quantity,should_raise):
    row = dict(VALID_STATION, Quantity=quantity)
    if should_raise:
        with pytest.raises(ValidationError):
            YoubikeStation.model_validate(row)
    else:
        YoubikeStation.model_validate(row)
@pytest.fixture
def local_server(switch_env):
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