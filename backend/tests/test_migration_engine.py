import sqlalchemy as sa

from app.services.migration_engine import (
    create_target_table_from_file, table_exists,
    migrate_csv_to_db, migrate_db_to_csv,
    adaptive_batch_size, _sanitize_exc,
)


def test_sanitize_exc_preserves_statement_for_step_logs():
    """A DBAPI-style error carrying .statement must survive re-raising through
    _sanitize_exc so job_runner can surface the failing SQL (issue #22)."""
    @_sanitize_exc
    def boom():
        exc = ValueError("duplicate key value violates unique constraint")
        exc.statement = "INSERT INTO orders (id) VALUES (1)"
        raise exc

    try:
        boom()
        assert False, "expected an exception"
    except Exception as e:
        assert "duplicate key" in str(e)
        assert e.statement == "INSERT INTO orders (id) VALUES (1)"


def test_sanitize_exc_strips_nul_bytes_and_has_no_statement_when_absent():
    @_sanitize_exc
    def boom():
        raise ValueError("bad value \x00 here")

    try:
        boom()
        assert False, "expected an exception"
    except Exception as e:
        assert "\x00" not in str(e)
        assert getattr(e, "statement", None) is None


def test_adaptive_batch_size_scales_with_row_count():
    """Batch size is ~1% of the estimated rows, floored and capped (issue #14)."""
    assert adaptive_batch_size(None, 100_000) == 100_000  # unknown estimate -> ceiling
    assert adaptive_batch_size(0, 100_000) == 100_000
    assert adaptive_batch_size(500, 100_000) == 1000  # floor
    assert adaptive_batch_size(500_000, 100_000) == 5000  # 1% of 500k
    assert adaptive_batch_size(50_000_000, 100_000) == 100_000  # capped at ceiling


def test_create_target_table_from_csv_file(tmp_path):
    """A file->DB job with create_target_table enabled must not crash trying
    to reflect a (nonexistent) source engine (issue #11) — columns are
    derived from the file itself instead."""
    csv_path = tmp_path / "title.ratings.csv"
    csv_path.write_text(
        "id,rating,note\n"
        "1,4.5,short\n"
        "2,3.2,a bit longer note here\n"
        "3,,\n"
    )

    engine = sa.create_engine("sqlite://")
    create_target_table_from_file(
        engine, str(tmp_path), "title.ratings", "title.ratings", None, "csv",
    )

    assert table_exists(engine, "title.ratings")
    cols = {c["name"]: c["type"] for c in sa.inspect(engine).get_columns("title.ratings")}
    assert isinstance(cols["id"], (sa.Integer, sa.BigInteger))
    assert isinstance(cols["rating"], sa.Float)
    assert isinstance(cols["note"], sa.String)


def test_create_target_table_from_file_sizes_varchar_from_sample():
    from app.services.migration_engine import _infer_sa_type_from_strings

    short_values = ["ab", "cde", "f"]
    t = _infer_sa_type_from_strings(short_values)
    assert isinstance(t, sa.String)
    assert t.length >= max(len(v) for v in short_values)

    # Leading-zero identifiers must stay text, not get coerced to integer.
    t2 = _infer_sa_type_from_strings(["007", "042"])
    assert isinstance(t2, sa.Text)


def test_csv_null_value_round_trips_through_db(tmp_path):
    """A configured csv_null_value sentinel must read back as SQL NULL, and
    NULL values written to CSV must use that sentinel (issue #13)."""
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text("id,note\n1,\\N\n2,fine\n")

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE orders (id INTEGER, note VARCHAR(50))"))

    migrate_csv_to_db(str(tmp_path), engine, "orders", "orders", None,
                      "append", 1000, csv_null_value="\\N")

    with engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT id, note FROM orders ORDER BY id")).fetchall()
    assert rows == [(1, None), (2, "fine")]

    out_dir = tmp_path / "out"
    migrate_db_to_csv(engine, str(out_dir), "orders", "orders", None, None,
                      "append", batch_size=1000, csv_null_value="\\N")
    written = (out_dir / "orders.csv").read_text()
    assert "\\N" in written
    assert written.count("\n") == 3  # header + 2 rows


def test_csv_null_value_default_preserves_empty_string_behavior(tmp_path):
    """With the default blank csv_null_value, empty CSV fields must still
    insert as empty string, not NULL (no behavior change for existing jobs)."""
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text("id,note\n1,\n")

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE orders (id INTEGER, note VARCHAR(50))"))

    migrate_csv_to_db(str(tmp_path), engine, "orders", "orders", None, "append", 1000)

    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT note FROM orders WHERE id = 1")).fetchone()
    assert row.note == ""
