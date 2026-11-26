"""Transcribe required fixed-VAL records once; do not rerun a model or score."""
import csv
import io
import json
import math
from pathlib import Path
from cpu_execution_20261126 import execution_fields,native_record
from storage_20261122 import CONTROL as C,REPO as R,write


def run():
    native_record()
    destination=R/'results/s_recipe/budget_curve.csv'
    marker=C/'budget_VAL_transcription_20261126_COMPLETE.json'
    if marker.exists():
        print(json.dumps(dict(status='VAL_ALREADY_TRANSCRIBED',source=str(destination))),flush=True)
        return 0
    if destination.exists():raise ValueError('Inspect an existing curve; do not repeat original VAL consumption')
    read=lambda path:json.loads(Path(path).read_text())
    matrix=read(R/'configs/s_recipe/full_finetune_matrix_20261124.json')
    selected={(point['run'],point['samples']):point['point'] for point in matrix['points']
        if point['source_training_budget']==9000000 and point['run'] in ('S_B0_s0_9M','S_final_s0_9M')}
    rows=[]
    originals=0
    families=set()
    nonfinite=[]
    for arm,run,config_name in (('S-B0','S_B0_s0_9M','S-B0'),('S-final','S_final_s0_9M','S-final')):
        delivered=R/'results/s_recipe'/(run+'.json')
        endpoint=read(delivered)
        c=read(R/'configs/s_recipe/confirmation'/(config_name+'.json'))
        if (endpoint.get('status')!='COMPLETE' or endpoint.get('run')!=run
                or endpoint.get('samples')!=9000000 or endpoint.get('layer')!=6 or c['run']!=run):
            raise ValueError('Reuse only the already delivered original layer6 9M endpoint')
        for samples in range(500000,9000001,500000):
            if samples==9000000:
                val=endpoint['final_VAL']
                val_source=str(delivered)+'#final_VAL'
            else:
                val_path=C/'training'/run/('VAL_'+str(samples)+'.json')
                val=read(val_path)
                val_source=str(val_path)
                originals+=1
            if val.get('samples')!=samples or not isinstance(val.get('losses'),dict):
                raise ValueError('Original VAL record belongs to another sample boundary')
            for family,value in val['losses'].items():
                if value is not None and (not isinstance(value,(int,float)) or not math.isfinite(value)):
                    nonfinite.append(dict(run=run,samples=samples,family=family,value=value))
            families.update(val['losses'])
            row=dict(arm=arm,samples=samples,source_training_budget=9000000,source_run=run,
                readout_run=run if samples==9000000 else '',readout_complete=samples==9000000,
                descriptive_only=True,layer=6,independent_budget=False,
                readout_status='COMPLETE_REUSED_9M' if samples==9000000 else
                    'WAITING_GPU' if samples%1000000==0 else 'NOT_REGISTERED_AT_500K',
                VAL_kind='original_fixed_5000_VAL_per_head_no_new_evaluation',VAL_source=val_source,
                disabled=json.dumps(c['disabled']),VAL_counts_json=json.dumps(val['counts'],sort_keys=True),
                fullFT_point=selected.get((run,samples),''),
                fullFT_status='WAITING_COMPLETED_POINT' if (run,samples) in selected else 'NOT_REGISTERED',
                fullFT_mean='',fullFT_ci_lower='',fullFT_ci_upper='',_losses=val['losses'])
            for name in ('R1','R3'):
                value=endpoint['readouts'][name] if samples==9000000 else None
                row[name+'_mean']=value['mean_normalized_improvement'] if value else ''
                row[name+'_ci_lower']=value['bootstrap_ci'][0] if value else ''
                row[name+'_ci_upper']=value['bootstrap_ci'][1] if value else ''
                pair=endpoint.get('paired_vs_B0',{}).get(name,{}) if arm=='S-final' and samples==9000000 else {}
                for field in ('delta','ci_lower','ci_upper'):
                    row[name+'_S_final_minus_S_B0_'+field]=pair.get(field,'')
            rows.append(row)
    for row in rows:
        losses=row.pop('_losses')
        for family in sorted(families):row['VAL_loss_'+family]=losses.get(family,'')
    if len(rows)!=36 or originals!=34:raise ValueError('Expected both complete eighteen-point fixed-VAL series')
    stream=io.StringIO(newline='')
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    pending=destination.with_name(destination.name+'.next')
    pending.write_text(stream.getvalue())
    pending.replace(destination)
    value=dict(status='VAL_COMPONENT_COMPLETE_READOUTS_AND_FULLFT_PENDING',**execution_fields(),
        output=str(destination),rows=len(rows),original_VAL_records_transcribed=originals,
        final_VAL_records_reused_from_delivery=2,original_9M_readouts_reused=2,
        expected_readout_points=18,missing_intermediate_readouts=16,registered_fullFT_points=5,
        nonfinite_original_VAL_cells_reported=nonfinite,new_model_evaluations=0,new_bootstraps=0,
        next='Fill new readout/fullFT columns from their successful producers; reuse these VAL columns without reopening original VAL files')
    write(marker,value)
    write(R/'results/s_recipe/budget_curve_status.json',value)
    print(json.dumps(value),flush=True)
    return 0
