"""C0 generation ledger summary: constant-size SQL metadata, never a tree walk."""
import os
from pathlib import Path
import sqlite3
import stat
from ..alpha_runtime_v1 import common as Q
from .quality_authority import read


def stamp(s):
    return (s.st_dev,s.st_ino,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def summarize(binding,root):
    """Caller must first prove parent and all recorded steps terminal C0."""
    receipt=read(binding['generation_receipt_reference']);root=Path(root).absolute()
    Q.need(receipt['runtime']==binding['runtime'] and receipt['execution_metadata']['original_launcher_plan_reference']==binding['plan_reference']
        and receipt['execution_metadata']['original_startup_proof_reference']==binding['startup_proof_reference']
        and receipt['status'] in ('COMPLETE_CANDIDATE_PILOT_NOT_TRAINING_RELEASE','COMPLETE_CANDIDATE_SHARD_NOT_TRAINING_RELEASE')
        and receipt['closed_family_export_molecules']==receipt['expected_molecules']
        and Path(binding['generation_receipt_reference']['path']).parent==root,
        'Actual complete same-source generation producer and terminal allocation binding')
    value=receipt['closed_ledger'];path=Path(value['path'])
    Q.need(value['schema_version']==2 and path.parent==root and not path.is_symlink()
        and value['whole_tree_root_blocks_used_as_total']is False and value['historical_peak_used_as_current']is False,
        'Explicit schema2 sealed generation ledger, never root blocks/peak as subtree total')
    Q.need(not any(Path(str(path)+s).exists()for s in ('-wal','-journal','-shm')),'Ledger must be closed without journal/WAL')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);db=None
    try:
        before=os.fstat(fd);native=path.lstat()
        Q.need(stat.S_ISREG(before.st_mode)and before.st_uid==Q.UID and before.st_nlink==1 and stamp(before)==stamp(native),
               'Own immutable same-FD ledger inode')
        # st_dev is deliberately absent: login/compute Gluster mount epochs differ.
        Q.need(value['producer_frame']==dict(uid=before.st_uid,size=before.st_size,mtime_ns=before.st_mtime_ns,
                   ctime_ns=before.st_ctime_ns,nlink=before.st_nlink),'Closed producer ledger frame changed')
        db=sqlite3.connect('file:/proc/self/fd/'+str(fd)+'?mode=ro&immutable=1',uri=True)
        Q.need(db.execute('PRAGMA user_version').fetchone()[0]==2,'U64 schema2 ledger required')
        logical,allocated,credit,cutoff=db.execute('SELECT logical,allocated,credit,cutoff FROM totals WHERE singleton=1').fetchone()
        directories=db.execute('SELECT allocated FROM directory_totals WHERE singleton=1').fetchone()[0]
        maximum=db.execute('SELECT maximum_ns FROM native_frontier WHERE singleton=1').fetchone()[0]
        totals=dict(closed_logical_bytes=logical,closed_allocated_bytes=allocated+directories,
            closed_directory_allocated_bytes=directories,eligible_old_own_allocated_bytes=credit,credit_cutoff_ns=cutoff)
        Q.need(totals==value['closed_totals'] and maximum==value['maximum_recorded_native_ns']
            and all(type(n)is int and n>=0 for n in (logical,allocated,directories,maximum)),
            'Persisted totals/frontier exactly match sealed actual producer, not historical peak')
        paths={root,path,Path(binding['generation_receipt_reference']['path'])}
        paths.update(map(Path,value['mutable_paths']));paths.update(map(Path,value['mutable_routing_directories']))
        # Only bounded top-level names; molecule/family subtrees are not enumerated.
        for p in root.iterdir():
            if p.is_symlink():raise ValueError('Generation top-level symlink rejected')
            if not p.is_dir():paths.add(p)
            Q.need(len(paths)<=2048,'Bounded top-level generation runtime namespace')
        Q.need(len(paths)<=2048,'Only bounded declared runtime/routing extras may use compact summary')
        seen=set();extra_blocks=extra_logical=0
        eligibility=max(value['closed_at_unix_ns'],maximum,before.st_ctime_ns,before.st_mtime_ns)
        for p in sorted(paths):
            Q.need(p==root or root in p.parents,'Summary extras must stay inside actual private generation root')
            try:s=p.lstat()
            except FileNotFoundError:continue
            Q.need(s.st_uid==Q.UID and (stat.S_ISREG(s.st_mode)or stat.S_ISDIR(s.st_mode))and stamp(s)==stamp(p.lstat()),
                   'Stable actual own file/directory summary extras; no symlinks')
            key=(s.st_dev,s.st_ino)
            if key in seen:continue
            seen.add(key)
            table='files'if stat.S_ISREG(s.st_mode)else'directories'
            old=db.execute('SELECT blocks,mtime,ctime FROM '+table+' WHERE path=?',(str(p),)).fetchone()
            if old is not None:
                Q.need(old==(s.st_blocks*512,s.st_mtime_ns,s.st_ctime_ns),'Closed recorded extra mutated')
                continue
            Q.need(not stat.S_ISREG(s.st_mode)or s.st_nlink==1,'Unregistered extra hardlink cannot receive ambiguous duplicate credit')
            extra_blocks+=s.st_blocks*512;extra_logical+=s.st_size if stat.S_ISREG(s.st_mode)else 0
            eligibility=max(eligibility,s.st_mtime_ns,s.st_ctime_ns)
        Q.need(stamp(before)==stamp(os.fstat(fd))==stamp(path.lstat()),'Ledger replaced or mutated while reading sameFD')
        return dict(kind='GENERATION_C0_LEDGER_V2_SUMMARY',scope=binding['scope'],path=str(root),
            allocated_bytes=allocated+directories+extra_blocks,logical_bytes=logical+extra_logical,
            maximum_eligible_ns=eligibility,generation_binding=binding,
            ledger_path=str(path),ledger_producer_frame=value['producer_frame'],
            persisted_closed_allocated_bytes=allocated+directories,small_extras_allocated_bytes=extra_blocks,
            unrecorded_tree_files_credited=False,whole_tree_enumerated=False,historical_peak_used_as_current=False)
    finally:
        if db is not None:db.close()
        os.close(fd)