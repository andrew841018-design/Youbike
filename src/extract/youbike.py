import requests
import psycopg
def extract_youbike():
    url = "https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json"
    response = requests.get(url)
    assert response.status_code == 200
    with psycopg.connect("dbname=extract") as conn:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO youbike (data) VALUES (%s)", (response.json(),))
