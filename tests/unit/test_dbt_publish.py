import pytest
from dotenv import dotenv_values
import os,subprocess
from config import here
from conftest import test_conn
import subprocess
@pytest.fixture
def fake_table(test_conn):
    test_conn.execute("drop schema if exists test_schema cascade")
    test_conn.execute("create schema test_schema")
    test_conn.execute("create table test_schema.response (like public.response)")
    test_conn.commit()
    yield test_conn
    test_conn.execute("drop schema test_schema cascade")
    test_conn.commit()

def run_dbt(action,*extra):
    ENV = {**os.environ, **dotenv_values(f"{here}/.env")}
    dbt = f"{here}/dbt/"
    target = "error_test"
    cmd = [f"{here}/.venv-dbt/bin/dbt", f"{action}","--target",target,"--project-dir", dbt, "--profiles-dir", dbt, *extra]
    return subprocess.run(cmd, capture_output=True, text=True, env=ENV)
def test_error_source(fake_table):
    conn = fake_table
    env = {** os.environ,** dotenv_values("Youbike/.env")}
    #build dbt
    check = conn.execute("select to_regclass(%s)",("test_dbt.mart_station_hourly",)).fetchone()
    if check[0] is None:# no mart
        result_1 = run_dbt("run")
        result_1 = run_dbt("build")
    else:
        result_1 = run_dbt("build")
    assert result_1.returncode == 0
    #record mart info before
    row = conn.execute("select count(*),max(last_ingested_at) from test_dbt.mart_station_hourly").fetchone()
    count,last_ingested_at = row
    conn.execute("alter table test_schema.response rename batch_id to batch_id_1")
    conn.commit()
    #build dbt
    result_2=run_dbt("build","--vars","{test_schema: test_schema}")
    assert result_2.returncode != 0
    assert 'column "batch_id" does not exist' in result_2.stdout

    #record mart info after
    row = conn.execute("select count(*),max(last_ingested_at) from test_dbt.mart_station_hourly").fetchone()
    count_after,last_ingested_at_after = row
    assert count == count_after and last_ingested_at== last_ingested_at_after

        



    