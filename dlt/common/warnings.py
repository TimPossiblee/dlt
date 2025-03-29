import functools
import warnings
import semver
import typing
from typing_extensions import deprecated as _deprecated

from dlt.version import __version__

VersionString = typing.Union[str, semver.Version]


class DltDeprecationWarning(DeprecationWarning):
    """A dlt specific deprecation warning.

    This warning is raised when using deprecated functionality in dlt. It provides information on when the
    deprecation was introduced and the expected version in which the corresponding functionality will be removed.

    Attributes:
        message: Description of the warning.
        since: Version in which the deprecation was introduced.
        expected_due: Version in which the corresponding functionality is expected to be removed.
    """

    def __init__(
        self,
        message: str,
        *args: typing.Any,
        since: VersionString,
        expected_due: VersionString = None,
    ) -> None:
        super().__init__(message, *args)
        self.message = message.rstrip(".")
        self.since = since if isinstance(since, semver.Version) else semver.Version.parse(since)
        if expected_due:
            expected_due = (
                expected_due
                if isinstance(expected_due, semver.Version)
                else semver.Version.parse(expected_due)
            )
        # we deprecate across major version since 1.0.0
        self.expected_due = expected_due if expected_due is not None else self.since.bump_major()

    def __str__(self) -> str:
        message = (
            f"{self.message}. Deprecated in dlt {self.since} to be removed in {self.expected_due}."
        )
        return message


class Dlt04DeprecationWarning(DltDeprecationWarning):
    V04 = semver.Version.parse("0.4.0")

    def __init__(self, message: str, *args: typing.Any, expected_due: VersionString = None) -> None:
        super().__init__(
            message, *args, since=Dlt04DeprecationWarning.V04, expected_due=expected_due
        )


class Dlt100DeprecationWarning(DltDeprecationWarning):
    V100 = semver.Version.parse("1.0.0")

    def __init__(self, message: str, *args: typing.Any, expected_due: VersionString = None) -> None:
        super().__init__(
            message, *args, since=Dlt100DeprecationWarning.V100, expected_due=expected_due
        )


# show dlt deprecations once
warnings.simplefilter("once", DltDeprecationWarning)

deprecated = _deprecated
