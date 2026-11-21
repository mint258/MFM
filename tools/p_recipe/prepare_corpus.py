"""Exclude discovered TRAIN/downstream overlaps; never refit normalization."""
import json
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

ROOT=Path('/share/home/zixiao/descriptor_analysis')
CONTROL=ROOT/'runs/p_recipe_20261113'
OUTPUT=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/corpus')

def main():
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    overlap=json.loads((CONTROL/'D6_identity.json').read_text())
    excluded=set(overlap['overlapping_molecules'])
    source=ROOT/'runs/data_v1_20261025/artifacts/export/D6_full_v31_20261105_v1/compact'
    manifest=json.loads((source/'manifest.json').read_text())
    ids=pq.read_table(Path(manifest['split_roots']['TRAIN'])/'id_map.parquet',
        columns=['molecule_id','molecule_index'],filters=[('record_kind','=','M')])
    indices=[];removed={}
    for mid,index in zip(ids.column('molecule_id').to_pylist(),ids.column('molecule_index').to_pylist()):
        if mid in excluded:removed[mid]=index
        else:indices.append(index)
    # Producer-only alignment of the authorized cohort, without repeating D6(d).
    if set(removed)!=excluded or len(indices)!=manifest['molecules']['TRAIN']-len(excluded):
        raise ValueError('Approved molecule exclusions do not align with delivered M records')
    OUTPUT.mkdir(parents=True,exist_ok=True)
    np.save(OUTPUT/'train_indices.npy',np.asarray(indices,dtype=np.int64),allow_pickle=False)
    result=dict(source_root=str(source),split='TRAIN',source_molecules=manifest['molecules']['TRAIN'],
        train_molecules=len(indices),excluded_molecules=len(removed),excluded_indices=sorted(removed.values()),
        excluded_molecule_ids=sorted(removed),train_indices=str(OUTPUT/'train_indices.npy'),
        authorization='User20261114 supplement: exclude discovered overlaps, preserve 20261107 fullTRAIN normalization and continue',
        original_files_modified=False,identity_audit_repeated=False)
    (OUTPUT/'corpus.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('source_molecules','train_molecules','excluded_molecules')}),flush=True)
    return result

if __name__=='__main__':main()
