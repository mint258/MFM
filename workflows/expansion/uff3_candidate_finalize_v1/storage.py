"""Storage classification and honest10M extrapolation, no chemical statistics."""
import os
from pathlib import Path
import stat
from ..alpha_runtime_v1.common import need

VARIABLE={'UFF_D_FAMILY_DATA','SAVED_MOLECULE_EVIDENCE','MOLECULE_DIRECTORY_METADATA','FAMILY_DIRECTORY_METADATA'}


def fact(path,category):
    path=Path(path);a=path.lstat();b=path.lstat()
    fields=lambda s:(s.st_dev,s.st_ino,s.st_uid,s.st_mode,s.st_size,s.st_blocks,s.st_mtime_ns,s.st_ctime_ns)
    need(a.st_uid==os.getuid()and(stat.S_ISREG(a.st_mode)or stat.S_ISDIR(a.st_mode))
        and fields(a)==fields(b),'Stable own native storage fact; symlinks/special files not counted as regular data')
    return (format(a.st_dev,'016x'),format(a.st_ino,'016x'),str(path),category,
            a.st_size if stat.S_ISREG(a.st_mode)else 0,a.st_blocks*512,
            'FILE'if stat.S_ISREG(a.st_mode)else'DIRECTORY',a.st_mtime_ns,a.st_ctime_ns)


def initialize(db):
    db.execute('CREATE TABLE physical(dev VARCHAR,ino VARCHAR,path VARCHAR,category VARCHAR,logical BIGINT,allocated BIGINT,kind VARCHAR,mtime BIGINT,ctime BIGINT)')


def add(db,items):
    if items:db.executemany('INSERT INTO physical VALUES(?,?,?,?,?,?,?,?,?)',items)


def projection(rows,shared):
    variable=[r for r in rows if r['category']in VARIABLE]
    return None if shared else dict(basis_molecules=2500000,target_molecules=10000000,scale=4,
        projected_logical_dataset_bytes=4*sum(r['logical_file_bytes']for r in variable),
        projected_allocated_dataset_bytes=4*sum(r['actual_allocated_blocks_bytes']for r in variable),
        is_extrapolation_not_measured_capacity=True,
        assumes_same_R_N_molecule_size_sparsity_and_compression_distribution=True)

def summarize(db):
    # Inodes can exceed signed64; dev/ino stay lossless TEXT. A shared hardlink
    # across cost categories is reported and makes extrapolation unavailable,
    # rather than counted twice or assigned an arbitrary cost owner.
    db.execute('CREATE TEMP VIEW native_unique AS SELECT dev,ino,min(category)category,min(logical)logical,min(allocated)allocated,count(DISTINCT category)categories,min(kind)kind FROM physical GROUP BY dev,ino')
    need(db.execute('SELECT count(*)FROM(SELECT dev,ino FROM physical GROUP BY dev,ino HAVING min(logical)<>max(logical)OR min(allocated)<>max(allocated)OR min(kind)<>max(kind))').fetchone()[0]==0,
         'Same inode facts changed during storage closure')
    rows=[dict(category=c,logical_file_bytes=l,actual_allocated_blocks_bytes=a,inodes=n)
        for c,l,a,n in db.execute('SELECT category,sum(logical),sum(allocated),count(*)FROM native_unique GROUP BY category ORDER BY category').fetchall()]
    shared=db.execute('SELECT count(*)FROM native_unique WHERE categories<>1').fetchone()[0]
    return dict(categories=rows,total_logical_file_bytes=sum(r['logical_file_bytes']for r in rows),
        total_actual_allocated_blocks_bytes=sum(r['actual_allocated_blocks_bytes']for r in rows),actual_native_inode_deduplication=True,shared_cross_category_inodes=shared,
        dataset_variable_categories=sorted(VARIABLE),linear10M_projection=projection(rows,shared),
        fixed_NN_full_pool_ranking_Common_calibration_and_shared_inputs_scaled=False,
        QA_and_finalizer_SQL_scratch_scaled=False,
        projected_10M_scientific_execution_authorized_or_started=False)