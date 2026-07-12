"""
db.py
One place to open a Snowflake connection. Credentials come from the
.env file (never hardcode them). Every script imports get_connection().
"""

import os
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()  # reads the .env file in the project root


def get_connection(schema: str = "RAW"):
    """
    Open a Snowflake connection to the SMART_CITY_AQI database.
    Pass schema="RAW" / "CLEAN" / "ANALYTICS" depending on the layer
    you are writing to.
    """
    return snowflake.connector.connect(
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        account=os.environ["SNOWFLAKE_ACCOUNT"],   # e.g. abcd-xy12345
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "SMART_CITY_AQI"),
        schema=schema,
    )
