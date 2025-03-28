import pendulum

import dlt

dlt.config["runtime.log_level"] = "INFO"
dlt.config["load.delete_completed_jobs"] = True

@dlt.resource(
    columns={"event_tstamp": {"data_type": "timestamp", "timezone": False}},
    primary_key="event_id",
)
def events():
    yield [
        {
            "event_id": 1,
            "EventMessage": "hello world!",
            "EventData": {"StatusCode": 1337},
            "EventList": [1, 3, 3, 7],
            "event_tstamp": pendulum.now(),
        },
        {
            "event_id": 2,
            "EventMessage": "hello world!",
            "EventData": {"StatusCode": 1337},
            "EventList": [1, 3, 3, 7],
            "event_tstamp": pendulum.now(),
        },
    ]
    yield [
        {
            "event_id": 3,
            "EventMessage": "hello world!",
            "EventData": {"StatusCode": 1337},
            "EventList": [1, 3, 3, 7],
            "event_tstamp": pendulum.now(),
        },
        {
            "event_id": 4,
            "EventMessage": "hello world!",
            "EventData": {"StatusCode": 1337},
            "EventList": [1, 3, 3, 7],
            "event_tstamp": pendulum.now(),
        },
    ]


p = dlt.pipeline(
    pipeline_name="chess",
    pipelines_dir="./tmp/pipelines",
    destination=dlt.destinations.duckdb("files/data.db"),
    dataset_name="chess_data",
)
p.run(events())
