"""Direct full TRAIN fit: original TSQR, exact tails, moments and median/MAD once."""
import argparse,collections,concurrent.futures as cf,json,multiprocessing as mp,os,pathlib
from . import io as I,statistics as T,eligibility as E
from .reader import need
B=T.B
P=pathlib.Path
ROUTES=('element_reference','normalization_quantiles','normalization_moments','diagnostic_median_MAD')


def histogram_rows(reports,name):
    import pyarrow.parquet as pq
    merged=collections.Counter()
    for report in reports:
        if report['radix_histogram'] is None:continue
        table=pq.ParquetFile(I.require(report['radix_histogram']))
        try:
            for batch in table.iter_batches(batch_size=8192,use_threads=False):
                for row in batch.to_pylist():
                    if row['query']==name:merged[(row['field_id'],row['node_id'],row['prefix_bits'],int(row['prefix']))]+=row['n']
        finally:table.close()
    return [{'field_id':f,'node_id':n,'prefix_bits':b,'prefix':p,'n':v} for (f,n,b,p),v in sorted(merged.items())]


def finish_stage(cfg,stage,root,reports):
    fields=I.load_data(cfg['field_map_reference']);purpose=cfg['statistics_purpose']
    result={};queries={};finished={key:list(value) for key,value in stage['finished'].items()}
    if purpose=='element_reference':
        models={str(f['field_id']):B.merge_qr([report['energy_TSQR'][str(f['field_id'])] for report in reports]) for f in fields if f['element_reference_eligible']}
        result['element_models_reference']=I.save(root/'element_models.json',models)
        counts=collections.defaultdict(collections.Counter)
        for report in reports:
            for fid,value in report['field_counts'].items():counts[fid].update(value)
        result['r73_derived_reference']=I.save(root/'r73_derived.json',{'files':[report['r73_derived_reference'] for report in reports if report.get('r73_derived_reference')], 'definition':'USER_APPROVED_20261105_PURE_SIGMA_SIGMA_PI_PI_BLOCKS', 'raw_r73_unchanged':True, 'raw_r73_statistics_are_source_K_entry_statistics_not_training_pair_sums':True})
        result['mask_overrides_reference']=I.save(root/'mask_overrides.json',{'files':[report['mask_override_reference'] for report in reports if report.get('mask_override_reference')], 'predicate':'Existing abs(EA)>10eV flag AND convergence not explicitly True', 'original_values_modified':False, 'original_record_and_atomic_mask_catalog':I.load_data(cfg['coverage_reference'])['parts_catalog'], 'rule_records':sum(report['mask_override_reference'].get('records',0) for report in reports if report.get('mask_override_reference')), 'newly_masked_records':sum(report['mask_override_reference'].get('newly_masked_records',0) for report in reports if report.get('mask_override_reference'))})
        result['validity_mask_counts_reference']=I.save(root/'validity_mask_counts.json',{
            'fields':{fid:dict(value) for fid,value in counts.items()},'new_mask_fraction_is_report_only':True,
            'physical_and_convergence_masks_reused':True,'manual_review_list_created':False})
        return result
    for name,query in stage['queries'].items():
        next_query,done=B.advance(query,histogram_rows(reports,name))
        key=query['purpose'] if name=='raw' else name;finished[key].extend(done)
        if next_query['fields']:queries[name]=next_query
    if purpose=='diagnostic_median_MAD' and not queries:
        if stage['queries']['raw']['purpose']=='median':
            queries={'raw':B.initial_queries(fields,'MAD',{row['field_id']:row['value'] for row in finished['median'] if row['value'] is not None})}
        else:
            med={row['field_id']:row for row in finished['median']};mad={row['field_id']:row for row in finished['MAD']}
            values={str(field['field_id']):{'median':med[field['field_id']]['value'],'MAD':mad.get(field['field_id'],{}).get('value'),
                'TRAIN_n':med[field['field_id']]['n'],'MAD_n':mad.get(field['field_id'],{}).get('n',0)} for field in fields}
            result['diagnostic_median_MAD_reference']=I.save(root/'diagnostic_median_MAD.json',{'fields':values,'purpose':'TRAIN_DIAGNOSTIC_MEDIAN_MAD','fit_role':'TRAIN'})
    if purpose=='normalization_quantiles' and not queries:
        result['exact_tail_reference']=I.save(root/'exact001_999.json',{
            'coverage_reference':cfg['coverage_reference'],'field_map_reference':cfg['field_map_reference'],
            'eligibility_reference':cfg['eligibility_reference'],'input_release_reference':cfg['input_release_reference'],
            'element_models_reference':cfg['element_models_reference'],'catalog':stage['catalog'],
            'quantiles':T.exact_tails(stage['catalog'],finished),'source_labels_modified':False})
    if purpose=='normalization_moments':
        result['winsorized_statistics_reference']=I.save(root/'winsorized_statistics.json',T.moment_result(stage,reports,fields))
        result['molecule_field_means_reference']=I.save(root/'molecule_field_means.json',{'files':[report['molecule_field_means_reference'] for report in reports if report.get('molecule_field_means_reference')], 'fit_role':'TRAIN', 'geometry_source':'pm7', 'scope':'Per-molecule field valid-leaf mean; produced during the existing moments source stream'})
    if queries:
        result['query_stage_reference']=I.save(root/'next_query.json',{
            'coverage_reference':cfg['coverage_reference'],'field_map_reference':cfg['field_map_reference'],
            'eligibility_reference':cfg['eligibility_reference'],'input_release_reference':cfg['input_release_reference'],
            'statistics_purpose':purpose,'element_models_reference':cfg.get('element_models_reference'),
            'queries':queries,'finished':finished})
    return result


def configuration(args):
    coverage=I.load(args.coverage)
    from ..window2_r73_views_v1.kernel import derived_fields
    original=I.load_data(coverage['field_map_reference']);fields=original+derived_fields(original)
    fieldpath=P(args.output)/'normalization_view_fields.json'
    if fieldpath.is_file():need(I.load(fieldpath)==fields,'FROZEN_EXTENDED_NORMALIZATION_VIEW_FIELDS')
    else:I.save(fieldpath,fields)
    return {'mode':'full','coverage_reference':I.ref(args.coverage),'common_reference':I.ref(args.common),
        'd5_reference':I.ref(args.d5),'input_release_reference':I.ref(args.common),
        'canonical_index':coverage['canonical_index'],'field_map_reference':I.ref(fieldpath),
        'logical_group_plan_reference':coverage['logical_group_plan_reference'],
        'source_inventory_reference':coverage['source_inventory_reference'],
        'element_basis':coverage['element_basis'],'source_records':coverage['records'],'workers':args.workers,
        'element_models_reference':None,'exact_tail_reference':None,'query_stage_reference':None}


def run(args):
    root=P(args.output);root.mkdir(parents=True,exist_ok=True);cfg=configuration(args)
    workers=cfg['workers']
    need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID') and workers<=int(os.environ['SLURM_CPUS_PER_TASK']),'REAL_MAIN_CPU_ALLOCATION')
    checkpoint=root/'checkpoint.json'
    if checkpoint.is_file():
        state=I.load(checkpoint);need(state['inputs']==cfg,'RESUME_ORIGINAL_CLOSED_INPUTS_ONLY')
    else:
        state={'inputs':dict(cfg),'purpose_index':0,'pass_index':0,'active_stage':None,'groups':{},'results':{}}
        eligibility=E.build(cfg,root/'eligibility');state['eligibility']=eligibility;I.save(checkpoint,state)
    groups=I.load_data(cfg['logical_group_plan_reference'])['groups'];fields=I.load_data(cfg['field_map_reference'])
    need(len({group['source_job_id'] for group in groups})==len(groups),'ORIGINAL_UNSPLIT_LOGICAL_GROUPS')
    cfg['eligibility_reference']=state['eligibility']['eligibility_reference']
    with cf.ProcessPoolExecutor(max_workers=workers,mp_context=mp.get_context('spawn')) as pool:
        while state['purpose_index']<len(ROUTES):
            purpose=ROUTES[state['purpose_index']];current=dict(cfg,statistics_purpose=purpose)
            current.update({key:value for key,value in state['results'].items() if key in ('element_models_reference','exact_tail_reference','query_stage_reference','mask_overrides_reference','r73_derived_reference')})
            if state['active_stage'] is None:
                state['pass_index']+=1;stage_root=root/('pass_%04d'%state['pass_index']);stage_root.mkdir()
                stage=T.initial_stage(current,fields);stage['element_basis']=cfg['element_basis']
                state['active_stage']=I.save(stage_root/'stage.json',stage);state['groups']={};I.save(checkpoint,state)
            else:
                stage=I.load_data(state['active_stage']);stage_root=P(state['active_stage']['path']).parent
            attempt=0
            while (stage_root/('attempt_%03d'%attempt)).exists():attempt+=1
            attempt_root=stage_root/('attempt_%03d'%attempt);attempt_root.mkdir()
            pending={}
            group_cfg=current
            if getattr(args,'group_scratch_root',None) and state['pass_index']>=getattr(args,'scratch_from_pass',1):
                group_cfg=dict(current,group_scratch_root=args.group_scratch_root,
                    group_producer_inputs={'inputs':state['inputs'],'stage_reference':state['active_stage'],
                        'eligibility_reference':current['eligibility_reference'],
                        'upstream_statistics':{name:current.get(name) for name in ('element_models_reference','exact_tail_reference','query_stage_reference','mask_overrides_reference','r73_derived_reference')}})
            for group in groups:
                key=str(group['group_index'])
                if key not in state['groups']:pending[pool.submit(T.group_pass,(group_cfg,stage,str(attempt_root),group))]=key
            errors=[]
            for future in cf.as_completed(pending):
                key=pending[future]
                try:state['groups'][key]=future.result()
                except BaseException as error:errors.append({'group_index':key,'error':repr(error)})
                I.save(checkpoint,state)
                print(json.dumps({'purpose':purpose,'pass':state['pass_index'],'closed_groups':len(state['groups']),'total_groups':len(groups),'errors':errors}),flush=True)
            if errors:raise ValueError('STATISTIC_GROUP_ERRORS:'+repr(errors))
            reports=[I.load_data(state['groups'][str(group['group_index'])]) for group in groups]
            result=finish_stage(current,stage,stage_root,reports);state['results'].update(result)
            if 'query_stage_reference' not in result:
                state['purpose_index']+=1;state['results'].pop('query_stage_reference',None)
            state['active_stage']=None;state['groups']={};I.save(checkpoint,state)
    manifest={'schema':'FULL_COMMON_TRAIN_NORMALIZATION_V1','status':'PM7_P_D_TRAIN_STATISTICS_COMPLETE',
        'fit_role':'TRAIN','VAL_used_for_fitting':False,'pilot_only':False,'full_second_statistics_pass_performed':False,
        'independent_numeric_replay_equal':None,'source_labels_modified':False,'content_hashes_computed':False,
        'inputs':cfg,'eligibility':state['eligibility'],'statistics':state['results'],
        'physical_statistical_algorithms':'Original TSQR256, original logical-group ordered reduction, exact type7 .001/.999, WinsorMoments, median/MAD',
        'radix_passes_are_algorithmic_refinement_not_an_independent_replay':True,
        'Pprime_status':'SEPARATE_INDEPENDENT_DATASET_NOT_SUBSTITUTED_BY_PM7_STATISTICS'}
    I.save(root/'manifest.json',manifest)
    I.save(root/'delivery_manifest.json',{'files':[dict(ref,records=1) for ref in state['results'].values() if isinstance(ref,dict) and 'path' in ref]})
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('coverage','common','d5','output'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--workers',type=int,default=16)
    parser.add_argument('--group-scratch-root',help='optional node-local group output; shared output/checkpoint stay authoritative')
    parser.add_argument('--scratch-from-pass',type=int,default=1,help='first future pass index using local group output')
    args=parser.parse_args()
    print(json.dumps(run(args),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
