"""Unit tests for job_runner's table-failure metadata capture (issue #22)."""
from app.services.job_runner import _capture_failure_meta


def test_capture_failure_meta_includes_statement_from_direct_attribute():
    exc = ValueError("constraint violation")
    exc.statement = "INSERT INTO orders (id) VALUES (1)"
    meta = _capture_failure_meta(exc)
    assert meta["error"] == "constraint violation"
    assert meta["error_type"] == "ValueError"
    assert meta["sql"] == "INSERT INTO orders (id) VALUES (1)"


def test_capture_failure_meta_walks_cause_chain_for_statement():
    inner = ValueError("driver error")
    inner.statement = "CREATE TABLE orders (id INT)"
    try:
        try:
            raise inner
        except ValueError as e:
            raise RuntimeError("wrapped") from e
    except RuntimeError as outer:
        meta = _capture_failure_meta(outer)
    assert meta["error"] == "wrapped"
    assert meta["error_type"] == "RuntimeError"
    assert meta["sql"] == "CREATE TABLE orders (id INT)"


def test_capture_failure_meta_omits_sql_when_none_found():
    meta = _capture_failure_meta(ValueError("no statement here"))
    assert "sql" not in meta
    assert meta["error"] == "no statement here"


def test_capture_failure_meta_includes_traceback_tail_when_raised():
    try:
        raise ValueError("boom")
    except ValueError as e:
        meta = _capture_failure_meta(e)
    assert "traceback" in meta
    assert "ValueError" in meta["traceback"] or "raise ValueError" in meta["traceback"]


def test_capture_failure_meta_truncates_long_fields():
    exc = ValueError("x" * 2000)
    exc.statement = "y" * 5000
    meta = _capture_failure_meta(exc)
    assert len(meta["error"]) <= 1000
    assert len(meta["sql"]) <= 4000
