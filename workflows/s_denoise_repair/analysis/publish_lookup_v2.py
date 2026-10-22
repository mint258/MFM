"""Sonmi actual-parent verification before selecting the new canonical lookup."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import hashlib

PROJECT=Path('/share/home/zixiao/descriptor_analysis')
ROOT=PROJECT/'runs/s_denoise_repair_20261016'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    out=ROOT/'reports/lookup_v2_canonical_publication.json';assert not out.exists()
    pointer=json.loads((ROOT/'reports/lookup_v2_latest.json').read_text());assert sha(pointer['path'])==pointer['sha256']
    result=json.loads(Path(pointer['path']).read_text())
    assert result['status']=='NEW_TRAIN_LOOKUP_REFIT_AND_FULL_EVALUATION_COMPLETE' and result['TRAIN_records']==11104772
    assert result['metrics']['full']['records']==127082 and result['metrics']['D3_FULL2000']['records']==18486
    plan_path=ROOT/'configs/lookup_refit_v2_plan.json';assert result['plan_sha256']==sha(plan_path)
    plan=json.loads(plan_path.read_text());supplement=ROOT/'configs/lookup_refit_v2_supplemental_frozen_inputs.json'
    for item in plan['sources']+json.loads(supplement.read_text())['sources']:assert sha(item['path'])==item['sha256']
    ids={'4515527',result['job_id']}
    for ref in result['part_result_references']:
        assert sha(ref['path'])==ref['sha256'];part=json.loads(Path(ref['path']).read_text())
        assert part['status']=='LOOKUP_V2_TRAIN_PART_COMPLETE';ids.add(part['job_id'])
    chunk_numbers=set()
    for ref in result['chunks']:
        assert sha(ref['path'])==ref['sha256'] and ref['number'] not in chunk_numbers
        chunk_numbers.add(ref['number'])
    assert chunk_numbers==set(range(170))
    raw=subprocess.check_output(['sacct','-X','-j',','.join(sorted(ids)),'-n','-P','-o','JobIDRaw,State%40,ExitCode,ElapsedRaw,AllocCPUS'],
        text=True,stdin=subprocess.DEVNULL,timeout=60)
    parents={r[0]:r[1:] for r in (line.split('|') for line in raw.splitlines()) if r[0] in ids};assert set(parents)==ids
    for job in ids-{'4515527'}:assert parents[job][:2]==['COMPLETED','0:0'],(job,parents[job])
    assert parents['4515527'][0].split()[0] in ['COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED']
    canonical=ROOT/'reports/lookup_latest.json'
    if parents['4515527'][:2]==['COMPLETED','0:0']:
        assert canonical.exists();previous=json.loads(canonical.read_text());assert sha(previous['path'])==previous['sha256']
        old=json.loads(Path(previous['path']).read_text());assert old['status']==result['status'] and old['TRAIN_records']==11104772
        action='ORIGINAL_COMPLETE_LOOKUP_RETAINED_NO_SELECTION_BY_SCORE'
    else:
        assert not canonical.exists(),'Unexpected previous canonical lookup requires explicit provenance review'
        with canonical.open('x') as stream:json.dump(pointer,stream,indent=2);stream.write('\n')
        action='RESUMABLE_V2_CANONICAL_LOOKUP_PUBLISHED_AFTER_ACTUAL_PARENT_CLOSURE'
    record=dict(status=action,new_result=pointer,actual_parents=parents,raw_sacct=raw,
        plan_sha256=sha(plan_path),supplemental_frozen_inputs_sha256=sha(supplement),timestamp=time.time(),
        scientific_recipe_unchanged=True,all_11104772_TRAIN_records_contribute_once=True,
        no_validation_used_for_fit=True,original_LMDB_written=False,new_LMDB_created=False,
        historical_reference_A=.042,metrics=result['metrics'])
    with out.open('x') as stream:json.dump(record,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status=action,metrics=result['metrics'])))


if __name__=='__main__':main()
