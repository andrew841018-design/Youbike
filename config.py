import os
from pathlib import Path
from dotenv import dotenv_values
here = Path(__file__).resolve().parent
def get_env_variable(var_name):
    value = os.environ.get(var_name) or dotenv_values(here / ".env").get(var_name)
    if value is None:
        raise ValueError(f"Environment variable '{var_name}' is not set.")
    return value
