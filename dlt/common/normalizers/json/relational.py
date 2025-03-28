from functools import lru_cache, partial
from typing import (
    ClassVar,
    Dict,
    Type,
    cast,
)

from dlt.common.normalizers.exceptions import InvalidJsonNormalizer, NormalizerException
from dlt.common.normalizers.typing import TJSONNormalizer
from dlt.common.normalizers.utils import generate_dlt_id
from dlt.common.typing import DictStrAny, TDataItem
from dlt.common.schema import Schema
from dlt.common.schema.typing import (
    C_DLT_ID,
    C_DLT_LOAD_ID,
    TColumnName,
    TSimpleRegex,
)
from dlt.common.schema.utils import (
    column_name_validator,
)
from dlt.common.utils import update_dict_nested
from dlt.common.normalizers.json import (
    TNormalizedRowIterator,
    wrap_in_dict,
    DataItemNormalizer as DataItemNormalizerBase,
)
from dlt.common.normalizers.json.typing import RelationalNormalizerConfig
from dlt.common.normalizers.json import helpers as normalize_helpers
from dlt.common.normalizers.json.helpers import (
    get_row_hash,
)
from dlt.common.validation import validate_dict


class DataItemNormalizer(DataItemNormalizerBase[RelationalNormalizerConfig]):
    # known normalizer props
    C_VALUE = "value"
    """for lists of simple types"""

    # other constants
    RELATIONAL_CONFIG_TYPE: ClassVar[Type[RelationalNormalizerConfig]] = RelationalNormalizerConfig

    normalizer_config: RelationalNormalizerConfig

    def __init__(self, schema: Schema) -> None:
        """This item normalizer works with nested dictionaries. It flattens dictionaries and descends into lists.
        It yields row dictionaries at each nesting level."""
        self.schema = schema
        self.naming = schema.naming
        self._reset()

    def _reset(self) -> None:
        # normalize known normalizer column identifiers
        self.c_dlt_id: TColumnName = TColumnName(self.naming.normalize_identifier(C_DLT_ID))
        self.c_dlt_load_id: TColumnName = TColumnName(
            self.naming.normalize_identifier(C_DLT_LOAD_ID)
        )
        self.c_value: TColumnName = TColumnName(self.naming.normalize_identifier(self.C_VALUE))

        # normalize config

        self.normalizer_config = self.schema._normalizers_config["json"].get("config") or {}  # type: ignore[assignment]
        # create cached versions of helper functions
        self._get_root_row_id_type = lru_cache(maxsize=None)(
            partial(normalize_helpers.get_root_row_id_type, self.schema)
        )
        self._shorten_fragments = lru_cache(maxsize=None)(
            partial(normalize_helpers.shorten_fragments, self.naming)
        )
        self._normalize_table_identifier = lru_cache(maxsize=None)(
            partial(normalize_helpers.normalize_table_identifier, self.schema, self.naming)
        )
        self._normalize_identifier = lru_cache(maxsize=None)(
            partial(normalize_helpers.normalize_identifier, self.schema, self.naming)
        )
        self._get_primary_key = lru_cache(maxsize=None)(
            partial(normalize_helpers.get_primary_key, self.schema)
        )

    @staticmethod
    def _extend_row(extend: DictStrAny, row: DictStrAny) -> None:
        row.update(extend)

    def _add_row_id(
        self,
        table: str,
        dict_row: DictStrAny,
        flattened_row: DictStrAny,
    ) -> str:
        row_id_type = self._get_root_row_id_type(table)
        if row_id_type in ("key_hash", "row_hash"):
            subset = None
            if row_id_type == "key_hash":
                # primary key based hash must be performed on normalized names
                subset = self._get_primary_key(table)
                row_id = get_row_hash(flattened_row, subset=subset)
            else:
                # base hash on `dict_row` instead of `flattened_row`
                # so changes in nested tables lead to new row id
                row_id = get_row_hash(dict_row)
        else:
            row_id = generate_dlt_id()

        flattened_row[self.c_dlt_id] = row_id
        return row_id

    def _normalize_row(
            self,
            dict_row: DictStrAny,
            table_name: str,
    ) -> TNormalizedRowIterator:
        # normalize current row
        normalized_row: dict = {}
        for k, v in dict_row.items():
            if k.strip():
                norm_k = self._normalize_identifier(k)
            else:
                msg = "Found empty key during Normalization."
                raise NormalizerException(msg)

            if norm_k in normalized_row:
                msg = f"Found duplicate key '{norm_k}' in row during Normalization."
                raise NormalizerException(msg)

            normalized_row[norm_k] = v

        # infer record hash or leave existing primary key if present
        row_id = normalized_row.get(self.c_dlt_id, None)
        if not row_id:
            self._add_row_id(table_name, dict_row, normalized_row)

        # yield parent table first
        should_descend = yield (
            (table_name, None),
            normalized_row,
        )
        # TODO unsure whether still needed for nestless logic
        if should_descend is False:
            return

    def extend_schema(self) -> None:
        """Extends Schema with normalizer-specific hints and settings.

        This method is called by Schema when instance is created or restored from storage.
        """
        config = cast(
            RelationalNormalizerConfig,
            self.schema._normalizers_config["json"].get("config") or {},
        )
        DataItemNormalizer._validate_normalizer_config(self.schema, config)

        # add hints, do not compile.
        self.schema._merge_hints(
            {
                "not_null": [
                    TSimpleRegex(self.c_dlt_id),
                    TSimpleRegex(self.c_dlt_load_id),
                ],
                "unique": [TSimpleRegex(self.c_dlt_id)],
                "row_key": [TSimpleRegex(self.c_dlt_id)],
            },
            normalize_identifiers=False,  # already normalized
        )

    def remove_table(self, table_name: str) -> None:
        pass

    def normalize_data_item(
        self, item: TDataItem, load_id: str, table_name: str
    ) -> TNormalizedRowIterator:
        # wrap items that are not dictionaries in dictionary, otherwise they cannot be processed by the JSON normalizer
        if not isinstance(item, dict):
            item = wrap_in_dict(self.c_value, item)
        # we will extend event with all the fields necessary to load it as root row

        # identify load id if loaded data must be processed after loading incrementally
        item[self.c_dlt_load_id] = load_id
        # TODO do this before for all date items in chunk, save compute
        root_table_name = self._normalize_table_identifier(table_name)

        yield from self._normalize_row(
            item,
            root_table_name,
        )

    @classmethod
    def ensure_this_normalizer(cls, norm_config: TJSONNormalizer) -> None:
        # make sure schema has right normalizer
        present_normalizer = norm_config["module"]
        if present_normalizer != cls.__module__:
            raise InvalidJsonNormalizer(cls.__module__, present_normalizer)

    @classmethod
    def update_normalizer_config(cls, schema: Schema, config: RelationalNormalizerConfig) -> None:
        cls._validate_normalizer_config(schema, config)
        existing_config = schema._normalizers_config["json"]
        cls.ensure_this_normalizer(existing_config)
        if "config" in existing_config:
            update_dict_nested(existing_config["config"], config)  # type: ignore
        else:
            existing_config["config"] = config

    @classmethod
    def get_normalizer_config(cls, schema: Schema) -> RelationalNormalizerConfig:
        norm_config = schema._normalizers_config["json"]
        cls.ensure_this_normalizer(norm_config)
        return cast(RelationalNormalizerConfig, norm_config.get("config", {}))

    @classmethod
    def _validate_normalizer_config(
        cls, schema: Schema, config: RelationalNormalizerConfig
    ) -> None:
        """Normalizes all known column identifiers according to the schema and then validates the configuration"""
        validate_dict(
            cls.RELATIONAL_CONFIG_TYPE,
            config,
            "./normalizers/json/config",
            validator_f=column_name_validator(schema.naming),
        )
