"""
Cached helper methods for all operations that are called often
"""
from typing import Any, Dict, List, Optional

from dlt.common.json import json
from dlt.common.destination.utils import resolve_merge_strategy
from dlt.common.normalizers.naming import NamingConvention
from dlt.common.normalizers.typing import TRowIdType
from dlt.common.normalizers.utils import DLT_ID_LENGTH_BYTES
from dlt.common.schema import Schema
from dlt.common.schema.typing import C_DLT_ID, DLT_NAME_PREFIX
from dlt.common.schema.utils import (
    get_columns_names_with_prop,
    get_first_column_name_with_prop,
)
from dlt.common.utils import digest128b


def shorten_fragments(naming: NamingConvention, *idents: str) -> str:
    return naming.shorten_fragments(*idents)


def normalize_table_identifier(schema: Schema, naming: NamingConvention, table_name: str) -> str:
    if schema._normalizers_config.get("use_break_path_on_normalize", True):
        return naming.normalize_tables_path(table_name)
    else:
        return naming.normalize_table_identifier(table_name)


def normalize_identifier(schema: Schema, naming: NamingConvention, identifier: str) -> str:
    if schema._normalizers_config.get("use_break_path_on_normalize", True):
        return naming.normalize_path(identifier)
    else:
        return naming.normalize_identifier(identifier)


def get_primary_key(schema: Schema, table_name: str) -> List[str]:
    if table_name not in schema.tables:
        return []
    table = schema.get_table(table_name)
    pk = get_columns_names_with_prop(table, "primary_key", include_incomplete=True)
    return pk


def get_root_row_id_type(schema: Schema, table_name: str) -> TRowIdType:
    if table := schema.tables.get(table_name):
        merge_strategy = resolve_merge_strategy(schema.tables, table)
        if merge_strategy == "upsert":
            return "key_hash"
        elif merge_strategy == "scd2":
            x_row_version_col = get_first_column_name_with_prop(
                schema.get_table(table_name),
                "x-row-version",
                include_incomplete=True,
            )
            if x_row_version_col == schema.naming.normalize_identifier(C_DLT_ID):
                return "row_hash"
    return "random"


def get_row_hash(row: Dict[str, Any], subset: Optional[List[str]] = None) -> str:
    """Returns hash of row.

    Hash includes column names and values and is ordered by column name.
    Excludes dlt system columns.
    Can be used as deterministic row identifier.
    """
    if subset is not None:
        # all parts of the key must be present
        row_filtered = {k: row[k] for k in subset}
    else:
        row_filtered = {k: v for k, v in row.items() if not k.startswith(DLT_NAME_PREFIX)}
    row_str = json.dumpb(row_filtered, sort_keys=True)
    return digest128b(row_str, DLT_ID_LENGTH_BYTES)
