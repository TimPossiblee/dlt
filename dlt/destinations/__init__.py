from dlt.destinations.impl.destination.factory import destination
from dlt.destinations.impl.duckdb.factory import duckdb
from dlt.destinations.impl.dummy.factory import dummy
from dlt.destinations.impl.snowflake.factory import snowflake

__all__ = [
    "destination",
    "duckdb",
    "dummy",
    "snowflake",
]
