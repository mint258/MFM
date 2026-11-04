"""Streaming closed-score metadata and original production-result validation."""
import hashlib
import json
import os
from pathlib import Path
import stat
import struct

N=1196122
FIELDS={'ecfp4_2048_hex','nearest_v1_key','nearest_v1_tanimoto','reference_ordinal',
        'score_numerator','score_denominator','evaluated_references',
        'strictly_bound_pruned_references','reference_molecules'}
PRESERVED=('filtered_pool_reference','reference','assigned_hash_buckets','partition_id','scope_key')


def need(value,message):
    if not value:raise ValueError(message)


def signature(s):return(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def actual_frame(path,uid):
    value=Path(path).lstat()
    need(stat.S_ISREG(value.st_mode)and value.st_uid==uid,'Actual own closed score/journal regular file')
    return signature(value)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def result_value(row):
    """Actual production9-column shape; no searched-group tuple is fabricated."""
    need(set(row)==FIELDS,'Exactly actual closed production score columns')
    fp=row['ecfp4_2048_hex'];need(isinstance(fp,str)and len(fp)==512 and all(c in'0123456789abcdef'for c in fp),'Exact FP bytes')
    for name in('reference_ordinal','score_numerator','score_denominator','evaluated_references',
                'strictly_bound_pruned_references','reference_molecules'):
        need(type(row[name])is int,'Original integral result field: '+name)
    num=row['score_numerator'];den=row['score_denominator'];index=row['reference_ordinal']
    need(row['reference_molecules']==N and 0<=index<N and 1<=den<=2048 and 0<=num<=den
         and row['evaluated_references']>=0 and row['strictly_bound_pruned_references']>=0
         and row['evaluated_references']+row['strictly_bound_pruned_references']==N,'Complete unchanged integer NN accounting')
    need(type(row['nearest_v1_tanimoto'])is float and struct.pack('<d',row['nearest_v1_tanimoto'])==struct.pack('<d',num/den),
         'Original binary64 score equals original unreduced integer fraction')
    return dict(score=row['nearest_v1_tanimoto'],**{name:row[name]for name in('reference_ordinal','score_numerator',
        'score_denominator','evaluated_references','strictly_bound_pruned_references','reference_molecules')})


def collect(root,uid,output,check=lambda:None):
    """Caller holds the terminal source parent.lock; no large DATA is read here."""
    root=Path(root);target=root/'scores';seen={};journals=[];parts=rows=0;ignored_tails=0
    need(root.is_absolute()and not root.is_symlink(),'Literal closed upstream root')
    with Path(output).open('xb')as out:
        for path in sorted(root.glob('closed_files*.jsonl')):
            before=actual_frame(path,uid);digest=hashlib.sha256();size=0;tail=0
            with path.open('rb')as stream:
                need(signature(os.fstat(stream.fileno()))==before,'Same closed journal FD')
                while True:
                    raw=stream.readline((64<<10)+1)
                    if not raw:break
                    need(len(raw)<=64<<10,'Bounded closed journal reference line')
                    digest.update(raw);size+=len(raw)
                    if not raw.endswith(b'\n'):
                        tail+=1;break
                    entry=json.loads(raw);candidate=Path(entry['path'])
                    need(candidate.is_absolute()and candidate.is_relative_to(root),'Journal path outside original root')
                    if not candidate.is_relative_to(target):continue
                    need(candidate.suffix=='.parquet'and candidate.resolve(strict=True)==candidate
                         and not any(p.is_symlink()for p in(candidate,*candidate.parents)),
                         'Literal closed score Parquet path')
                    ref={k:entry[k]for k in('path','bytes','sha256','rows','fp_bucket')}
                    need(type(ref['rows'])is int and ref['rows']>0 and type(ref['bytes'])is int and ref['bytes']>0
                         and isinstance(ref['sha256'],str)and len(ref['sha256'])==64
                         and ref['fp_bucket']in'0123456789abcdef'and len(ref['fp_bucket'])==1,'Complete score reference fields')
                    token=canonical(ref);previous=seen.get(ref['path'])
                    if previous is not None:
                        need(previous==token,'Conflicting duplicate closed score reference');continue
                    current=actual_frame(candidate,uid);need(current[4]==ref['bytes'],'Closed score physical bytes differ')
                    seen[ref['path']]=token;parts+=1;rows+=ref['rows']
                    out.write(canonical(dict(reference=ref,current_frame=list(current)))+b'\n')
                    if parts%128==0:check()
                after=signature(os.fstat(stream.fileno()))
            need(before==after==actual_frame(path,uid)and size==before[4],'Terminal journal changed/EOF differs')
            ignored_tails+=tail
            journals.append(dict(reference=dict(path=str(path),bytes=size,sha256=digest.hexdigest()),current_frame=list(before),
                                 incomplete_final_line_preserved_and_not_adopted=bool(tail)))
        out.flush();os.fsync(out.fileno())
    need(parts>0,'Actual terminal source has no closed score parts')
    return dict(parts=parts,rows=rows,journals=journals,incomplete_journal_tails=ignored_tails,
                score_body_SHA_not_recomputed_by_metadata_collector=True)
