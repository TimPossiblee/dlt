"""Measure the extract, normalize and load progress"""
from typing import Union, Literal

from dlt.common.runtime.collector import LogCollector as log
from dlt.common.runtime.collector import Collector as _Collector, NULL_COLLECTOR as _NULL_COLLECTOR

TSupportedCollectors = Literal["log"]
TCollectorArg = Union[_Collector, TSupportedCollectors]


def _from_name(collector: TCollectorArg) -> _Collector:
    """Create default collector by name"""
    if collector is None:
        return _NULL_COLLECTOR

    if isinstance(collector, str):
        if collector == "log":
            return log()
        raise ValueError(collector)
    return collector
