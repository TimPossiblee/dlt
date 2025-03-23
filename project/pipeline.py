import dlt


@dlt.resource(
    columns={"event_tstamp": {"data_type": "timestamp", "timezone": False}},
    primary_key="event_id",
)
def events():
    yield [{"event_id": 1, "event_tstamp": "2024-07-30T10:00:00.123+00:00"}]


p = dlt.pipeline(
    pipeline_name="chess",
    destination=dlt.destinations.duckdb("files/data.db"),
    dataset_name="chess_data",
)
p.run(events(), schema_contract={"tables": "evolve", "columns": "evolve", "data_type": "evolve"})
