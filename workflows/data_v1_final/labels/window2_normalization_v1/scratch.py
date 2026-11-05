"""Optional group output on node-local scratch, shared report published last."""
import json,os,shutil
from pathlib import Path
from . import io as I

OUTPUT_REFERENCES=('r73_derived_reference','radix_histogram','mask_override_reference','molecule_field_means_reference')

def execute_group(work,compute):
    cfg,stage,shared_attempt,group=work
    shared_attempt=Path(shared_attempt).absolute();name='group_%04d'%group['group_index']
    producer_inputs=dict(cfg['group_producer_inputs'],statistics_purpose=cfg['statistics_purpose'],
        group_index=group['group_index'],source_job_id=group['source_job_id'])
    # A report is the existing group manifest, written only after every output
    # is closed and copied. Recover such a publication if parent checkpointing
    # was interrupted; no numeric file is opened or replayed here.
    for filename in sorted(shared_attempt.parent.glob('attempt_*/'+name+'/report.json')):
        report=I.load(filename)
        if report.get('producer_inputs')==producer_inputs:return I.ref(filename)
    local_attempt=Path(cfg['group_scratch_root']).absolute()/('job_'+os.environ.get('SLURM_JOB_ID','local'))/shared_attempt.parent.name/shared_attempt.name
    local_attempt.mkdir(parents=True,exist_ok=True)
    reference=compute((dict(cfg),stage,str(local_attempt),group))
    report=I.load(reference['path']);local_group=local_attempt/name
    shared_group=shared_attempt/name
    shared_group.mkdir(parents=True,exist_ok=False)
    copied={}
    for key in OUTPUT_REFERENCES:
        original=report.get(key)
        if not original:continue
        source=Path(original['path']).absolute()
        if source.parent!=local_group:continue  # an existing shared input ref
        target=shared_group/source.name
        if source not in copied:
            temporary=target.with_name(target.name+'.copying')
            shutil.copyfile(source,temporary);os.replace(temporary,target)
            copied[source]=target
        report[key]=dict(original,path=str(copied[source]))
    report['producer_inputs']=producer_inputs
    report['group_output_publication']='CLOSED_LOCAL_OUTPUTS_COPIED_SHARED_REPORT_LAST'
    # Numeric state and source order are unchanged; only output paths move.
    return I.save(shared_group/'report.json',report)
