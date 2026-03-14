"""Core migration engine: copies tables from source to target DB."""
import sqlalchemy as sa
from sqlalchemy import inspect, text, MetaData, Table, Column
from sqlalchemy import String, Text, Integer, BigInteger, Float, Numeric, Boolean, Date, DateTime
from sqlalchemy.engine import Engine
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)

def build_engine(db_type: str, host: str, port: int, database: str, username: str, password: str) -> Engine:
    port = port or {"postgresql": 5432, "mysql": 3306, "mssql": 1433}.get(db_type, 5432)
    if db_type == "postgresql":
        url = f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}"
        return sa.create_engine(url, pool_pre_ping=True)
    elif db_type == "mysql":
        url = f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
        return sa.create_engine(url, pool_pre_ping=True)
    elif db_type == "mssql":
        url = f"mssql+pymssql://{username}:{password}@{host}:{port}/{database}"
        return sa.create_engine(url, pool_pre_ping=True)
    raise ValueError(f"Unsupported db_type: {db_type}")

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
    src_full = f"{src_schema}.{src_table}" if src_schema else src_table
    tgt_full = f"{tgt_schema}.{tgt_table}" if tgt_schema else tgt_table

    query = f"SELECT * FROM {src_full}"
    if table_filter:
        query += f" WHERE {table_filter}"

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
                _insert_batch(tgt_engine, tgt_full, cols, batch)
                total += len(batch)
                if progress_cb:
                    progress_cb(total)
                batch = []

        if batch:
            _insert_batch(tgt_engine, tgt_full, cols, batch)
            total += len(batch)
            if progress_cb:
                progress_cb(total)

    return total

def _insert_batch(engine: Engine, table_full: str, cols: list[str], rows: list[dict]):
    col_names = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    sql = text(f"INSERT INTO {table_full} ({col_names}) VALUES ({placeholders})")
    with engine.begin() as conn:
        conn.execute(sql, rows)
