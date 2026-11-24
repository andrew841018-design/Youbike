from datetime import datetime as DateTime,timezone
from airflow.sdk import DAG
from pathlib import Path
youbike_root = Path(__file__).resolve().parents[1]

from airflow.providers.standard.operators.bash import BashOperator
with DAG(
    dag_id="youbike_monthly_dag",
    schedule="15 07 1 * *",
    start_date=DateTime(2023, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
) as dag:
    BashOperator(
        task_id="dbt_test_monthly",
        bash_command=(
            f"set -a; . {youbike_root}/.env; set +a; "
            f"{youbike_root}/.venv-dbt/bin/dbt test --select tag:monthly --target production "
            f"--project-dir {youbike_root}/dbt --profiles-dir {youbike_root}/dbt"
        )
    )