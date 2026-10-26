"""Actual CPU recount of the Root-reviewed N1 mother and original-rule valid32."""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,pathlib,sys,tempfile,time,traceback
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.n1_pprime2_pilot_v3 import contract as C,core,io as I
WORK={}


def q(value):return "'"+str(value).replace("'","''")+"'"


def init_validation(catalog_ref,admission):
    global WORK
    catalog=C.load_catalog(catalog_ref)
    I.active_parent_continuation(admission,C.PREP_SCOPE_KEY,C.PREP_SCOPE,'analysis')
    os.environ.update({key:'1' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
    refs=catalog['references'];original_io=C.module_from_pin('_n1_prep_original_io',refs['io'])
    recipe=original_io.load_config(C.pinned_small(refs['recipe']))
    if 'prepare' in sys.modules:C.need(pathlib.Path(sys.modules['prepare'].__file__).absolute()==pathlib.Path(refs['legacy_prepare_import']['path']),'WRONG_PREPARE_MODULE_ALREADY_IMPORTED')
    science=original_io.load_science(recipe);science.worker_init()
    from rdkit import rdBase
    C.need(original_io.version_tuple(rdBase.rdkitVersion)==(2025,9,5),'ORIGINAL_RDKIT_REQUIRED_FOR_PREP_GRAPH_STEREO')
    WORK={'io':original_io,'science':science}


def validate_original(item):
    """Read one original PM7 payload and baseline; never embed/minimize/QM."""
    import numpy as np
    science=WORK['science'];original_io=WORK['io'];mid=item['meta']['molecule_id']
    result={'molecule_id':mid,'status':'PENDING','reason':None,'new_UFF_calls':0,'new_QM_calls':0}
    phase='BASELINE_AND_SEED_METADATA'
    try:
        pointer=item['records'][0];old=item['baseline'];seed=C.proposed_seed(mid)
        C.need(len(item['records'])==1 and old['molecule_id']==mid and old['status']=='SUCCESS'
            and old['converged'] is True and old['sprime_conf_idx']==0,'ONE_REAL_ORIGINAL_BASELINE_REQUIRED')
        C.need(type(old['seed']) is int and seed!=old['seed'],'NEW_SEED_COLLISION_WITH_OLD_BASELINE')
        phase='ORIGINAL_PM7_PAYLOAD_AND_ENERGY';raw=science.read(pointer);energy=science.field(raw,'energy')
        C.need(energy is not None and np.isfinite(float(science.plain(energy).reshape(-1)[0])),'PM7_MINIMUM_ENERGY_MISSING')
        phase='ORIGINAL_PM7_GRAPH_AND_STEREO';mol,numbers,pm7_xyz=science.graph(raw);source,signature=science.fix_stereo(mol,str(science.field(raw,'smiles')))
        atom_sha=hashlib.sha256(numbers.astype('<i8').tobytes()).hexdigest()
        phase='BASELINE_ATOM_ANCHOR_STEREO_GEOMETRY_IDENTITY'
        C.need(old['atom_order_sha256']==atom_sha and old['source_record_id']==pointer['record_id'],'BASELINE_SOURCE_ANCHOR_OR_ATOM_ORDER_CHANGED')
        C.need(old['stereo_signature']==signature,'BASELINE_SOURCE_STEREO_SIGNATURE_CHANGED')
        geometry_sha=original_io.geometry_sha(numbers,old['coordinates'])
        C.need(old.get('geometry_sha256',geometry_sha)==geometry_sha and np.isfinite(float(old['uff_energy_kcal_mol'])),'BASELINE_GEOMETRY_OR_ENERGY_INVALID')
        phase='BASELINE_NATIVE_GEOMETRY_STEREO';cid=core._add_conformer(mol,old['coordinates'])
        try:C.need(science.check_geometry_stereo(mol,cid),'BASELINE_GEOMETRY_STEREO_INVALID')
        finally:mol.RemoveConformer(cid)
        result.update(status='ORIGINAL_SOURCE_AND_BASELINE_VALIDATED_NO_NEW_UFF',reason=None,seed=seed,
            baseline_row_sha256=C.sha_value(old),baseline_geometry_sha256=geometry_sha,
            pm7_geometry_sha256=original_io.geometry_sha(numbers,pm7_xyz),atom_order_sha256=atom_sha,
            ordered_graph_sha256=C.sha_value(science.ordered_graph(mol)),stereo_source=source,stereo_signature=signature,
            atomic_numbers=numbers.tolist(),original_payload_sha256=pointer['record_payload_sha256'])
    except Exception as exc:result.update(reason=phase+':'+type(exc).__name__,error_full=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
    return result


def mother_aggregation(metas,inventory,expected,correction_ref,phase,usability_semantics_provenance):
    """Every mother contributes once to each joint/marginal; no role filtering."""
    meta_by_mid={row['molecule_id']:row for row in metas}
    C.need(len(meta_by_mid)==len(metas)==len(inventory) and {row['molecule_id'] for row in inventory}==set(meta_by_mid)
        and len({row['molecule_id'] for row in inventory})==len(inventory),'MOTHER_AGGREGATE_EXACT_ROW_IDENTITY_CONSERVATION')
    dimensions=('source_role','effective_role','Sprime_status','Sprime_usable_equals_source_N',
        'original_Sprime_usable_count','pm7_S_usable_equals1','pm7_S_usable_count',
        'physical_original_Sprime_usable_count','metadata_eligibility_reason','final_status','final_reason')
    joint=collections.Counter();strata=collections.Counter();marginals={name:collections.Counter() for name in dimensions}
    for item in inventory:
        meta=meta_by_mid[item['molecule_id']]
        values=(meta.get('source_role'),meta.get('effective_role'),meta.get('Sprime_status'),
            meta.get('Sprime_conformers')==meta['S_conformers'],meta.get('Sprime_conformers'),
            meta.get('S_usable_conformers')==1,meta.get('S_usable_conformers'),item['actual_usable_baseline_rows'],
            item['metadata_eligibility_reason'],item['status'],item['reason'])
        joint[values]+=1;strata[values[:4]]+=1
        for name,value in zip(dimensions,values):marginals[name][value]+=1
    ordered=lambda rows:sorted(rows,key=lambda values:C.canonical(list(values)))
    joint_rows=[dict(zip(dimensions,values),molecules=joint[values]) for values in ordered(joint)]
    strata_rows=[dict(zip(dimensions[:4],values),molecules=strata[values]) for values in ordered(strata)]
    marginal_rows={name:[{'value':key,'molecules':counter[key]} for key in sorted(counter,key=lambda value:C.canonical(value))]
        for name,counter in marginals.items()}
    count=len(inventory);totals={name:sum(counter.values()) for name,counter in marginals.items()}
    C.need(sum(row['molecules'] for row in joint_rows)==sum(row['molecules'] for row in strata_rows)==count and all(n==count for n in totals.values()),
        'EVERY_JOINT_AND_MARGINAL_COUNT_MUST_CONSERVE_ALL_MOTHER_ROWS')
    return {'schema':'N1_PPRIME2_ROLE_STATUS_USABLE_AUDIT_V3','status':'ALL_OBSERVED_MOTHER_COUNTS_CONSERVED',
        'phase':phase,'count_correction_authority':correction_ref,'mother_count':count,'expected_mother_count':expected,
        'usability_semantics_provenance':usability_semantics_provenance,
        'mother_count_matches_reviewed_source':count==expected,'mother_unique_ids':len(meta_by_mid),
        'mother_definition':'original per_molecule S_conformers=1, no role filter',
        'Sprime_usable_equals_source_N_definition':'original per_molecule Sprime_conformers==S_conformers; mother source_N remains1',
        'original_Sprime_usable_count_definition':'producer Sprime_conformers counts original rows status SUCCESS AND converged IS TRUE',
        'pm7_S_usable_count_definition':'producer S_usable_conformers counts original PM7 geometry with nonempty atomic_numbers; never an Sprime count',
        'pm7_S_usable_equals1_definition':'metadata S_usable_conformers==1; separate PM7 S eligibility condition',
        'physical_original_Sprime_usable_count_definition':'fresh original baseline Parquet row status SUCCESS and converged is True',
        'joint_dimensions':list(dimensions),'joint_counts':joint_rows,'joint_total':sum(joint.values()),
        'role_status_strictusable_joint_dimensions':list(dimensions[:4]),
        'role_status_strictusable_joint_counts':strata_rows,'role_status_strictusable_joint_total':sum(strata.values()),
        'marginals':marginal_rows,'marginal_totals':totals,
        'metadata_eligible_rows':sum(item['metadata_eligibility_reason'] is None for item in inventory),
        'physically_validated_rows':sum(item['status']=='ORIGINAL_SOURCE_AND_BASELINE_VALIDATED_NO_NEW_UFF' for item in inventory),
        'all_mother_ids_sha256':C.sha_value(sorted(meta_by_mid)),
        'legacy_expected_count':5040,'legacy_count_has_independent_source_measurement':False,
        'legacy_difference65_source_row_membership':None,'difference65_not_preassigned_to_any_reason':True,
        'common':False,'pilot_membership':False,'production_membership':False,'final_common_reference':None,
        'new_UFF_calls':0,'new_QM_calls':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__);options=('formal-config','root-preflight','output')
    for name in options:parser.add_argument('--'+name,type=pathlib.Path,required=True)
    a=parser.parse_args();formal_ref=I.request_ref(a.root_preflight,a.formal_config)
    proof,catalog,admission=I.admit(__file__,a,options,C.PREP_SCOPE_KEY,C.PREP_SCOPE,'analysis',[formal_ref])
    correction_ref=catalog['count_correction_authority_reference'];correction=C.load_count_correction(correction_ref)
    expected=correction['expected_source_pm7_n1_molecules']
    out=I.new_output(a.output);budget=I.Budget(proof,out,rss_cap=32<<30);started=time.monotonic()
    config=I.read(formal_ref);C.need(config['schema']=='DATA_V1_SPRIME_FORMAL_V1','READ_ONLY_ORIGINAL_FORMAL_METADATA_REQUIRED')
    C.need(config['per_molecule']==correction['per_molecule_reference'],'COUNT_REVIEW_AND_CURRENT_PER_MOLECULE_PIN_MUST_MATCH')
    metadata_refs=[config[name] for name in ('per_molecule','roles_authority','formal_source_receipt','sprime_manifest')]
    I.authorized(proof,metadata_refs)
    roles_authority=I.read(config['roles_authority']);roles_ref=roles_authority['source_role_manifest']
    I.authorized(proof,[roles_ref,roles_authority['actual_closure']]);roles=I.read(roles_ref)
    C.need(roles_authority['status']=='FROZEN' and roles_authority['validation_source']=='ROUTINE'
        and roles['status']=='ROUTINE_MOLECULE_VAL_ROLES_FROZEN','REAL_FROZEN_ROUTINE_ROLES_REQUIRED')
    role_parts=[{key:row[key] for key in ('path','bytes','sha256')} for row in roles['outputs'] if '/molecule_roles/' in row['path']]
    C.need(len(role_parts)==16,'ALL16_ACTUAL_ROLE_PARTS_REQUIRED')
    source_receipt=I.read(config['formal_source_receipt']);C.need(source_receipt['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED','ORIGINAL_INDEX_CLOSED_PIN_REQUIRED')
    pointer_refs=[row['reference'] for row in source_receipt['outputs'] if row['name']=='formal_population']
    C.need(len(pointer_refs)==1,'UNIQUE_ORIGINAL_CANONICAL_POINTER_INDEX_REQUIRED');pointer_ref=pointer_refs[0]
    sprime=I.read(config['sprime_manifest']);C.need(sprime['status']=='FULL_DATASET_ACCEPTED','ORIGINAL_SPRIME_DATASET_ACCEPTANCE_REQUIRED')
    baseline_refs=[{key:row[key] for key in ('path','bytes','sha256')} for row in sprime['references'] if row['kind']=='conformers']
    C.need(len(baseline_refs)==5,'ALL5_ORIGINAL_BASELINE_PARTS_REQUIRED')
    actual_inputs=[*metadata_refs,roles_ref,roles_authority['actual_closure'],*role_parts,pointer_ref,*baseline_refs]
    unique={row['path']:row for row in actual_inputs};I.authorized(proof,list(unique.values()))
    checks=[]
    # Hash all five original baseline parts on the actual allocation. A source
    # manifest/size alone is not promoted to a fresh scientific source hash.
    with cf.ThreadPoolExecutor(max_workers=16) as hashes:
        futures={hashes.submit(I.source_check,row):row for row in unique.values()}
        for future in cf.as_completed(futures):checks.append(future.result())
    source_check_ref=I.json_new(out/'source_sha_validation.json',{'status':'ALL_ACTUAL_SOURCE_SHA_VERIFIED',
        'runtime':{'job_id':str(proof['job_id']),'uid':os.getuid(),'allocated_cpus':16},'inputs':checks},[out])
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(16);pa.set_io_thread_count(4)
    with tempfile.TemporaryDirectory(prefix='n1p2_prepare_'+str(proof['job_id'])+'_',dir='/tmp') as scratch:
        # Temporary spill bytes are included in the same whole-stage cap.
        budget.roots.append(pathlib.Path(scratch));db=duckdb.connect()
        db.execute('SET threads=16');db.execute("SET memory_limit='6GB'")
        db.execute('SET temp_directory='+q(scratch));db.execute("SET max_temp_directory_size='6GB'")
        db.execute('CREATE VIEW p AS SELECT * FROM read_parquet('+q(config['per_molecule']['path'])+')')
        C.need(db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM p').fetchone()==(1220466,1220466),'ORIGINAL_PER_MOLECULE_POPULATION_MISMATCH')
        db.execute('CREATE TEMP TABLE mother AS SELECT * FROM p WHERE S_conformers=1')
        count=db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM mother').fetchone()
        db.execute('CREATE VIEW roles AS SELECT * FROM read_parquet(['+','.join(q(row['path']) for row in role_parts)+'])')
        C.need(db.execute('SELECT count(*),count(DISTINCT molecule_id) FROM roles').fetchone()==(1220466,1220466),'ORIGINAL_FROZEN_ROLE_POPULATION_MISMATCH')
        metas=db.execute('SELECT m.*,r.source_role,r.effective_role,r.records AS role_records,r.file_group FROM mother m LEFT JOIN roles r USING(molecule_id) ORDER BY m.molecule_id').fetch_arrow_table().to_pylist()
        C.need(len(metas)==count[0] and len({row['molecule_id'] for row in metas})==len(metas),'N1_ROLE_JOIN_MULTIPLICITY')
        initial_inventory_ref=I.write(out/'mother_initial.jsonl',b''.join(C.canonical({'molecule_id':row['molecule_id'],
            'source_N':1,'source_role':row.get('source_role'),'effective_role':row.get('effective_role'),
            'status':'BASELINE_VALIDATION_PENDING','common':False,'pilot_membership':False,'final_common_reference':None})+b'\n' for row in metas),budget.roots)
        pointer_columns=('record_id','molecule_id','source_path','real_index','record_payload_sha256','total_atoms')
        pointers=db.execute('SELECT '+','.join('r.'+name for name in pointer_columns)+' FROM read_parquet('+q(pointer_ref['path'])+') r JOIN mother USING(molecule_id) ORDER BY molecule_id,record_id').fetch_arrow_table().to_pylist()
        oldrows=db.execute('SELECT c.* FROM read_parquet(['+','.join(q(row['path']) for row in baseline_refs)+'],filename=true) c JOIN mother USING(molecule_id)').fetch_arrow_table().to_pylist()
        db.close()
        grouped_pointers={row['molecule_id']:[] for row in metas};grouped_baseline={mid:[] for mid in grouped_pointers}
        sources_by_path={row['path']:row for row in baseline_refs}
        for row in pointers:grouped_pointers[row['molecule_id']].append(row)
        for row in oldrows:
            filename=row.pop('filename');grouped_baseline[row['molecule_id']].append((row,sources_by_path[filename]))
        inventory=[];work=[]
        for meta in metas:
            mid=meta['molecule_id'];ptr=grouped_pointers[mid];all_base=grouped_baseline[mid]
            usable=[pair for pair in all_base if pair[0].get('status')=='SUCCESS' and pair[0].get('converged') is True]
            reason='REVIEWED_MOTHER_COUNT_MISMATCH' if count!=(expected,expected) else 'ROLE_FULL_OR_MISSING' if meta['effective_role'] not in {'TRAIN','VAL'} else \
                'PM7_USABLE_COUNT_NOT1' if meta.get('S_usable_conformers')!=1 else 'UFF_UNSUPPORTED' if meta.get('Sprime_status')=='UFF_UNSUPPORTED' else \
                'ORIGINAL_PM7_POINTER_COUNT_NOT1' if len(ptr)!=1 or meta.get('role_records')!=1 else \
                'DECLARED_PHYSICAL_BASELINE_COUNT_DISAGREE' if meta.get('Sprime_conformers')!=len(usable) else 'ACCEPTED_BASELINE_COUNT_NOT1' if len(usable)!=1 else None
            item={'molecule_id':mid,'source_N':1,'source_role':meta.get('source_role'),'effective_role':meta.get('effective_role'),
                'declared_Sprime_count':meta.get('Sprime_conformers'),'role_record_count':meta.get('role_records'),'actual_original_baseline_rows':len(all_base),
                'actual_usable_baseline_rows':len(usable),'actual_PM7_pointers':len(ptr),
                'Sprime_status':meta.get('Sprime_status'),'pm7_S_usable_count':meta.get('S_usable_conformers'),
                'pm7_S_usable_equals1':meta.get('S_usable_conformers')==1,
                'original_Sprime_usable_count':meta.get('Sprime_conformers'),
                'Sprime_usable_equals_source_N':meta.get('Sprime_conformers')==meta['S_conformers'],
                'metadata_eligibility_reason':reason,
                'status':'PENDING','reason':reason,'common':False,'pilot_membership':False,'final_common_reference':None}
            inventory.append(item)
            if reason is None:work.append({'meta':meta,'records':ptr,'baseline':usable[0][0],'baseline_source_reference':usable[0][1]})
        metadata_aggregate=mother_aggregation(metas,inventory,expected,correction_ref,'BEFORE_PHYSICAL_PM7_BASELINE_GRAPH_STEREO_VALIDATION',catalog['usability_semantics_provenance'])
        metadata_aggregate.update(job_id=str(proof['job_id']),per_molecule_reference=config['per_molecule'],source_sha_validation=source_check_ref)
        C.need(len(C.canonical(metadata_aggregate))+1<=1<<20,'BOUNDED_SMALL_ALL_MOTHER_METADATA_AGGREGATE')
        metadata_aggregate_ref=I.json_new(out/'mother_role_status_usable_before_validation.json',metadata_aggregate,budget.roots)
        if work and budget.observe(reserve=I.ADMIN_RESERVE) is None:
            results={};index=0;active={}
            with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=init_validation,
                    initargs=(I.ref(I.HERE/'frozen_sources.json'),admission)) as pool:
                while active or index<len(work):
                    budget.observe(list(pool._processes.values()),reserve=I.ADMIN_RESERVE)
                    while budget.stop is None and index<len(work) and len(active)<16:
                        row=work[index];active[pool.submit(validate_original,row)]=row;index+=1
                    if not active:break
                    done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                    for future in done:
                        row=active.pop(future);mid=row['meta']['molecule_id']
                        try:results[mid]=future.result()
                        except Exception as exc:results[mid]={'molecule_id':mid,'status':'PENDING','reason':'VALIDATION_WORKER_ERROR:'+str(exc),'traceback':traceback.format_exc()}
        else:results={}
        valid=[];work_by_mid={row['meta']['molecule_id']:row for row in work}
        for item in inventory:
            if item['reason'] is not None:continue
            checked=results.get(item['molecule_id'])
            if checked is None:item['reason']='VALIDATION_UNSTARTED_AFTER_OBSERVED_STOP';continue
            item['validation']=checked;item['status']=checked['status'];item['reason']=checked.get('reason')
            if checked['status']=='ORIGINAL_SOURCE_AND_BASELINE_VALIDATED_NO_NEW_UFF':valid.append(work_by_mid[item['molecule_id']])
        inventory_ref=I.write(out/'mother_inventory.jsonl',b''.join(C.canonical(row)+b'\n' for row in inventory),budget.roots)
        final_aggregate=mother_aggregation(metas,inventory,expected,correction_ref,'AFTER_ORIGINAL_PHYSICAL_VALIDATION_AND_BEFORE_PILOT_SELECTION',catalog['usability_semantics_provenance'])
        final_aggregate.update(job_id=str(proof['job_id']),per_molecule_reference=config['per_molecule'],source_sha_validation=source_check_ref,
            metadata_aggregation_before_validation=metadata_aggregate_ref)
        C.need(final_aggregate['all_mother_ids_sha256']==metadata_aggregate['all_mother_ids_sha256']
            and all(final_aggregate['marginals'][name]==metadata_aggregate['marginals'][name] for name in
                ('source_role','effective_role','Sprime_status','Sprime_usable_equals_source_N','original_Sprime_usable_count',
                 'pm7_S_usable_equals1','pm7_S_usable_count','physical_original_Sprime_usable_count','metadata_eligibility_reason')),
            'MOTHER_METADATA_MEMBERSHIP_AND_FILTER_INPUTS_MUST_NOT_CHANGE_DURING_VALIDATION')
        C.need(len(C.canonical(final_aggregate))+1<=1<<20,'BOUNDED_SMALL_ALL_MOTHER_FINAL_AGGREGATE')
        final_aggregate_ref=I.json_new(out/'mother_role_status_usable_audit.json',final_aggregate,budget.roots)
        selection=C.module_from_pin('_n1_prepare_selection',catalog['references']['selection']);picked=C.pilot32(valid,selection)
        reasons={}
        for item in inventory:reasons[item['reason'] or 'SOURCE_BASELINE_READY']=reasons.get(item['reason'] or 'SOURCE_BASELINE_READY',0)+1
        authority={'schema':'N1_PPRIME2_SOURCE_POPULATION_AUTHORITY_V3',
            'status':'ORIGINAL_SOURCE_POPULATION_CLOSED_PILOT_ONLY' if count==(expected,expected) else 'OBSERVED_SOURCE_COUNT_MISMATCH_PILOT_NOT_READY',
            'job_id':str(proof['job_id']),'formal_config':formal_ref,'mother_count':len(inventory),'expected_mother_count':expected,
            'count_correction_authority':correction_ref,'role_status_usable_audit':final_aggregate_ref,
            'metadata_aggregation_before_validation':metadata_aggregate_ref,
            'legacy_expected_count':5040,'legacy_count_provenance':correction['legacy_count_provenance'],
            'mother_inventory':inventory_ref,'initial_mother_inventory':initial_inventory_ref,'source_sha_validation':source_check_ref,'source_inputs':list(unique.values()),
            'roles_manifest':roles_ref,'roles_authority':config['roles_authority'],'source_pointer_index':pointer_ref,
            'sprime_manifest':config['sprime_manifest'],'eligible_source_baselines':len(valid),'reason_counts':reasons,
            'selected_molecule_ids':[row['meta']['molecule_id'] for row in picked['tasks']],
            'seed_domain':C.SEED_DOMAIN,'final_common_reference':None,'common':False,'pilot_membership':False,'production_membership':False,
            'new_UFF_calls':0,'new_QM_calls':0,'actual_terminal_C0_not_claimed_by_running_producer':True}
        authority_ref=I.json_new(out/'source_population_authority.json',authority,budget.roots)
        (out/'tasks').mkdir();(out/'baselines').mkdir();task_refs=[];base_refs=[]
        for row in picked['tasks']:
            meta=row['meta'];mid=meta['molecule_id'];checked=results[mid];old=row['baseline']
            name=hashlib.sha256(mid.encode()).hexdigest()+'.json'
            base=I.json_new(out/'baselines'/name,{'schema':'N1_ORIGINAL_BASELINE_PACKET_V2','molecule_id':mid,
                'original_row':old,'original_parquet_reference':row['baseline_source_reference'],'validation':checked,
                'source_population_authority':authority_ref,'common':False,'pilot_membership':False},budget.roots);base_refs.append(base)
            task={'schema':'N1_PPRIME2_PILOT_TASK_V2','task_key':C.task_key(mid),'final_common_reference':None,
                'meta':{'molecule_id':mid,'source_N':1,'PM7_source_count':1,'accepted_baseline_count':1,'UFF_desired_count':2,
                    'final_common_member':False,'common':False,'pilot_membership':False,'production_membership':False,
                    'effective_role':meta['effective_role'],'source_role':meta['source_role'],'Sprime_status':meta['Sprime_status']},
                'records':row['records'],'existing_conformers':[old],'baseline_row_sha256':checked['baseline_row_sha256'],
                'source_atomic_numbers':checked['atomic_numbers'],
                'baseline_geometry_id':'accepted_sprime_source_row:'+C.sha_value({'source':row['baseline_source_reference'],'molecule_id':mid,'index':0,'row_sha256':checked['baseline_row_sha256']}),
                'authority_references':{'source_population_authority':authority_ref,'source_pointer_manifest':pointer_ref,
                    'accepted_baseline_evidence':base,'roles_manifest':roles_ref}}
            C.validate_task(task,authority_ref);raw=C.canonical(task)+b'\n';C.need(len(raw)<=I.TASK_CAP,'BOUNDED_TASK_METADATA_ENVELOPE_REQUIRED')
            task_refs.append(I.write(out/'tasks'/name,raw,budget.roots))
        ready=count==(expected,expected) and len(task_refs)==32 and budget.stop is None
        prepared={'schema':'N1_PPRIME2_PILOT_PREPARED32_V3','status':'ACTUAL_INPUT32_READY_NOT_GENERATED' if ready else 'PENDING_INPUT32_NOT_READY',
            'job_id':str(proof['job_id']),'source_population_authority':authority_ref,'tasks':task_refs,'baseline_packets':base_refs,
            'mother_inventory':inventory_ref,'source_sha_validation':source_check_ref,'formal_config':formal_ref,
            'catalog':I.ref(I.HERE/'frozen_sources.json'),'budget':budget.report(),'reason_counts':reasons,
            'count_correction_authority':correction_ref,'role_status_usable_audit':final_aggregate_ref,
            'metadata_aggregation_before_validation':metadata_aggregate_ref,
            'expected_mother_count':expected,'legacy_expected_count':5040,'legacy_count_provenance':correction['legacy_count_provenance'],
            'eligible_count':len(valid),'selected_count':len(task_refs),'mother_count':len(inventory),
            'common':False,'pilot_membership':False,'production_membership':False,'final_common_reference':None,
            'new_UFF_calls':0,'new_QM_calls':0,'elapsed_seconds':time.monotonic()-started,
            'actual_terminal_accounting_required':True,'actual_parent_allocated_core_seconds':None}
        result=I.json_new(out/'prepared.json',prepared,budget.roots)
    print(json.dumps({'prepared':result,'status':prepared['status'],'selected_count':len(task_refs),'common':False}))
    return 0 if ready else 3


if __name__=='__main__':raise SystemExit(main())
