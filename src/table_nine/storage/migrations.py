from __future__ import annotations

from copy import deepcopy
from typing import Any


CURRENT_SCHEMA_VERSION = 2


class SchemaMigrationError(ValueError):
    """Raised when a workbench document cannot be migrated safely."""


def migrate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(payload)
    version = migrated.get("table_nine_schema")
    if version is None:
        raise SchemaMigrationError("table_nine_schema is required")
    if not isinstance(version, int):
        raise SchemaMigrationError("table_nine_schema must be an integer")
    if version > CURRENT_SCHEMA_VERSION:
        raise SchemaMigrationError(
            f"schema {version} is newer than supported schema {CURRENT_SCHEMA_VERSION}"
        )
    if version == 1:
        migrated["table_nine_schema"] = 2
        migrated.setdefault("suggestions", [])
        version = 2
    if version < CURRENT_SCHEMA_VERSION:
        raise SchemaMigrationError(f"no migration path exists from schema {version}")
    return migrated
