import contextlib
import io
from typing import ClassVar, List

from dlt.common.configuration.exceptions import DuplicateConfigProviderException
from dlt.common.configuration.providers import (
    ConfigProvider,
    ContextProvider,
)
from dlt.common.configuration.specs import (
    GcpServiceAccountCredentials,
    BaseConfiguration,
    configspec,
    known_sections,
)
from dlt.common.typing import Annotated


@configspec
class ConfigProvidersConfiguration(BaseConfiguration):
    enable_google_secrets: bool = False
    only_toml_fragments: bool = True

    # always look in providers
    __section__: ClassVar[str] = known_sections.PROVIDERS


class ConfigProvidersContainer:
    """Injectable list of providers used by the configuration `resolve` module"""

    providers: List[ConfigProvider] = None
    context_provider: ConfigProvider = None

    def __init__(self, initial_providers: List[ConfigProvider]) -> None:
        super().__init__()
        # add default providers
        self.providers = initial_providers
        # ContextProvider will provide contexts when embedded in configurations
        self.context_provider = ContextProvider()

    def add_extras(self) -> None:
        """Adds extra providers. Extra providers may use initial providers when setting up"""
        for provider in _extra_providers():
            self[provider.name] = provider

    def __getitem__(self, name: str) -> ConfigProvider:
        try:
            return next(p for p in self.providers if p.name == name)
        except StopIteration:
            raise KeyError(name)

    def __setitem__(self, name: str, provider: ConfigProvider) -> None:
        idx = next((i for i, p in enumerate(self.providers) if p.name == name), -1)
        if idx == -1:
            self.providers.append(provider)
        else:
            self.providers[idx] = provider

    def __contains__(self, name: object) -> bool:
        try:
            self.__getitem__(name)  # type: ignore
            return True
        except KeyError:
            return False

    def add_provider(self, provider: ConfigProvider) -> None:
        if provider.name in self:
            raise DuplicateConfigProviderException(provider.name)
        self.providers.append(provider)


def _extra_providers() -> List[ConfigProvider]:
    """Providers that require initial providers to be instantiated as the are enabled via config"""
    from dlt.common.configuration.resolve import resolve_configuration

    providers_config = resolve_configuration(ConfigProvidersConfiguration())
    extra_providers = []
    if providers_config.enable_google_secrets:
        extra_providers.append(
            _google_secrets_provider(only_toml_fragments=providers_config.only_toml_fragments)
        )
    return extra_providers


def _google_secrets_provider(
    only_secrets: bool = True, only_toml_fragments: bool = True
) -> ConfigProvider:
    from dlt.common.configuration.resolve import resolve_configuration
    from dlt.common.configuration.providers.google_secrets import GoogleSecretsProvider

    c = resolve_configuration(
        GcpServiceAccountCredentials(), sections=(known_sections.PROVIDERS, "google_secrets")
    )
    return GoogleSecretsProvider(
        c, only_secrets=only_secrets, only_toml_fragments=only_toml_fragments
    )
