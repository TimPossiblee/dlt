import yaml
from typing import Iterator, List, Mapping, Tuple, cast

from dlt.common import logger
from dlt.common.json import json
from dlt.common.configuration import with_config
from dlt.common.configuration.accessors import config
from dlt.common.schema.utils import get_processing_hints, to_pretty_json, to_pretty_yaml
from dlt.common.storages.configuration import (
    SchemaStorageConfiguration,
    TSchemaFileFormat,
    SchemaFileExtensions,
)
from dlt.common.storages.file_storage import FileStorage
from dlt.common.schema import Schema, verify_schema_hash
from dlt.common.typing import DictStrAny

from dlt.common.storages.exceptions import (
    InStorageSchemaModified,
    SchemaNotFoundError,
    UnexpectedSchemaName,
)


class SchemaStorage(Mapping[str, Schema]):
    SCHEMA_FILE_NAME = "schema.%s"
    NAMED_SCHEMA_FILE_PATTERN = f"%s.{SCHEMA_FILE_NAME}"

    @with_config(spec=SchemaStorageConfiguration, sections=("schema",))
    def __init__(
        self, config: SchemaStorageConfiguration = config.value, makedirs: bool = False
    ) -> None:
        self.config = config
        self.storage = FileStorage(config.schema_volume_path, makedirs=makedirs)

    def _load_schema_json(self, name: str) -> DictStrAny:
        schema_file = self._file_name_in_store(name, "json")
        return cast(DictStrAny, json.loads(self.storage.load(schema_file)))

    def load_schema(self, name: str) -> Schema:
        # loads a schema from a store holding many schemas
        storage_schema: DictStrAny = None
        try:
            storage_schema = self._load_schema_json(name)
            # prevent external modifications of schemas kept in storage
            if not verify_schema_hash(storage_schema, verifies_if_not_migrated=True):
                raise InStorageSchemaModified(name, self.config.schema_volume_path)
        except FileNotFoundError:
            # maybe we can import from external storage
            pass

        if storage_schema is None:
            raise SchemaNotFoundError(name, self.config.schema_volume_path)
        return Schema.from_dict(storage_schema, validate_schema=False)

    def save_schema(self, schema: Schema) -> str:
        """Saves schema to the storage and returns the path relative to storage."""
        return self._save_and_export_schema(schema)

    def remove_schema(self, name: str) -> None:
        schema_file = self._file_name_in_store(name, "json")
        self.storage.delete(schema_file)

    def has_schema(self, name: str) -> bool:
        schema_file = self._file_name_in_store(name, "json")
        return self.storage.has_file(schema_file)

    def list_schemas(self) -> List[str]:
        files = self.storage.list_folder_files(".", to_root=False)
        # extract names
        return [f.split(".")[0] for f in files]

    def clear_storage(self) -> None:
        for schema_name in self.list_schemas():
            self.remove_schema(schema_name)

    def __getitem__(self, name: str) -> Schema:
        return self.load_schema(name)

    def __len__(self) -> int:
        return len(self.list_schemas())

    def __iter__(self) -> Iterator[str]:
        for name in self.list_schemas():
            yield name

    def __contains__(self, name: str) -> bool:  # type: ignore
        return name in self.list_schemas()

    def _save_schema(self, schema: Schema) -> str:
        """Saves schema to schema store and bumps the version"""
        schema_file = self._file_name_in_store(schema.name, "json")
        stored_schema = schema.to_dict()
        saved_path = self.storage.save(schema_file, to_pretty_json(stored_schema))
        # this should be the only place where this function is called. we bump a version and
        # clean modified status
        schema._bump_version()
        return saved_path

    def _save_and_export_schema(self, schema: Schema, check_processing_hints: bool = False) -> str:
        """Save schema to schema store."""
        saved_path = self._save_schema(schema)
        # if any processing hints are found we should warn the user
        if check_processing_hints and (processing_hints := get_processing_hints(schema.tables)):
            msg = (
                f"Imported schema {schema.name} contains processing hints for some tables."
                " Processing hints are used by normalizer (x-normalizer) to mark tables that got"
                " materialized and that prevents destructive changes to the schema. In most cases"
                " import schema should not contain processing hints because it is mostly used to"
                " initialize tables in a new dataset. "
            )
            msg += "Affected tables are: " + ", ".join(processing_hints.keys())
            logger.warning(msg)
        return saved_path

    @staticmethod
    def load_schema_file(
        path: str,
        name: str,
        extensions: Tuple[TSchemaFileFormat, ...] = SchemaFileExtensions,
        remove_processing_hints: bool = False,
    ) -> Schema:
        storage = FileStorage(path)
        for extension in extensions:
            file = SchemaStorage._file_name_in_store(name, extension)
            if storage.has_file(file):
                parsed_schema = SchemaStorage._parse_schema_str(storage.load(file), extension)
                schema = Schema.from_dict(
                    parsed_schema, remove_processing_hints=remove_processing_hints
                )
                if schema.name != name:
                    raise UnexpectedSchemaName(name, path, schema.name)
                return schema
        raise SchemaNotFoundError(name, path)

    @staticmethod
    def _parse_schema_str(schema_str: str, extension: TSchemaFileFormat) -> DictStrAny:
        if extension == "json":
            imported_schema: DictStrAny = json.loads(schema_str)
        elif extension == "yaml":
            imported_schema = yaml.safe_load(schema_str)
        else:
            raise ValueError(extension)
        return imported_schema

    @staticmethod
    def _file_name_in_store(name: str, fmt: TSchemaFileFormat) -> str:
        if name:
            return SchemaStorage.NAMED_SCHEMA_FILE_PATTERN % (name, fmt)
        else:
            return SchemaStorage.SCHEMA_FILE_NAME % fmt
