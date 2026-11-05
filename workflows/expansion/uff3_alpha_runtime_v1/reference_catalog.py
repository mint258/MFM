"""Newline-closed full-QA reference catalogs, bounded rows and same-FD EOF proof."""
import hashlib
import json
import os
from pathlib import Path
import stat
from ..alpha_runtime_v1 import common as Q

SCHEMA='PUBCHEM_UFF3_QA_REFERENCE_CATALOG_V1'
MAX_ROW_BYTES=1<<20


def literal(path,root):
    path=Path(path);root=Path(root)
    Q.need(path.is_absolute()and '..'not in path.parts and '..'not in root.parts and path.parent==root and not any(p.is_symlink()for p in(path,*path.parents)),
           'Catalog must be literal direct child of actual private QA result root')
    Q.need(root.is_dir()and root.lstat().st_uid==os.getuid(),'Own actual private QA root required')
    return path


def frame(value):
    Q.need(stat.S_ISREG(value.st_mode)and value.st_uid==os.getuid()and value.st_nlink==1,
           'Own regular closed catalog without hardlinks')
    return(value.st_dev,value.st_ino,value.st_uid,value.st_mode,value.st_nlink,value.st_size,value.st_mtime_ns,value.st_ctime_ns)


def reference(value):
    Q.need(isinstance(value,dict)and isinstance(value.get('path'),str)and Path(value['path']).is_absolute()
        and type(value.get('bytes'))is int and value['bytes']>=0 and isinstance(value.get('sha256'),str)
        and len(value['sha256'])==64 and all(c in '0123456789abcdef'for c in value['sha256']),
        'Complete original reference row; retain all additional original fields')
    return value


def write(path,values,root,kind,budget):
    path=literal(path,root);Q.need(kind in ('family_files','batch_manifests'),'Explicit QA reference catalog kind')
    digest=hashlib.sha256();rows=size=0;seen=set()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb')as out:
        for value in values:
            reference(value);Q.need(value['path']not in seen,'Duplicate catalog member path')
            seen.add(value['path']);raw=Q.canonical(value)+b'\n'
            Q.need(len(raw)<=MAX_ROW_BYTES,'Bounded complete reference catalog row')
            out.write(raw);digest.update(raw);rows+=1;size+=len(raw)
            if rows%256==0:out.flush();budget.check()
        out.flush();os.fsync(out.fileno());before=frame(os.fstat(out.fileno()))
        Q.need(before==frame(path.lstat())and before[5]==size,'Published catalog FD/path/size changed')
    Q.need(before==frame(path.lstat()),'Catalog changed at writer close')
    budget.register(path);budget.check()
    return dict(schema=SCHEMA,kind=kind,path=str(path),bytes=size,sha256=digest.hexdigest(),rows=rows)


def read(ref,root,kind,check=lambda:None):
    """Consumer must exhaust iterator; only then is SHA/row count/EOF accepted."""
    Q.need(ref['schema']==SCHEMA and ref['kind']==kind and type(ref['rows'])is int and ref['rows']>=0
        and type(ref['bytes'])is int and ref['bytes']>=0,'Actual closed catalog declaration')
    path=literal(ref['path'],root);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    digest=hashlib.sha256();rows=size=0;seen=set()
    with os.fdopen(fd,'rb')as stream:
        before=frame(os.fstat(stream.fileno()))
        Q.need(before==frame(path.lstat())and before[5]==ref['bytes'],'Same native closed catalog FD/path/declared size')
        while raw:=stream.readline(MAX_ROW_BYTES+1):
            Q.need(len(raw)<=MAX_ROW_BYTES and raw.endswith(b'\n'),'Complete bounded newline catalog row/EOF required')
            value=reference(json.loads(raw));Q.need(value['path']not in seen,'Duplicate closed catalog member path')
            seen.add(value['path']);digest.update(raw);rows+=1;size+=len(raw)
            Q.need(rows<=ref['rows']and size<=ref['bytes'],'Catalog exceeds declared closed rows/bytes')
            if rows%256==0:check()
            yield value
        Q.need(rows==ref['rows']and size==ref['bytes']and digest.hexdigest()==ref['sha256'],
               'Whole catalog SHA/rows/bytes/EOF differs')
        Q.need(before==frame(os.fstat(stream.fileno()))==frame(path.lstat()),'Closed catalog mutated/replaced during sameFD read')
        check()


def members(qa,key,qa_reference,check=lambda:None):
    """Full catalogs and original small inline producers remain distinct."""
    kinds={'all_family_file_references':'family_files','closed_batch_manifest_references':'batch_manifests'}
    catalog=key+'_catalog'
    Q.need(not(key in qa and catalog in qa),'Ambiguous inline and catalog QA membership')
    if catalog in qa:
        yield from read(qa[catalog],Path(qa_reference['path']).parent,kinds[key],check)
    else:
        values=qa[key];Q.need(isinstance(values,list),'Actual original inline membership list required')
        seen=set()
        for value in values:
            reference(value);Q.need(value['path']not in seen,'Duplicate legacy inline reference member')
            seen.add(value['path']);yield value