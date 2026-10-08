from datetime import datetime as DateTime,timezone
from airflow.sdk import DAG
import sys
from pathlib import Path
youbike_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(youbike_root))

from src.extract.youbike import extract_youbike
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import RetryPolicy, RetryDecision
import requests

class Retry_Policy(RetryPolicy):
    def evaluate(self, exception, try_number, max_tries, context=None):
        if isinstance(exception, requests.Timeout) or isinstance(exception, requests.ConnectionError):
            return RetryDecision.retry()
        if isinstance(exception, requests.HTTPError):
            if exception.response is not None:
                HttpError = exception.response.status_code
                if (HttpError >= 500 and HttpError < 600) or HttpError == 429:
                    return RetryDecision.retry()
        return RetryDecision.fail()
with DAG(
    dag_id="youbike_realtime_dag",
    schedule="*/30 * * * *",
    start_date=DateTime(2023, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
) as dag:
    policy = Retry_Policy()
    PythonOperator(
        task_id="scrape_youbike_realtime",
        python_callable=extract_youbike,  # Replace with actual scraping logic
        op_kwargs={
            "scrape_time": "{{ data_interval_end }}",
        },
        retries=4,
        retry_delay=60,  # Retry after 60 seconds
        retry_exponential_backoff=True,  # Exponential backoff for retries
        max_retry_delay=600,  # Maximum retry delay of 10 minutes
        retry_policy=Retry_Policy(),
    )
