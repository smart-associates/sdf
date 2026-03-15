"""Core migration engine: copies tables from source to target DB."""
import csv
import os
import sqlalchemy as sa
from sqlalchemy import inspect, text, MetaData, Table, Column
from sqlalchemy import String, Text, Integer, BigInteger, Float, Numeric, Boolean, Date, DateTime
from sqlalchemy.engine import Engine, URL
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)

_DRIVERS = {
    "postgresql": "postgresql+psycopg2",
    "mysql": "mysql+pymysql",
    "mssql": "mssql+pymssql",
}
_DEFAULT_PORTS = {"postgresql": 5432, "mysql": 3306, "mssql": 1433}

# Forbidden patterns in user-supplied WHERE clauses
_FILTER_FORBIDDEN = [";", "--", "/*", "*/", "xp_", "exec ", "execute "]


def _quote_ident(name: str) -> str:
    """Double-quote an SQL identifier, escaping embedded double quotes."""
    return '"' + name.replace('"', '""') + '"'


def _full_table(schema: Optional[str], table: str) -> str:
    if schema:
        return f"{_quote_ident(schema)}.{_quote_ident(table)}"
    return _quote_ident(table)


def _validate_filter(table_filter: str) -> str:
    """Reject obviously dangerous patterns in a user-supplied WHERE clause."""
    lower = table_filter.lower()
    for tok in _FILTER_FORBIDDEN:
        if tok in lower:
            raise ValueError(f"table_filter contains forbidden pattern: {tok!r}")
    return table_filter


def build_engine(db_type: str, host: str, port: int, database: str, username: str, password: str) -> Engine:
    if db_type not in _DRIVERS:
        raise ValueError(f"Unsupported db_type: {db_type}")
    port = port or _DEFAULT_PORTS.get(db_type, 5432)
    url = URL.create(_DRIVERS[db_type], username=username, password=password,
                     host=host, port=port, database=database)
    return sa.create_engine(url, pool_pre_ping=True)


def to_generic_type(col_type) -> sa.types.TypeEngine:
    type_str = str(col_type).upper()
    if "BIGINT" in type_str:
        return BigInteger()
    if "INT" in type_str:
        return Integer()
    if "BOOL" in type_str or "BIT" in type_str:
        return Boolean()
    if "DOUBLE" in type_str or "FLOAT" in type_str or "REAL" in type_str:
        return Float()
    if "NUMERIC" in type_str or "DECIMAL" in type_str or "MONEY" in type_str:
        p = getattr(col_type, "precision", 18)
        s = getattr(col_type, "scale", 4)
        return Numeric(precision=p, scale=s)
    if "TIMESTAMP" in type_str or "DATETIME" in type_str:
        return DateTime()
    if "DATE" in type_str:
        return Date()
    if "TEXT" in type_str or "CLOB" in type_str or "NTEXT" in type_str:
        return Text()
    if "CHAR" in type_str or "VARCHAR" in type_str or "NVARCHAR" in type_str:
        length = getattr(col_type, "length", None) or 255
        if length == -1 or length > 8000:
            return Text()
        return String(length)
    return Text()


def get_table_names(engine: Engine, schema: Optional[str] = None) -> list[str]:
    insp = inspect(engine)
    return insp.get_table_names(schema=schema)


def reflect_table(engine: Engine, table_name: str, schema: Optional[str] = None) -> Table:
    meta = MetaData()
    return Table(table_name, meta, autoload_with=engine, schema=schema)


def create_target_table(src_engine: Engine, tgt_engine: Engine,
                         src_table: str, tgt_table: str,
                         src_schema: Optional[str], tgt_schema: Optional[str]):
    """Reflect source table, map types, create on target."""
    src = reflect_table(src_engine, src_table, src_schema)
    tgt_meta = MetaData()
    cols = []
    for col in src.columns:
        cols.append(Column(col.name, to_generic_type(col.type), nullable=col.nullable))
    tgt = Table(tgt_table, tgt_meta, *cols, schema=tgt_schema)
    tgt_meta.create_all(tgt_engine)


def table_exists(engine: Engine, table_name: str, schema: Optional[str] = None) -> bool:
    insp = inspect(engine)
    return insp.has_table(table_name, schema=schema)


def migrate_table(
    src_engine: Engine,
    tgt_engine: Engine,
    src_table: str,
    tgt_table: str,
    src_schema: Optional[str],
    tgt_schema: Optional[str],
    table_filter: Optional[str],
    migration_mode: str,
    batch_size: int,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> int:
    """Migrate one table. Returns total record count."""
    src_full = _full_table(src_schema, src_table)
    tgt_full = _full_table(tgt_schema, tgt_table)

    query = f"SELECT * FROM {src_full}"
    if table_filter:
        query += f" WHERE {_validate_filter(table_filter)}"

    if migration_mode == "truncate_load":
        with tgt_engine.begin() as tgt_conn:
            tgt_conn.execute(text(f"TRUNCATE TABLE {tgt_full}"))

    total = 0
    with src_engine.connect() as src_conn:
        result = src_conn.execution_options(stream_results=True).execute(text(query))
        cols = list(result.keys())

        batch = []
        for row in result:
            batch.append(dict(zip(cols, row)))
            if len(batch) >= batch_size:
                _insert_batch(tgt_engine, tgt_schema, tgt_table, cols, batch)
                total += len(batch)
                if progress_cb:
                    progress_cb(total)
                batch = []

        if batch:
            _insert_batch(tgt_engine, tgt_schema, tgt_table, cols, batch)
            total += len(batch)
            if progress_cb:
                progress_cb(total)

    return total


def _insert_batch(engine: Engine, tgt_schema: Optional[str], tgt_table: str,
                  cols: list[str], rows: list[dict]):
    tgt_full = _full_table(tgt_schema, tgt_table)
    col_idents = ", ".join(_quote_ident(c) for c in cols)
    # Use indexed placeholders to avoid issues with special chars in column names
    placeholders = ", ".join(f":p{i}" for i in range(len(cols)))
    sql = text(f"INSERT INTO {tgt_full} ({col_idents}) VALUES ({placeholders})")
    mapped = [{f"p{i}": row[c] for i, c in enumerate(cols)} for row in rows]
    with engine.begin() as conn:
        conn.execute(sql, mapped)


# ---------------------------------------------------------------------------
# Parquet helpers
# ---------------------------------------------------------------------------

def _parquet_path(directory: str, table: str) -> str:
    return os.path.join(directory, f"{table}.parquet")


def parquet_table_exists(directory: str, table: str) -> bool:
    return os.path.isfile(_parquet_path(directory, table))


def migrate_parquet_to_db(
    src_dir: str,
    tgt_engine: Engine,
    src_table: str,
    tgt_table: str,
    tgt_schema: Optional[str],
    migration_mode: str,
    batch_size: int,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> int:
    """Read a Parquet file and insert rows into a target DB table."""
    import pyarrow.parquet as pq

    path = _parquet_path(src_dir, src_table)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Parquet file not found: {path}")

    tgt_full = _full_table(tgt_schema, tgt_table)
    if migration_mode == "truncate_load":
        with tgt_engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {tgt_full}"))

    pf = pq.ParquetFile(path)
    cols = pf.schema_arrow.names
    total = 0
    for batch in pf.iter_batches(batch_size=batch_size):
        rows = batch.to_pydict()
        # Convert column-oriented dict to list of row dicts
        n = len(next(iter(rows.values())))
        row_list = [{c: rows[c][i] for c in cols} for i in range(n)]
        _insert_batch(tgt_engine, tgt_schema, tgt_table, cols, row_list)
        total += len(row_list)
        if progress_cb:
            progress_cb(total)
    return total


def migrate_db_to_parquet(
    src_engine: Engine,
    tgt_dir: str,
    src_table: str,
    tgt_table: str,
    src_schema: Optional[str],
    table_filter: Optional[str],
    migration_mode: str,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> int:
    """Stream rows from a source DB table and write to a Parquet file."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    src_full = _full_table(src_schema, src_table)
    query = f"SELECT * FROM {src_full}"
    if table_filter:
        query += f" WHERE {_validate_filter(table_filter)}"

    os.makedirs(tgt_dir, exist_ok=True)
    path = _parquet_path(tgt_dir, tgt_table)

    total = 0
    writer = None
    try:
        with src_engine.connect() as src_conn:
            result = src_conn.execution_options(stream_results=True).execute(text(query))
            cols = list(result.keys())
            batch: list[dict] = []
            for row in result:
                batch.append(dict(zip(cols, row)))
                if len(batch) >= 10000:
                    table_chunk = pa.Table.from_pylist(batch, schema=_infer_pa_schema(batch, cols))
                    if writer is None:
                        writer = pq.ParquetWriter(path, table_chunk.schema)
                    writer.write_table(table_chunk)
                    total += len(batch)
                    if progress_cb:
                        progress_cb(total)
                    batch = []
            if batch:
                table_chunk = pa.Table.from_pylist(batch)
                if writer is None:
                    writer = pq.ParquetWriter(path, table_chunk.schema)
                writer.write_table(table_chunk)
                total += len(batch)
                if progress_cb:
                    progress_cb(total)
    finally:
        if writer:
            writer.close()
    return total


def migrate_parquet_to_parquet(
    src_dir: str,
    tgt_dir: str,
    src_table: str,
    tgt_table: str,
    migration_mode: str,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> int:
    """Copy a Parquet file to another directory, optionally appending."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    src_path = _parquet_path(src_dir, src_table)
    if not os.path.isfile(src_path):
        raise FileNotFoundError(f"Parquet file not found: {src_path}")

    os.makedirs(tgt_dir, exist_ok=True)
    tgt_path = _parquet_path(tgt_dir, tgt_table)

    src_file = pq.ParquetFile(src_path)
    writer = None
    total = 0
    try:
        # When appending, carry over existing rows first
        if migration_mode == "append" and os.path.isfile(tgt_path):
            existing = pq.read_table(tgt_path)
            writer = pq.ParquetWriter(tgt_path + ".tmp", existing.schema)
            writer.write_table(existing)
            total += existing.num_rows

        for batch in src_file.iter_batches(batch_size=10000):
            tbl = pa.Table.from_batches([batch])
            if writer is None:
                out_path = tgt_path + ".tmp" if os.path.isfile(tgt_path) else tgt_path
                writer = pq.ParquetWriter(out_path, tbl.schema)
            writer.write_table(tbl)
            total += batch.num_rows

        if writer:
            writer.close()
            writer = None
            tmp = tgt_path + ".tmp"
            if os.path.isfile(tmp):
                os.replace(tmp, tgt_path)
    finally:
        if writer:
            writer.close()
    if progress_cb:
        progress_cb(total)
    return total


def _infer_pa_schema(rows: list[dict], cols: list[str]):
    """Infer a pyarrow schema from the first row, falling back to string for unknowns."""
    import pyarrow as pa
    if not rows:
        return pa.schema([pa.field(c, pa.string()) for c in cols])
    sample = rows[0]
    fields = []
    for c in cols:
        v = sample.get(c)
        if isinstance(v, bool):
            fields.append(pa.field(c, pa.bool_()))
        elif isinstance(v, int):
            fields.append(pa.field(c, pa.int64()))
        elif isinstance(v, float):
            fields.append(pa.field(c, pa.float64()))
        else:
            fields.append(pa.field(c, pa.string()))
    return pa.schema(fields)


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _csv_path(directory: str, table: str) -> str:
    return os.path.join(directory, f"{table}.csv")


def csv_table_exists(directory: str, table: str) -> bool:
    return os.path.isfile(_csv_path(directory, table))


def migrate_csv_to_db(
    src_dir: str,
    tgt_engine: Engine,
    src_table: str,
    tgt_table: str,
    tgt_schema: Optional[str],
    migration_mode: str,
    batch_size: int,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> int:
    """Read a CSV file and insert rows into a target DB table."""
    path = _csv_path(src_dir, src_table)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"CSV file not found: {path}")

    tgt_full = _full_table(tgt_schema, tgt_table)
    if migration_mode == "truncate_load":
        with tgt_engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {tgt_full}"))

    total = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = list(reader.fieldnames or [])
        batch: list[dict] = []
        for row in reader:
            batch.append(dict(row))
            if len(batch) >= batch_size:
                _insert_batch(tgt_engine, tgt_schema, tgt_table, cols, batch)
                total += len(batch)
                if progress_cb:
                    progress_cb(total)
                batch = []
        if batch:
            _insert_batch(tgt_engine, tgt_schema, tgt_table, cols, batch)
            total += len(batch)
            if progress_cb:
                progress_cb(total)
    return total


def migrate_db_to_csv(
    src_engine: Engine,
    tgt_dir: str,
    src_table: str,
    tgt_table: str,
    src_schema: Optional[str],
    table_filter: Optional[str],
    migration_mode: str,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> int:
    """Stream rows from a source DB table and write to a CSV file."""
    src_full = _full_table(src_schema, src_table)
    query = f"SELECT * FROM {src_full}"
    if table_filter:
        query += f" WHERE {_validate_filter(table_filter)}"

    os.makedirs(tgt_dir, exist_ok=True)
    path = _csv_path(tgt_dir, tgt_table)
    append_mode = migration_mode == "append" and os.path.isfile(path)
    file_mode = "a" if append_mode else "w"

    total = 0
    with src_engine.connect() as src_conn:
        result = src_conn.execution_options(stream_results=True).execute(text(query))
        cols = list(result.keys())
        with open(path, file_mode, newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            if not append_mode:
                writer.writeheader()
            for row in result:
                writer.writerow(dict(zip(cols, row)))
                total += 1
                if progress_cb and total % 1000 == 0:
                    progress_cb(total)
    if progress_cb:
        progress_cb(total)
    return total


def migrate_csv_to_csv(
    src_dir: str,
    tgt_dir: str,
    src_table: str,
    tgt_table: str,
    migration_mode: str,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> int:
    """Copy a CSV file to another directory."""
    src_path = _csv_path(src_dir, src_table)
    if not os.path.isfile(src_path):
        raise FileNotFoundError(f"CSV file not found: {src_path}")

    os.makedirs(tgt_dir, exist_ok=True)
    tgt_path = _csv_path(tgt_dir, tgt_table)
    append_mode = migration_mode == "append" and os.path.isfile(tgt_path)
    file_mode = "a" if append_mode else "w"

    total = 0
    with open(src_path, newline="", encoding="utf-8") as src_f:
        reader = csv.DictReader(src_f)
        cols = list(reader.fieldnames or [])
        with open(tgt_path, file_mode, newline="", encoding="utf-8") as tgt_f:
            writer = csv.DictWriter(tgt_f, fieldnames=cols)
            if not append_mode:
                writer.writeheader()
            for row in reader:
                writer.writerow(row)
                total += 1
    if progress_cb:
        progress_cb(total)
    return total
