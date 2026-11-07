"""Bounded SQLite-to-Arrow loading and literal SQL identifiers."""
from pathlib import Path
import uuid
import threading
from ..alpha_runtime_v1.common import need, reference


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def attempt(stage):
    path = Path(stage) / ('attempt_' + uuid.uuid4().hex)
    path.mkdir(mode=0o700)
    return path


def connection(out, workers, memory_bytes):
    import duckdb
    db = duckdb.connect(str(Path(out) / 'stage.duckdb'))
    db.execute('SET threads=' + str(int(workers)))
    db.execute('SET memory_limit=' + literal(str(int(memory_bytes)) + 'B'))
    db.execute('SET temp_directory=' + literal(Path(out) / 'spill'))
    db.execute('SET preserve_insertion_order=false')
    return db


def load_sqlite_table(db, incoming, name, columns, types, check):
    import pyarrow as pa
    schema = pa.schema(list(zip(columns, types)))
    db.execute('CREATE TABLE ' + name + '(' + ','.join(c + ' ' + ('BIGINT' if pa.types.is_integer(t) else 'VARCHAR') for c, t in zip(columns, types)) + ')')
    cursor = incoming.execute('SELECT ' + ','.join(columns) + ' FROM ' + name)
    while True:
        values = cursor.fetchmany(8192)
        if not values:
            break
        check()
        table = pa.Table.from_pylist([dict(zip(columns, row)) for row in values], schema=schema)
        db.register('incoming_chunk', table)
        try:
            db.execute('INSERT INTO ' + name + ' SELECT * FROM incoming_chunk')
        finally:
            db.unregister('incoming_chunk')


def copy_parquet(db, query, path):
    db.execute('COPY (' + query + ') TO ' + literal(path) + ' (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 65536)')
    import pyarrow.parquet as pq
    return {**reference(path), 'rows': pq.ParquetFile(path).metadata.num_rows}


class SQLStopper:
    """Interrupt only this connection when the actual resource guard stops."""
    def __init__(self, db, check):
        self.db, self.check = db, check
        self.done, self.errors = threading.Event(), []
        self.thread = threading.Thread(target=self.observe, daemon=True)
        self.thread.start()

    def observe(self):
        while not self.done.wait(1):
            try:
                self.check()
            except BaseException as exc:
                self.errors.append(repr(exc))
                self.db.interrupt()
                return

    def close(self):
        self.done.set(); self.thread.join()
