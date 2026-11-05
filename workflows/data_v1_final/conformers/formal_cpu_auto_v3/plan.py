"""CPU census/import draft, explicit finite-wave freeze and unstarted continuation."""
from __future__ import annotations
import argparse,collections,json,pathlib,sys
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as C,runtime_io as R

OPTIONS=('config','root-preflight','quota-reuse-review','pilot-review','draft','wave-review','closed-batch','output')


def write_rows(path,rows):
    import pyarrow as pa
    return R.write_parquet_new(path,pa.Table.from_pylist(rows))


def draft(args,value,proof,config_reference):
    import duckdb
    import pyarrow as pa
    review_ref=R.input_ref(args.root_preflight,args.pilot_review);review,report,parents=C.pilot_review(review_ref)
    R.authorized(proof,[review['closure_report'],review['terminal_outcomes'],review['pilot_tasks'],review['actual_accounting']])
    tasks={}
    with C.pinned(review['pilot_tasks'],C.CAP).open() as stream:
        for line in stream:
            task=json.loads(line);mid=task['meta']['molecule_id'];C.need(mid not in tasks,'DUPLICATE_PILOT_TASK');tasks[mid]=task
    outcomes=C.read(review['terminal_outcomes']);C.need(len(tasks)==len(outcomes)==336,'FULL336_TASK_AND_TERMINAL_METADATA_REQUIRED')
    by_mid={row['molecule_id']:row for row in outcomes};C.need(len(by_mid)==336 and set(by_mid)==set(tasks),'EXACT336_ORIGINAL_TASK_UNION_REQUIRED')
    packages=[row['package_reference'] for row in outcomes if row['science_result_observed']]
    C.need(len(packages)==334 and sum(row['package_reference'] is None for row in outcomes)==2,'334_REAL_PACKAGES_TWO_UNKNOWN_NO_EMPTY_PACKETS')
    R.authorized(proof,packages)
    # Whole compressed SHA, EOF/CRC and float64 selected-geometry SHA are checked
    # on this CPU allocation. No optimizer or QM is initialized for planning.
    for row in outcomes:
        task=tasks[row['molecule_id']]
        C.need(C.sha_value(task)==row['original_task_sha256'] and C.seed_for(row['molecule_id'],row['cohort']=='retry_once')==row['original_task_seed'],
            'CLOSED_TASK_BYTES_OR_SEED_CHANGED')
        if row['package_reference'] is not None:
            packet=R.read_packet(row['package_reference'],value)
            C.need(packet['summary']['molecule_id']==row['molecule_id'] and packet['summary']['status']==row['scientific_status'],
                'REAL_PACKAGE_ID_OR_SCIENTIFIC_STATUS_CHANGED')
    roles_ref,parts=R.authority_roles(value);R.authorized(proof,[value['per_molecule']]);C.pinned(value['per_molecule'])
    db=duckdb.connect();db.execute('SET threads=16');db.execute("SET memory_limit='12GB'")
    db.execute('CREATE VIEW p AS SELECT * FROM read_parquet('+C.q(value['per_molecule']['path'])+')')
    db.execute('CREATE VIEW r AS SELECT * FROM read_parquet(['+','.join(C.q(ref['path']) for ref in parts)+'])')
    C.need(db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM p').fetchone()==(1220466,1220466),'PER_MOLECULE_SOURCE_POPULATION_CHANGED')
    C.need(db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM r').fetchone()==(1220466,1220466),'ROUTINE_ROLE_POPULATION_CHANGED')
    rows=db.execute('''SELECT p.*,r.file_group,r.records,r.source_role,r.effective_role
        FROM p JOIN r USING(molecule_id) WHERE p.Sprime_conformers<p.S_conformers
        ORDER BY r.file_group,p.molecule_id''').fetch_arrow_table().to_pylist()
    C.need(len(rows)==len({row['molecule_id'] for row in rows})==99351,'EXACT_ORIGINAL99351_DEFICITS_REQUIRED')
    ids={row['molecule_id'] for row in rows};imports=[];unsupported=[];unstarted=[];controls=[]
    for row in rows:
        mid=row['molecule_id'];kind=C.cohort(row)
        C.need(row['records']==row['S_conformers'] and row['split_role']==row['source_role'],'FROZEN_SOURCE_ROLE_OR_PM7_COUNT_CHANGED')
        row.update(cohort=kind,expected_conformers=int(row['S_conformers']),task_key=C.task_key(mid,kind),max_heavy_atoms=int(row['heavy_atoms']))
        if kind=='unsupported':unsupported.append(row);continue
        if mid in by_mid:
            outcome=by_mid[mid];C.need(outcome['cohort']==kind and tasks[mid]['meta']['expected_conformers']==row['expected_conformers'],
                'PILOT_DEFICIT_COHORT_N_CHANGED')
            imports.append(C.import_outcome(outcome,tasks[mid],review['closure_report'],value['recipe_config']))
        else:unstarted.append(row)
    for mid,outcome in by_mid.items():
        if mid not in ids:
            C.need(outcome['cohort']=='enough_control' and tasks[mid]['meta']['Sprime_conformers']>=tasks[mid]['meta']['S_conformers'],
                'ONLY_ORIGINAL_ENOUGH_CONTROLS_MAY_BE_OUTSIDE_DEFICITS');controls.append(outcome)
    C.need(len(unsupported)==9282 and len(imports)==320 and len(controls)==16 and len(unstarted)==89749
        and sum(not row['science_result_observed'] for row in imports)==2 and sum(row['science_result_observed'] for row in imports)==318,
        'EXACT9282_UNSUPPORTED_318_PACKAGE2_UNKNOWN_16_CONTROLS_89749_UNSTARTED_CONSERVATION')
    C.need({row['molecule_id'] for row in imports}.isdisjoint({row['molecule_id'] for row in unstarted}), 'CONSUMED_AND_UNSTARTED_OVERLAP')
    out=R.OUT;(out/'task_shards').mkdir();batches=[]
    for start in range(0,len(unstarted),value['max_molecules_per_batch']):
        chunk=unstarted[start:start+value['max_molecules_per_batch']];bid='batch-%05d'%len(batches)
        reference=write_rows(out/'task_shards'/(bid+'.parquet'),chunk)
        batches.append({'batch_id':bid,'tasks':reference,'molecules':len(chunk),'estimated_core_hours':None})
    original=write_rows(out/'original_deficits.parquet',rows);excluded=write_rows(out/'unsupported.parquet',unsupported)
    imports_ref=R.write_json_new(out/'pilot_consumed_imports.json',imports);control_ref=R.write_json_new(out/'enough_controls16.json',controls)
    result={'schema':C.SCHEMAS['draft'],'status':'DRAFT_NOT_AUTHORITY_TO_RUN','config':config_reference,'pilot_review':review_ref,
        'kernel_sha256':C.KERNEL_SHA,'recipe_config':value['recipe_config'],'roles_manifest':roles_ref,'role_parts':parts,
        'original_deficits':original,'unsupported':excluded,'pilot_imports':imports_ref,'enough_controls':control_ref,
        'original_deficit_molecules':99351,'unsupported_molecules':9282,'non_unsupported_deficits':90069,
        'historical_consumed_deficit_molecules':320,'unstarted_planned_molecules':89749,'enough_controls_not_population':16,
        'same_seed_controls_not_population':14,'batches':batches,'full_forecast_status':C.FORECAST,
        'estimated_full_core_hours':None,'bounded_package_times_are_descriptive_only':True,
        'pilot_scientific_success_packages':102,'pilot_scientific_failure_packages':232,'execution_unresolved_imported':2,
        'actual_historical_parent_ids':sorted(parents),'runtime':{'job_id':str(proof['job_id']),'uid':1278,'node':proof['node']},
        'formal_generation_authorized':False,'common_frozen':False,'original_data_modified':False}
    R.write_json_new(out/'draft.json',result);db.close()


def freeze(args,value,proof,config_reference):
    draft_ref=R.input_ref(args.root_preflight,args.draft);data=C.read(draft_ref);approval_ref=R.input_ref(args.root_preflight,args.wave_review)
    C.need(data['schema']==C.SCHEMAS['draft'] and data['status']=='DRAFT_NOT_AUTHORITY_TO_RUN' and data['config']==config_reference,
        'MATCHING_CPU_DRAFT_REQUIRED')
    review=C.approve_wave(draft_ref,data,approval_ref,config_reference);C.pilot_review(data['pilot_review'])
    R.authorized(proof,[data['pilot_review'],data['pilot_imports'],data['original_deficits'],data['unsupported']])
    imports=C.read(data['pilot_imports']);C.need(len(imports)==320 and len({r['task_key'] for r in imports})==320,'EXACT320_ONCE_IMPORTS_REQUIRED')
    for row in imports:R.import_once(row)
    # Only after all320 imports reread exactly may a frozen plan be emitted.
    for row in imports:C.need(C.read(C.ref(C.ledger_path(row['task_key'])))==row,'ONCE_IMPORT_NOT_DURABLE_OR_CONFLICTING')
    selected={j['batch_id'] for j in review['jobs']};batches=[b for b in data['batches'] if b['batch_id'] in selected]
    R.authorized(proof,[b['tasks'] for b in batches])
    for batch in batches:C.pinned(batch['tasks'])
    result={'schema':C.SCHEMAS['plan'],'status':'BOUNDED_WAVE_FROZEN_IMPORTS_CLOSED','config':config_reference,
        'draft':draft_ref,'root_review':approval_ref,'batches':batches,'jobs':review['jobs'],'pilot_imports':data['pilot_imports'],
        'original_deficits':data['original_deficits'],'unsupported':data['unsupported'],'pilot_review':data['pilot_review'],
        'root_draft':data.get('root_draft',draft_ref),'parent_plan':data.get('parent_plan'),
        'requested_allocation_core_seconds_ceiling':review['requested_allocation_core_seconds_ceiling'],
        'full_forecast_status':C.FORECAST,'estimated_full_core_hours':None,'maximum_concurrent_jobs':review['maximum_concurrent_jobs'],
        'imports320_durably_verified':True,'formal_generation_authorized':'ONLY_LISTED_FINITE_WAVE',
        'common_frozen':False,'runtime':{'job_id':str(proof['job_id'])}}
    R.write_json_new(R.OUT/'plan.json',result)


def continuation(args,value,proof,config_reference):
    reference=R.input_ref(args.root_preflight,args.closed_batch);closed=C.read(reference)
    C.need(closed['schema']=='SPRIME_FORMAL_CPU_CLOSED_BATCH_V3' and closed['status']=='ACTUAL_TERMINAL_BATCH_CLASSIFIED',
        'REAL_TERMINAL_CLOSE_REQUIRED_NOT_PARENT_C0_ASSUMPTION')
    R.authorized(proof,[closed['unstarted_metas'],closed['plan']]);C.pinned(closed['unstarted_metas'])
    import pyarrow.parquet as pq
    rows=pq.read_table(closed['unstarted_metas']['path']).to_pylist()
    C.need(rows and all(not C.ledger_path(row['task_key']).exists() for row in rows),'ONLY_PROVEN_NEVER_DISPATCHED_TASKS_CAN_CONTINUE')
    plan=C.read(closed['plan']);base=C.read(plan['draft']);C.need(plan['config']==config_reference,'SAME_SCIENCE_CONFIG_REQUIRED')
    bid='cont-'+closed['batch_id']+'-'+reference['sha256'][:8]
    shard=write_rows(R.OUT/(bid+'.parquet'),rows)
    base.update(root_draft=plan['root_draft'],parent_plan=closed['plan'],continuation_close_reference=reference,
        batches=[{'batch_id':bid,'tasks':shard,'molecules':len(rows),'estimated_core_hours':None}],
        unstarted_planned_molecules=len(rows),formal_generation_authorized=False)
    R.write_json_new(R.OUT/'draft.json',base) # a NEW Root finite-wave approval is still required


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('draft','freeze','continuation'))
    for name in OPTIONS:p.add_argument('--'+name,type=pathlib.Path,required=name in {'config','root-preflight','quota-reuse-review','output'})
    args=p.parse_args();stage='draft' if args.mode=='continuation' else args.mode
    value,proof,session,config_ref=R.admit(__file__,args,stage,OPTIONS);R.new_output_directory(args.output,value)
    budget=R.Budget(proof,session,value,R.OUT);C.need(budget.observe() is None,'FRESH_ACCOUNT_QUOTA_REQUIRED_BEFORE_CPU_SOURCE_READ')
    budget.start_monitor()
    try:{'draft':draft,'freeze':freeze,'continuation':continuation}[args.mode](args,value,proof,config_ref)
    finally:
        budget.close_monitor();R.write_json_new(R.OUT/'resource_observations.json',budget.report())


if __name__=='__main__':main()
