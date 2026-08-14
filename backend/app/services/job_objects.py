"""Resolve a job's effective list of source objects.

Single source of truth for "which objects does a job replicate", replacing the
old newline-separated ``jobs.source_tables`` text column and job-wide
``table_filter``. Consumed by both the job runner and the jobs router so they
agree on the same set.

Community edition is literal-only and include-only: each ``job_tables`` row names
one object (``schema_name`` + ``object_name``) and carries its own optional WHERE
filter. There are no glob patterns (those remain Pro).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class ResolvedObject:
    schema: Optional[str]
    name: str
    entry: str                      # canonical "schema.name" or "name"
    table_filter: Optional[str]     # per-object WHERE clause, or None


def entry_of(schema: Optional[str], name: str) -> str:
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
        entry = entry_of(schema, name)
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


def qualify_rows(
    rows: list[dict],
    *,
    list_schemas: Callable[[], list[str]],
    list_objects: Callable[[Optional[str]], list[dict]],
) -> list[dict]:
    """Suggest schema-qualified/canonical forms for a job's manual entries.

    A bare entry (no schema_name) whose object_name resolves to exactly one
    object across all schemas is qualified with that schema; an entry that
    already names a schema is case-corrected to the catalog's canonical
    schema/name if they differ. Ambiguous bare names (matching in more than
    one schema) are left alone. The whole-catalog scan only runs when there's
    at least one non-blank entry to qualify.

    Returns ``[{"original", "schema_name", "object_name"}, ...]`` for the
    entries that actually change — ``original`` is the entry as currently
    typed, for the caller to match back against its own rows.
    """
    entries = [r for r in rows if (r.get("object_name") or "").strip()]
    if not entries:
        return []

    by_name: dict[str, dict] = {}   # lower name -> {(schema, name): None}
    by_ref: dict[str, tuple] = {}   # lower "schema.name" -> (schema, name)
    for schema in list_schemas():
        for o in list_objects(schema):
            nm = o.get("name")
            if not nm:
                continue
            sch = o.get("schema") or schema
            by_name.setdefault(nm.lower(), {})[(sch, nm)] = None
            by_ref[f"{sch}.{nm}".lower()] = (sch, nm)

    out: list[dict] = []
    for r in entries:
        name = (r.get("object_name") or "").strip()
        schema = r.get("schema_name") or None
        original = entry_of(schema, name)
        if schema:
            hit = by_ref.get(f"{schema}.{name}".lower())
            if hit and (hit[0] != schema or hit[1] != name):
                out.append({"original": original, "schema_name": hit[0], "object_name": hit[1]})
        else:
            cands = by_name.get(name.lower(), {})
            if len(cands) == 1:
                sch, nm = next(iter(cands))
                out.append({"original": original, "schema_name": sch, "object_name": nm})
    return out
