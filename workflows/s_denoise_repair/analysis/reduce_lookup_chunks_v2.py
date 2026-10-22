"""Ordered canonical reduction and unchanged original FULL lookup evaluator."""
from concurrent.futures import ProcessPoolExecutor
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import time
import refit_lookup as canonical
from runtime import ROOT,OLD,assert_allocation,native_components,save,sha
from lookup_refit_chunks_v2 import PLAN,OUT,validate_plan,read_chunk,bounds

_TABLE=None


def initialize_eval(table):
    canonical.initialize_worker('full',table);canonical._DATASET.cache_bytes=0


def main():
    assert_allocation();assert not (ROOT/'GUIDE_STOP.json').exists();plan=validate_plan()
    output=OUT/('reduce_job'+os.environ['SLURM_JOB_ID']);output.mkdir(exist_ok=False)
    references=[];parts=[]
    for part in range(plan['parts']):
        pointer=json.loads((OUT/('part'+str(part)+'_latest.json')).read_text());assert sha(pointer['path'])==pointer['sha256']
        report=json.loads(Path(pointer['path']).read_text());assert report['status']=='LOOKUP_V2_TRAIN_PART_COMPLETE'
        assert report['part']==part and report['plan_sha256']==sha(PLAN)
        parts.append(dict(**pointer,job_id=report['job_id']))
    aggregate={};visited=0
    count=math.ceil(11104772/plan['chunk_records'])
    for number in range(count):
        ref=read_chunk(number,plan);assert ref is not None;references.append(ref)
        chunk=json.loads(Path(ref['path']).read_text())['result'];visited+=chunk['records']
        for key,value in chunk['stats'].items():
            accumulator=aggregate.setdefault(key,[0,0.,0.])
            for j in range(3):accumulator[j]+=value[j]
    assert visited==11104772
    table={int(key):v[1]/v[0] for key,v in aggregate.items() if v[0]>=32 and int(key)%101<100}
    save(output/'TRAIN_only_bin_statistics.json',aggregate);save(output/'TRAIN_only_lookup.json',{str(k):v for k,v in table.items()})
    index,dataset,_=native_components('full',seed=0,epoch_noise=True);records=len(index);dataset.close();assert records==127082
    values={'full':[0.,0.,0,0,0],'D3_FULL2000':[0.,0.,0,0,0]}
    with ProcessPoolExecutor(16,mp_context=mp.get_context('spawn'),initializer=initialize_eval,initargs=(table,)) as pool:
        for result in pool.map(canonical.evaluate_chunk,[(i,min(i+8192,records)) for i in range(0,records,8192)],chunksize=1):
            for role in values:
                for j in range(5):values[role][j]+=result[role][j]
    assert values['full'][3]==127082 and values['D3_FULL2000'][3]==18486
    metrics={role:dict(lookup_rmse_A=math.sqrt(v[0]/v[2]),noisy_rmse_A=math.sqrt(v[1]/v[2]),pairs=v[2],records=v[3],lookup_used_pairs=v[4]) for role,v in values.items()}
    report=dict(status='NEW_TRAIN_LOOKUP_REFIT_AND_FULL_EVALUATION_COMPLETE',execution_revision=2,TRAIN_records=visited,
        validation_values_used_for_fit=False,sigma_A=.1,recipe=plan['recipe'],noise_seed_includes_epoch=True,view_seed=0,evaluation_epoch=0,
        historical_guide_reference_A=.042,metrics=metrics,input_manifest_sha256=sha(OLD/'training_inputs_v1/manifest.json'),
        plan_sha256=sha(PLAN),part_result_references=parts,chunks=references,
        original_fit_and_evaluation_functions_unchanged=True,ordered_reduction_matches_original_chunk_order=True,
        record_cache_bytes=0,job_id=os.environ['SLURM_JOB_ID'],canonical_publication_pending_actual_Sonmi_parent_verification=True)
    save(output/'result.json',report)
    save(ROOT/'reports/lookup_v2_latest.json',dict(path=str(output/'result.json'),sha256=sha(output/'result.json')))
    print(json.dumps(dict(status=report['status'],TRAIN_records=visited,metrics=metrics)),flush=True)


if __name__=='__main__':main()
