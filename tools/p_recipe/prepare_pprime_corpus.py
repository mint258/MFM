"""Derive source-available P-prime cohorts from the published M18/M14 flags."""
import argparse,json
from pathlib import Path
import lmdb
import numpy as np
from phychem_mfm.phase1.v31_loader import decode_mfm4,record_key,split_metadata

def select_eligible(directory,indices,*,train):
    selected=[]
    with lmdb.open(str(directory),readonly=True,lock=False,readahead=False,max_readers=512) as env:
        with env.begin(buffers=True) as transaction:
            for ordinal,index in enumerate(indices):
                payload=transaction.get(record_key('M',int(index)))
                if payload is None:raise KeyError(('M',int(index)))
                arrays=decode_mfm4(payload,array_ids={14,18} if train else {14})
                holdout=arrays[14].astype(bool)
                eligible=(arrays[18].astype(bool)&~holdout) if train else ~holdout
                if np.any(eligible):selected.append(int(index))
                if (ordinal+1)%100000==0:
                    print(json.dumps(dict(role='TRAIN' if train else 'Common_VAL',inspected=ordinal+1,available=len(selected))),flush=True)
    return np.asarray(selected,dtype=np.int64)

def prepare(configuration):
    from phychem_mfm.phase1.p_recipe_data import validation_indices
    c=json.loads(Path(configuration).read_text())
    supplied=json.loads(Path(c['corpus']).read_text())
    original=Path(supplied.get('original_corpus',c['corpus']));corpus=json.loads(original.read_text())
    destination=original.parent/'Pprime_corpus.json'
    if destination.exists():
        available=json.loads(destination.read_text())
        if available.get('original_corpus')!=str(original):raise ValueError('Existing Pprime cohort has another source')
    else:
        indices=np.load(corpus['train_indices'])
        train_dir,_=split_metadata(Path(c['root']),'TRAIN')
        full_dir,_=split_metadata(Path(c['root']),'FULL')
        train=select_eligible(train_dir,indices,train=True)
        # Published Common VAL has7567 molecules; use all before source eligibility.
        full_val=validation_indices(c,count=7567)
        val=select_eligible(full_dir,full_val,train=False)
        if len(train)<128000 or len(val)<2000:raise ValueError('Insufficient published source-eligible cohort')
        train_path=original.parent/'Pprime_train_indices.npy'
        val_path=original.parent/'Pprime_VAL_indices.npy'
        np.save(train_path,train);np.save(val_path,val)
        available=dict(corpus,original_corpus=str(original),source_condition='UFF/Pprime',
            train_indices=str(train_path),train_molecules=len(train),
            source_available_common_validation_indices=str(val_path),
            source_available_common_validation_molecules=len(val),
            geometry_unavailable_train_molecules=len(indices)-len(train),
            geometry_unavailable_common_validation_molecules=len(full_val)-len(val),
            eligibility='TRAIN uses published M18 and excludes M14; Common VAL uses actual non-heldout UFF geometries; original cohort/normalizations unchanged')
        destination.write_text(json.dumps(available,indent=2)+'\n')
    c['corpus']=str(destination)
    Path(configuration).write_text(json.dumps(c,indent=2)+'\n')
    print(json.dumps(dict(status='PPRIME_COHORT_READY',corpus=str(destination),train_molecules=available['train_molecules'],validation_molecules=available['source_available_common_validation_molecules'])),flush=True)
    return available

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--configuration',required=True);a=p.parse_args();prepare(a.configuration)
