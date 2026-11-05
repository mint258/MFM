"""Independent full-TRAIN P-prime statistics, no repeated raw source projection."""
import argparse,collections,concurrent.futures as cf,json,multiprocessing as mp,os
from pathlib import Path
from . import projection as P,statistics as T
from ..window2_normalization_v1 import io as I,run as Original


def fit(plan,cache):
    root=Path(plan['output'])/'statistics';root.mkdir(parents=True,exist_ok=True)
    cfg={'mode':'full','coverage_reference':I.ref(Path(plan['output'])/'projection/manifest.json'),
        'field_map_reference':cache['field_map_reference'],'logical_group_plan_reference':cache['logical_group_plan_reference'],
        'element_basis':cache['element_basis'],'eligibility_reference':cache['eligibility'],'input_release_reference':I.ref(plan['common']),
        'workers':plan.get('workers',16),'element_models_reference':None,'exact_tail_reference':None,'query_stage_reference':None}
    checkpoint=root/'checkpoint.json'
    if checkpoint.exists():
        state=I.load(checkpoint);P.need(state['inputs']==cfg,'SAME_CLOSED_PPRIME_CACHE_FOR_RESUME')
    else:
        state={'inputs':dict(cfg),'purpose_index':0,'pass_index':0,'active_stage':None,'groups':{},'results':{}};I.save(checkpoint,state)
    groups=I.load_data(cache['logical_group_plan_reference'])['groups'];fields=I.load_data(cache['field_map_reference'])
    with cf.ProcessPoolExecutor(cfg['workers'],mp_context=mp.get_context('spawn'))as pool:
        while state['purpose_index']<len(Original.ROUTES):
            purpose=Original.ROUTES[state['purpose_index']];current=dict(cfg,statistics_purpose=purpose)
            current.update({key:value for key,value in state['results'].items()if key in('element_models_reference','exact_tail_reference','query_stage_reference')})
            if state['active_stage']is None:
                state['pass_index']+=1;stage_root=root/('pass_%04d'%state['pass_index']);stage_root.mkdir()
                stage=T.Original.initial_stage(current,fields);stage['element_basis']=cfg['element_basis']
                state['active_stage']=I.save(stage_root/'stage.json',stage);state['groups']={};I.save(checkpoint,state)
            else:
                stage=I.load_data(state['active_stage']);stage_root=Path(state['active_stage']['path']).parent
            attempt=0
            while(stage_root/('attempt_%03d'%attempt)).exists():attempt+=1
            attempt_root=stage_root/('attempt_%03d'%attempt);attempt_root.mkdir();pending={}
            for group in groups:
                key=str(group['group_index'])
                if key not in state['groups']:pending[pool.submit(T.group_pass,(current,stage,str(attempt_root),group))]=key
            errors=[]
            for future in cf.as_completed(pending):
                key=pending[future]
                try:state['groups'][key]=future.result()
                except BaseException as exc:errors.append({'group':key,'error':repr(exc)})
                I.save(checkpoint,state)
                print(json.dumps({'purpose':purpose,'pass':state['pass_index'],'closed_groups':len(state['groups']),'total_groups':len(groups),'errors':errors}),flush=True)
            if errors:raise ValueError('PPRIME_STATISTIC_GROUP_ERRORS:'+repr(errors))
            reports=[I.load_data(state['groups'][str(g['group_index'])])for g in groups]
            if purpose=='element_reference':
                models={str(f['field_id']):T.Original.B.merge_qr([report['energy_TSQR'][str(f['field_id'])]for report in reports])for f in fields if f['element_reference_eligible']}
                counts=collections.defaultdict(collections.Counter)
                for report in reports:
                    for fid,value in report['field_counts'].items():counts[fid].update(value)
                result={'element_models_reference':I.save(stage_root/'element_models.json',models),'validity_mask_counts_reference':I.save(stage_root/'validity_mask_counts.json',{'fields':{fid:dict(v)for fid,v in counts.items()},'new_mask_fraction_is_report_only':True,'geometry_source':'uff_sprime','EA_mask_overrides_references':cache['EA_mask_overrides_references'],'manual_review_list_created':False})}
            else:result=Original.finish_stage(current,stage,stage_root,reports)
            if purpose=='normalization_moments':
                ref=result['winsorized_statistics_reference'];value=I.load_data(ref);value.update(geometry_source='uff_sprime',Pprime_status='INDEPENDENT_TRAIN_STATISTICS');result['winsorized_statistics_reference']=I.save(ref['path'],value)
                ref=result['molecule_field_means_reference'];value=I.load_data(ref);value['geometry_source']='uff_sprime';result['molecule_field_means_reference']=I.save(ref['path'],value)
            state['results'].update(result)
            if'query_stage_reference'not in result:
                state['purpose_index']+=1;state['results'].pop('query_stage_reference',None)
            state['active_stage']=None;state['groups']={};I.save(checkpoint,state)
    manifest={'schema':'FINAL_COMMON_TRAIN_PPRIME_NORMALIZATION_V1','status':'PPRIME_INDEPENDENT_TRAIN_STATISTICS_COMPLETE',
        'fit_role':'TRAIN','VAL_or_FULL_used_for_fitting':False,'D5_actual_UFF_bases_and_all_task_views_excluded':True,
        'geometry_source':'uff_sprime','source_projection':I.ref(Path(plan['output'])/'projection/manifest.json'),
        'statistics':state['results'],'full_second_statistics_pass_performed':False,'independent_numeric_replay_equal':None,
        'content_hashes_computed':False,'source_labels_modified':False,'normalization_independent_from_PM7':True,
        'mathematics':'Original TSQR256 / ordered logical source-job reduction / exact type7 .001/.999 / WinsorMoments / median MAD',
        'radix_passes_are_algorithmic_refinement_not_QA':True,'field_mask_counts':cache['field_mask_counts'],'EA_mask_overrides_references':cache['EA_mask_overrides_references']}
    I.save(root/'manifest.json',manifest)
    I.save(Path(plan['output'])/'delivery_manifest.json',{'files':[dict(r,records=1)for r in state['results'].values()if isinstance(r,dict)and'path'in r]})
    return manifest


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);a=parser.parse_args();plan=I.load(a.plan)
    P.need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')and plan.get('workers',16)<=int(os.environ['SLURM_CPUS_PER_TASK']),'ACTUAL_MAIN_CPU_ALLOCATION')
    cache=P.build(plan);print(json.dumps(fit(plan,cache)),flush=True)

if __name__=='__main__':main()