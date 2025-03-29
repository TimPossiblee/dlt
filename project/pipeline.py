import pendulum

import dlt
from dlt.common import Decimal

dlt.config["runtime.log_level"] = "INFO"
dlt.config["load.delete_completed_jobs"] = True


@dlt.resource(primary_key="id")
def customers():
    yield [
        {"id": 1, "name": "simon", "city": "berlin"},
        {"id": 2, "name": "violet", "city": "london"},
        {"id": 3, "name": "tammo", "city": "new york"},
    ]


@dlt.resource(primary_key="id")
def inventory():
    yield [
        {"id": 1, "name": "apple", "price": Decimal("1.50")},
        {"id": 2, "name": "banana", "price": Decimal("1.70")},
        {"id": 3, "name": "pear", "price": Decimal("2.50")},
    ]


@dlt.source
def fruitshop():
    return customers(), inventory()


fruitshop2 = fruitshop()
fruitshop2.resources.add(fruitshop2.resources["customers"].with_name("customers2"))
fruitshop2 = fruitshop2.with_resources("customers2")


@dlt.resource(write_disposition="append", name="all_datatypes")
def resource():
    yield [
        {
            "col1": 989127831,
            "col2": 898912.821982,
            "col3": True,
            "col4": "2022-05-23T13:26:45.176451+00:00",
            "col5": "string data \n \r  🦆",
            "col6": Decimal("2323.34"),
            "col7": b"binary data \n \r ",
            "col8": 2**56 + 92093890840,
            "col9": {
                "json": [1, 2, 3, "a"],
                "link": (
                    "?commen\ntU\nrn=urn%3Ali%3Acomment%3A%28acti\012 \6 \\vity%3A69'08444473\n\n551163392%2C6n \r 9085"
                ),
            },
            "col10": "2023-02-27",
            "col11": "13:26:45.176451",
        }
    ]


@dlt.source
def source_debug():
    return resource()


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
    pipeline_name="main_pipeline",
    pipelines_dir="./tmp/pipelines",
    destination=dlt.destinations.duckdb("files/data.db"),
    dataset_name="main_pipeline",
)
load_info = p.run([source_debug(), fruitshop(), fruitshop2, events()])

print(load_info)
