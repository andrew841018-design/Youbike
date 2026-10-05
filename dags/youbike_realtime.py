from datetime import datetime as DateTime,timezone
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator
with DAG(
    dag_id="youbike_realtime_dag",
    schedule="*/5 * * * *",
    start_date=DateTime(2023, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
) as dag:
    BashOperator(
        task_id="scrape_youbike_realtime",
        cwd="/Users/andrew/Desktop/andrew/Data_engineer/Youbike",
        bash_command=".venv/bin/python -m src.extract.youbike --scrape_time '{{ data_interval_end }}'",
    )