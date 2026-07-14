"""Resolve a job's effective list of source objects.

Single source of truth for "which objects does a job replicate", replacing the
old newline-separated ``jobs.source_tables`` text column and job-wide
``table_filter``. Consumed by both the job runner and the jobs router so they
agree on the same set.

Community edition is literal-only and include-only: each ``job_tables`` row names
one object (``schema_name`` + ``object_name``) and carries its own optional WHERE
filter. There are no glob patterns and no catalog browsing (those remain Pro).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ResolvedObject:
    schema: Optional[str]
    name: str
    entry: str                      # canonical "schema.name" or "name"
    table_filter: Optional[str]     # per-object WHERE clause, or None


def _entry_of(schema: Optional[str], name: str) -> str:
    return f"{schema}.{name}" if schema else name


def resolve_job_objects(rows: list[dict]) -> list[ResolvedObject]:
    """Resolve a job's effective object list from its job_tables rows.

    ``rows`` is a list of dicts with keys: schema_name, object_name,
    table_filter, enabled, position. Enabled rows are returned ordered by
    ``position``, deduped by canonical entry (first occurrence wins).
    """
    enabled = [r for r in rows if r.get("enabled", True)]
    enabled.sort(key=lambda r: (r.get("position") or 0))

    resolved: list[ResolvedObject] = []
    seen: set[str] = set()
    for r in enabled:
        name = (r.get("object_name") or "").strip()
        if not name:
            continue
        schema = r.get("schema_name") or None
        entry = _entry_of(schema, name)
        key = entry.lower()
        if key in seen:
            continue
        seen.add(key)
        resolved.append(ResolvedObject(
            schema=schema,
            name=name,
            entry=entry,
            table_filter=r.get("table_filter") or None,
        ))
    return resolved
