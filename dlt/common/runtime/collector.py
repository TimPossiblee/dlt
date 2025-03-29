import os
import sys
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import (
    Any,
    ContextManager,
    Dict,
    Type,
    TYPE_CHECKING,
    DefaultDict,
    NamedTuple,
    Optional,
    Union,
    TextIO,
    TypeVar,
)

from dlt.common import logger as dlt_logger
from dlt.common.exceptions import MissingDependencyException

TCollector = TypeVar("TCollector", bound="Collector")


class Collector(ABC):
    step: str

    @abstractmethod
    def update(
        self,
        name: str,
        inc: int = 1,
        total: int = None,
        inc_total: int = None,
        message: str = None,
        label: str = None,
    ) -> None:
        """Creates or updates a counter

        This function updates a counter `name` with a value `inc`. If counter does not exist, it is created with optional total value of `total`.
        Depending on implementation `label` may be used to create nested counters and message to display additional information associated with a counter.

        Args:
            name (str): An unique name of a counter, displayable.
            inc (int, optional): Increase amount. Defaults to 1.
            total (int, optional): Maximum value of a counter. Defaults to None which means unbound counter.
            icn_total (int, optional): Increase the maximum value of the counter, does nothing if counter does not exit yet
            message (str, optional): Additional message attached to a counter. Defaults to None.
            label (str, optional): Creates nested counter for counter `name`. Defaults to None.
        """
        pass

    @abstractmethod
    def _start(self, step: str) -> None:
        """Starts counting for a processing step with name `step`"""
        pass

    @abstractmethod
    def _stop(self) -> None:
        """Stops counting. Should close all counters and release resources ie. screen or push the results to a server."""
        pass

    def __call__(self: TCollector, step: str) -> TCollector:
        """Syntactic sugar for nicer context managers"""
        self.step = step
        return self

    def __enter__(self: TCollector) -> TCollector:
        self._start(self.step)
        return self

    def __exit__(self, exc_type: Type[BaseException], exc_val: BaseException, exc_tb: Any) -> None:
        self._stop()


class NullCollector(Collector):
    """A default counter that does not count anything."""

    def update(
        self,
        name: str,
        inc: int = 1,
        total: int = None,
        inc_total: int = None,
        message: str = None,
        label: str = None,
    ) -> None:
        pass

    def _start(self, step: str) -> None:
        pass

    def _stop(self) -> None:
        pass


class DictCollector(Collector):
    """A collector that just counts"""

    def __init__(self) -> None:
        self.counters: DefaultDict[str, int] = None

    def update(
        self,
        name: str,
        inc: int = 1,
        total: int = None,
        inc_total: int = None,
        message: str = None,
        label: str = None,
    ) -> None:
        assert not label, "labels not supported in dict collector"
        self.counters[name] += inc

    def _start(self, step: str) -> None:
        self.counters = defaultdict(int)

    def _stop(self) -> None:
        self.counters = None


class LogCollector(Collector):
    """A Collector that shows progress by writing to a Python logger or a console"""

    logger: Union[logging.Logger, TextIO]
    log_level: int

    class CounterInfo(NamedTuple):
        description: str
        start_time: float
        total: Optional[int]

    def __init__(
        self,
        log_period: float = 1.0,
        logger: Union[logging.Logger, TextIO] = sys.stdout,
        log_level: int = logging.INFO,
        dump_system_stats: bool = True,
    ) -> None:
        """
        Collector writing to a `logger` every `log_period` seconds. The logger can be a Python logger instance, text stream, or None that will attach `dlt` logger

        Args:
            log_period (float, optional): Time period in seconds between log updates. Defaults to 1.0.
            logger (logging.Logger | TextIO, optional): Logger or text stream to write log messages to. Defaults to stdio.
            log_level (str, optional): Log level for the logger. Defaults to INFO level
            dump_system_stats (bool, optional): Log memory and cpu usage. Defaults to True
        """
        self.log_period = log_period
        self.logger = logger
        self.log_level = log_level
        self.counters: DefaultDict[str, int] = None
        self.counter_info: Dict[str, LogCollector.CounterInfo] = None
        self.messages: Dict[str, Optional[str]] = None
        if dump_system_stats:
            try:
                import psutil
            except ImportError:
                self._log(
                    logging.WARNING,
                    "psutil dependency is not installed and mem stats will not be available. add"
                    " psutil to your environment or pass dump_system_stats argument as False to"
                    " disable warning.",
                )
                dump_system_stats = False
        self.dump_system_stats = dump_system_stats
        self.last_log_time: float = None

    def update(
        self,
        name: str,
        inc: int = 1,
        total: int = None,
        inc_total: int = None,
        message: str = None,
        label: str = None,
    ) -> None:
        counter_key = f"{name}_{label}" if label else name

        if counter_key not in self.counters:
            self.counters[counter_key] = 0
            self.counter_info[counter_key] = LogCollector.CounterInfo(
                description=f"{name} ({label})" if label else name,
                start_time=time.time(),
                total=total,
            )
            self.messages[counter_key] = None
            self.last_log_time = None
        else:
            counter_info = self.counter_info[counter_key]
            if inc_total:
                self.counter_info[counter_key] = LogCollector.CounterInfo(
                    description=counter_info.description,
                    start_time=counter_info.start_time,
                    total=counter_info.total + inc_total,
                )

        self.counters[counter_key] += inc
        if message is not None:
            self.messages[counter_key] = message
        self.maybe_log()

    def maybe_log(self) -> None:
        current_time = time.time()
        if self.last_log_time is None or current_time - self.last_log_time >= self.log_period:
            self.dump_counters()
            self.last_log_time = current_time

    def dump_counters(self) -> None:
        current_time = time.time()
        log_lines = []

        step_header = f" {self.step} ".center(80, "-")
        log_lines.append(step_header)

        for name, count in self.counters.items():
            info = self.counter_info[name]
            elapsed_time = current_time - info.start_time
            items_per_second = (count / elapsed_time) if elapsed_time > 0 else 0

            progress = f"{count}/{info.total}" if info.total else f"{count}"
            percentage = f"({count / info.total * 100:.1f}%)" if info.total else ""
            elapsed_time_str = f"{elapsed_time:.2f}s"
            items_per_second_str = f"{items_per_second:.2f}/s"
            message = f"[{self.messages[name]}]" if self.messages[name] is not None else ""

            counter_line = (
                f"{info.description}: {progress} {percentage} | Time: {elapsed_time_str} | Rate:"
                f" {items_per_second_str} {message}"
            )
            log_lines.append(counter_line.strip())

        if self.dump_system_stats:
            import psutil

            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            current_mem = mem_info.rss / (1024**2)  # Convert to MB
            mem_percent = psutil.virtual_memory().percent
            cpu_percent = process.cpu_percent()
            log_lines.append(
                f"Memory usage: {current_mem:.2f} MB ({mem_percent:.2f}%) | CPU usage:"
                f" {cpu_percent:.2f}%"
            )

        log_lines.append("")
        log_message = "\n".join(log_lines)
        if not self.logger:
            # try to attach dlt logger
            self.logger = dlt_logger.LOGGER
        self._log(self.log_level, log_message)

    def _log(self, log_level: int, log_message: str) -> None:
        if isinstance(self.logger, (logging.Logger, logging.LoggerAdapter)):
            self.logger.log(log_level, log_message)
        else:
            print(log_message, file=self.logger or sys.stdout)  # noqa

    def _start(self, step: str) -> None:
        self.counters = defaultdict(int)
        self.counter_info = {}
        self.messages = {}
        self.last_log_time = time.time()

    def _stop(self) -> None:
        self.dump_counters()
        self.counters = None
        self.counter_info = None
        self.messages = None
        self.last_log_time = None


NULL_COLLECTOR = NullCollector()
