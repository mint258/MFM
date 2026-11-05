"""Immutable inputs, unique-inode output budgets and Root's CPU-analysis guard."""
from __future__ import annotations

from datetime import datetime
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys
import time

from workflows.data_v1_final.execution.cpu_analysis_v1.runtime_v2 import root_guard as _cpu_root_guard, checkpoint


def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):
            h.update(block)
    return h.hexdigest()


def ref(path):
    p=Path(path).absolute()
    return {"path":str(p),"bytes":p.stat().st_size,"sha256":digest(p)}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def require(pin,content=True):
    p=Path(pin["path"])
    s=p.lstat()
    if not p.is_absolute() or not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_size!=int(pin["bytes"]):
        raise ValueError("INPUT_TYPE_OWNER_SIZE_DIFFERS:"+str(p))
    if content and digest(p)!=pin["sha256"]:
        raise ValueError("INPUT_SHA_DIFFERS:"+str(p))
    return p


def identity(path):
    s=Path(path).stat()
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]


def new_root(path,allowed):
    p,a=Path(path).absolute(),Path(allowed).absolute()
    if p==a or a not in p.parents or any(x.is_symlink() for x in (p,*p.parents)):
        raise ValueError("OUTPUT_NOT_NEW_OWNED_EXTERNAL_CHILD")
    p.mkdir(parents=True,exist_ok=False,mode=0o700)
    return p


def unique_bytes(root):
    """Count this run's actual inodes once, including directories and failures."""
    total,seen=0,set();regular_counts={};regular_links={}
    for p in [Path(root),*Path(root).rglob("*")]:
        s=p.lstat()
        if s.st_uid!=os.getuid() or not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):
            raise ValueError("OUTPUT_UNKNOWN_OWNER_OR_TYPE:"+str(p))
        key=(s.st_dev,s.st_ino)
        if stat.S_ISREG(s.st_mode):
            regular_counts[key]=regular_counts.get(key,0)+1;regular_links[key]=s.st_nlink
        if key not in seen:
            seen.add(key)
            total+=s.st_size
    if any(regular_counts[key]!=links for key,links in regular_links.items()):
        raise ValueError("OUTPUT_HAS_HARDLINK_OUTSIDE_OWN_RUN")
    return total


def budget(root,cap,additional=0,reserve=2<<20):
    used=unique_bytes(root)
    if used+int(additional)+int(reserve)>int(cap):
        raise RuntimeError("UNIQUE_INODE_OUTPUT_CAP_EXCEEDED")
    return used


def save(path,value,root=None,cap=None):
    raw=(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+"\n").encode()
    if root is not None:
        budget(root,cap,len(raw))
    with Path(path).open("xb") as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    return ref(path)


def write_blob(path,raw,root,cap,reserve=2<<20):
    """Serialize commits under one lock; exact bytes are known before creation."""
    import fcntl
    lock=Path(root)/"output_budget.lock"
    with lock.open("a+b") as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        budget(root,cap,len(raw),reserve=reserve)
        with Path(path).open("xb") as out:
            out.write(raw);out.flush();os.fsync(out.fileno())
        fcntl.flock(stream,fcntl.LOCK_UN)
    return ref(path)


class ParquetSink:
    """Small compressed per-source outputs stay bounded before disk commits."""
    def __init__(self,schema,max_buffer_bytes):
        import pyarrow as pa
        import pyarrow.parquet as pq
        self.pa=pa;self.buffer=pa.BufferOutputStream();self.schema=schema
        self.writer=pq.ParquetWriter(self.buffer,schema,compression="zstd",use_dictionary=True)
        self.cap=max_buffer_bytes;self.rows=0

    def add(self,rows):
        if not rows:return
        self.writer.write_table(self.pa.Table.from_pylist(rows,schema=self.schema),row_group_size=4096)
        self.rows+=len(rows)
        if self.buffer.tell()>self.cap:
            raise RuntimeError("WORKER_COMPRESSED_BUFFER_CAP_EXCEEDED")

    def close(self,path,root,cap):
        self.writer.close();raw=self.buffer.getvalue()
        if raw.size>self.cap:raise RuntimeError("WORKER_COMPRESSED_BUFFER_CAP_EXCEEDED")
        result=write_blob(path,memoryview(raw),root,cap)
        result["rows"]=self.rows
        return result


def root_guard(path,pinned_path,cap,wall_limit=3600):
    return _cpu_root_guard(path,pinned_path,cap,wall_limit)


def checkpoint_iter(iterable):
    iterator=iter(iterable)
    while True:
        checkpoint()
        try:
            item=next(iterator)
        except StopIteration:
            return
        yield item


def legacy(config):
    """Import the already-proven functions only after checking their exact pins."""
    for pin in config["adapter_source_pins"]:
        require(pin)
    parent=Path(config["adapter_source_pins"][0]["path"]).parent
    sys.path.insert(0,str(parent))
    try:
        common=importlib.import_module("common")
        masks=importlib.import_module("pilot_masks")
        if Path(common.__file__).absolute()!=parent/"common.py" or Path(masks.__file__).absolute()!=parent/"pilot_masks.py":
            raise ValueError("LABEL_ADAPTER_IMPORT_PATH_COLLISION")
    finally:
        sys.path.pop(0)
    return common,masks


def sqlstr(s):
    return "'"+str(s).replace("'","''")+"'"


def path_list(paths):
    return "["+",".join(sqlstr(p) for p in paths)+"]"
