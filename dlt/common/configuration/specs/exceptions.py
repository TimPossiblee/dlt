from typing import Any, Type
from dlt.common.configuration.exceptions import ConfigurationException


class SpecException(ConfigurationException):
    pass


class OAuth2ScopesRequired(SpecException):
    def __init__(self, spec: type) -> None:
        self.spec = spec
        super().__init__(
            "Scopes are required to retrieve refresh_token. Use 'openid' scope for a token without"
            " any permissions to resources."
        )


class NativeValueError(SpecException, ValueError):
    def __init__(self, spec: Type[Any], native_value: str, msg: str) -> None:
        self.spec = spec
        self.native_value = native_value
        super().__init__(msg)


class InvalidConnectionString(NativeValueError):
    def __init__(self, spec: Type[Any], native_value: str, driver: str):
        driver = driver or "driver"
        msg = (
            f"The expected representation for {spec.__name__} is a standard database connection"
            f" string with the following format: {driver}://username:password@host:port/database."
        )
        super().__init__(spec, native_value, msg)


class ObjectStoreRsCredentialsException(ConfigurationException):
    pass


class UnsupportedAuthenticationMethodException(ConfigurationException):
    pass
