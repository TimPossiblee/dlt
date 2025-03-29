from typing import Optional, Tuple

from dlt.common.schema.typing import TAnySchemaColumns, TSchemaContract
from dlt.extract.items import TTableHintTemplate
from dlt.extract.items_transform import ValidateItem


def create_item_validator(
    columns: TTableHintTemplate[TAnySchemaColumns],
    schema_contract: TTableHintTemplate[TSchemaContract] = None,
) -> Tuple[Optional[ValidateItem], TTableHintTemplate[TSchemaContract]]:
    """Creates item validator for a `columns` definition and a `schema_contract`

    Returns a tuple (validator, schema contract). If validator could not be created, returns None at first position.
    If schema_contract was not specified a default schema contract for given validator will be returned
    """
    return None, schema_contract
