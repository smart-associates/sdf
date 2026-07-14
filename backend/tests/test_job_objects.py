from app.services.job_objects import resolve_job_objects


def _row(**kw):
    base = {"schema_name": None, "object_name": None, "table_filter": None,
            "enabled": True, "position": 0}
    base.update(kw)
    return base


def test_literal_entries_resolve_with_schema():
    out = resolve_job_objects([
        _row(schema_name="public", object_name="users", position=0),
        _row(schema_name=None, object_name="orders", position=1),
    ])
    assert [(o.schema, o.name, o.entry) for o in out] == [
        ("public", "users", "public.users"),
        (None, "orders", "orders"),
    ]


def test_ordered_by_position():
    out = resolve_job_objects([
        _row(object_name="b", position=2),
        _row(object_name="a", position=1),
        _row(object_name="c", position=3),
    ])
    assert [o.name for o in out] == ["a", "b", "c"]


def test_disabled_rows_excluded():
    out = resolve_job_objects([
        _row(object_name="a", enabled=True),
        _row(object_name="b", enabled=False),
    ])
    assert [o.name for o in out] == ["a"]


def test_dedupe_keeps_first_occurrence():
    out = resolve_job_objects([
        _row(schema_name="public", object_name="users", table_filter="id > 1", position=0),
        _row(schema_name="public", object_name="users", table_filter="id > 999", position=1),
    ])
    assert len(out) == 1
    assert out[0].table_filter == "id > 1"


def test_per_object_filter_passthrough():
    out = resolve_job_objects([
        _row(object_name="users", table_filter="created_at > '2024-01-01'"),
        _row(object_name="orders"),
    ])
    assert out[0].table_filter == "created_at > '2024-01-01'"
    assert out[1].table_filter is None


def test_blank_object_names_skipped():
    out = resolve_job_objects([
        _row(object_name="  "),
        _row(object_name="real"),
    ])
    assert [o.name for o in out] == ["real"]
