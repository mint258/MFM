"""One bounded CPU Parent: Source3, actual55k projection, F64/Family/D3 closure."""
import argparse,concurrent.futures as cf,hashlib,io,json,multiprocessing as mp,os,pathlib,sys,traceback,unittest
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[_key]='1'
from . import contract as C,io as I,domain as D,source as X,writer as W,verify as V,configuration as G,projection as P,frame_mapping as M
from workflows.data_v1_final.export.family_export_day_v1 import transport as T
def fixtures(out):
    from . import test_v1
    inverse=P.source_proof()
    test_v1.WORKSPACE=out;case=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries);C.need(case.countTestCases()==3,'EXACT3_MEANINGFUL_SOURCE_METHODS')
    log=io.StringIO();r=unittest.TextTestRunner(stream=log,verbosity=2).run(case)
    result={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),
      'transcript':log.getvalue(),'before_SCI_DATA_Budget_native_reader':True,'new_QM_UFF_calls':0,'revision2_source_inverse':inverse}
    ref=I.save(out/'source3.json',result);C.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_FAILED_NO_DATA');return ref,result
def merge(db,result):
    db.execute('ATTACH DATABASE ? AS completed',(result['reference']['path'],))
    try:db.execute('INSERT INTO pieces SELECT * FROM completed.pieces');db.execute('INSERT INTO closed_groups VALUES(?,?)',(result['key'],json.dumps(result,sort_keys=True)));db.commit()
    finally:db.execute('DETACH DATABASE completed')
def checked_recipe(recipe,registry,compiled,fields,declared):
    C.need(recipe['schema'] in ('BOUNDED_PILOT_ORIGINAL_FAMILY_PROJECTION_RECIPE_V1','BOUNDED_PILOT_ORIGINAL_FAMILY_PROJECTION_RECIPE_V2') and recipe['ordinary_PM7_only'] is True,'EXPLICIT_VERSIONED_PROJECTION_RECIPE_NOT_GUESSED_SOURCE_LAYOUT')
    mapping={f['field_key']:f['field_id'] for f in fields};C.need(set(mapping.values())==set(range(146)),'ORIGINAL146_FIELD_IDS_UNCHANGED')
    used=set()
    for task,tr in recipe['tasks'].items():
        C.need(type(tr['actual_task_charge']) is int and tr['actual_charge_authority_reference'] in declared,'ACTUAL_EXECUTION_CHARGE_AUTHORITY_NOT_SMILES_FORMAL_CHARGE')
        protocol=C.meta(tr['actual_charge_authority_reference']);actual=next(t for t in protocol['tasks'] if t['name']==task) if tr['geometry_binding']=='ACTUAL_WP5_PROGRAM_INPUT_DOUBLE_HASH' else None
        if actual is not None:
            if actual['family']=='xtb':charge=int(actual['args'][actual['args'].index('--chrg')+1])
            else:
                tokens=actual['keywords'].split() if isinstance(actual['keywords'],str) else actual['keywords'];hits=[v for v in tokens if v.upper().startswith('CHARGE=')]
                C.need(len(hits)<=1,'UNAMBIGUOUS_ORIGINAL_MOPAC_CHARGE');charge=int(hits[0].split('=',1)[1]) if hits else 0
            C.need(charge==tr['actual_task_charge'],'EXACT_ORIGINAL_TASK_STATE_NO_IONIC_SMILES_FILTER')
        for tid in tr['targets']:
            t=compiled['ordered_record_targets'].get(tid) or compiled['physical_targets'][tid]
            C.need(t['condition']!='Pprime' and t['geometry_source']=='pm7','NO_FORMAL_PPRIME_OR_EXTRA_GEOMETRY_IMPUTATION')
            for m in t['members']:
                key=m['field_key'];C.need(key not in used and registry[key]['task']==task and tr['components'][key]['compact']['field_id']==mapping[key],'EVERY_ENABLED_MEMBER_EXACTLY_ONCE_IN_ORIGINAL_TASK');used.add(key)
    C.need(used==set(registry),'ALL_ENABLED_FIELDS_PROJECTED_NO_SILENT_R73_OR_TENSOR_DROP')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=C.meta(C.Q.pin(a.plan));C.need(plan['schema']=='BOUNDED_PILOT_FAMILY_D3_PLAN_V1' and plan['scope_parameters']==C.parameters(plan),'EXACT_BOUNDED_PLAN')
    accepted,prior,priorproof,old,review,data,refs=C.parents(plan);C.need(data==plan['data_references'],'UNCHANGED_POSITIVE_DATA_DECLARATIONS')
    proof=I.guard(a.plan,a.startup_proof,plan);C.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py'
      and sys.argv==[str(C.HERE/'run.py'),'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)],'EXACT_PRIMARY_MODULE_AND_COMPLETE_ARGV')
    for r in C.sources():C.need(r in proof['request']['source_references'],'FROZEN_DIRECT_OBJECT_SOURCE_DEPENDENCIES')
    root=pathlib.Path(plan['output_directory']);C.need(not root.exists() and C.OUTPUT in root.parents and not any(x.is_symlink() for x in (root,*root.parents)),'FRESH_OWN_LITERAL_OUTPUT')
    root.mkdir(parents=True,mode=0o700);I.configure(plan,old);gate,gate_values=fixtures(root);budget=None;pool=None;db=None;errors=[];context=None;stores=[];verification=None;state='SOURCE3'
    try:
        budget=I.Budget(plan,proof,root);budget.check(force=True);roots=review['transitive_closed_output_roots'];components=accepted['component_references']
        cfg=D.read(components['typed_reader_config_reference'],roots);coverage=D.read(components['coverage_reference'],roots)
        C.need(coverage['all14task_and_base_exact_once'] is True and coverage['quality_hold_fields']==[] and coverage['errors']==[],'ORIGINAL_ONE_PERCENT_QUALITY_GATE_NOT_WAIVED_BY_EXPORT')
        for r in cfg['data_references']:
            if r['path'] not in I.B.ALLOWED:D.register(r,roots)
        cfg=I.configure_reader(cfg,coverage,old['output_directory'])
        fields=I.load_data(cfg['field_map_reference'],8<<20);bykey={f['field_key']:f for f in fields}
        if review.get('configuration_mode')==G.MODE:
            generated,registry,mapping,recipe,physical,compiled=G.materialize(plan,review,components,fields,cfg,roots,root/'actual_bounded_configurations',budget)
            review=dict(review,**generated)
        else:
            registry=D.read(review['registry_reference'],roots);mapping=D.read(review['mapping_reference'],roots);recipe=D.read(review['projection_recipe_reference'],roots)
            physical=D.read(review['target_policy_reference'],roots)
        C.need(physical['schema']=='BOUNDED_D1_TARGET_LOCAL_EXPOSURE_AND_SCALE_V1' and physical['original_numeric_masks_unchanged'] is True
          and physical['actual_task_charge_separate_from_SMILES_formal_charge'] is True,'ACTUAL_TARGET_LOCAL_POLICY_NOT_A_BLANKET_GRAPH_ION_FILTER')
        compiled=M.compile_targets(registry,mapping);checked_recipe(recipe,{f['field_key']:f for f in registry['fields'] if f['status']=='enabled'},compiled,fields,plan['source_references'])
        rootPolicy=dict(review,target_policy=physical['targets']);db,g,binding,roots=D.build(plan,old,accepted,root,budget);rootPolicy['actual_cell_binding_reference']=binding;state='DOMAIN_CLOSED'
        if C.native_mode(plan):
            order_capability_reference=I.save(root/'available_orders.json',{'schema':'BOUNDED_NATIVE55K_FIXED_RANDOM_ORDER_CAPABILITY_V1',
              **C.capabilities(plan),'actual_D4_acceptance_reference':plan['pilot_acceptance_reference'],
              'actual_geometry_reference':components['geometry_reference'],'actual_orders_table_reference':g['table_references']['orders'],
              'actual_parent_job_id':str(proof['job_id']),'Root_Model_actual_payload_acceptance':False,
              'full_three_order_consumers_must_refuse':True,'all_actual_base_child_input_geometries_retained':True})
        else:order_capability_reference=None
        r674_report=D.read(components['r674_report_reference'],roots)
        actual_scales={v['loss_recipe_candidate']['series_key']:v['loss_recipe_candidate'] for v in r674_report['groups']}
        for policy in physical['targets'].values():
            if policy.get('scale_status')!='ACTUAL_TRAIN_POPULATION_SHA_BOUND':continue
            actual=actual_scales.get(policy.get('series_key'));C.need(actual is not None and actual['candidate_scale']==policy.get('scale')
              and actual['statistic_reference']==policy.get('scale_reference') and actual['population_version_reference']==policy.get('scale_population_reference')
              and actual['population_version_reference']==components['population_reference'],'SCALE_EXACT_ACTUAL_SOURCE_RECIPE_POPULATION_SERIES_NOT_INLINE_S1')
        for r in components['numeric_repetitions']:D.register(r,roots);I.require(r)
        C.need(pathlib.Path(components['numeric_repetitions'][0]['path']).read_bytes()==pathlib.Path(components['numeric_repetitions'][1]['path']).read_bytes(),'ACTUAL_PRIOR_NUMERIC_REPLAYS_EQUAL_NOT_SOURCE_ASSERTION')
        # Current-device frames are derived on this CPU. No original catalog
        # frame, source file, geometry or producer configuration is rewritten.
        I.append(root/'lineage.DATA.jsonl',{'actual_old_parent':accepted['actual_parent'],'original_catalog_frame':D.read(components['typed_reader_config_reference'],roots)['catalog_frame'],
          'current_catalog_frame':cfg['catalog_frame'],'geometry_reference':components['geometry_reference'],'new_parent_job_id':str(proof['job_id']),'not_same_parent_as_old_source':True})
        db.commit();groups=BC_groups(cfg,roots);context={'plan':plan,'old_plan':old,'reader_config':cfg,'field_map':fields,'compiled':compiled,'recipe':recipe,
          'domain_database':str(root/'domain.sqlite'),'binding_database':binding['path'],'coverage_catalog':coverage['parts_catalog']['path'],
          'control':budget.control,'job_id':str(proof['job_id']),'node':proof['request']['node'],'registered_references':list(I.B.ALLOWED.values()),'reader_origins':dict(I.B.ORIGINS)}
        ctx=mp.get_context('spawn');pool=cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=X.initialize,initargs=(context,));pending={};cursor=iter(groups);done=False
        stage=root/'permanent_f64_source_groups';stage.mkdir();state='SOURCE_PROJECTION'
        while pending or not done:
            while not done and len(pending)<32:
                try:budget.check();group=next(cursor)
                except StopIteration:done=True;break
                key=hashlib.sha256(json.dumps(group,sort_keys=True,separators=(',',':')).encode()).hexdigest();path=stage/(key+'.sqlite')
                C.need(not path.exists(),'NO_AUTOMATIC_UNKNOWN_GROUP_RETRY');I.append(root/'dispatch.jsonl',{'key':key,'group_key':str(group['source_job_id']),'output':str(path),'parent_job_id':str(proof['job_id'])})
                pending[pool.submit(X.one,(key,group,str(path)))]=key
            if pending:
                ready,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in ready:
                    key=pending.pop(future);result=future.result();I.add(result['reference']);I.require(result['reference']);merge(db,result);I.append(root/'closed_groups.jsonl',result)
        state='PERMANENT_F64_GROUPS_CLOSED';stores,eligibility=W.write(db,root,compiled,rootPolicy,plan,proof,budget)
        verification,qa=V.run(db,stores,root,context,pool,budget);state='ACTUAL_D3_READBACK_CLOSED'
        procs=list(pool._processes.values());pool.shutdown(wait=True,cancel_futures=False);pool=None
        C.need(all(not v.is_alive() and v.exitcode==0 for v in procs),'ALL_ACTUAL_PROJECTION_AND_READBACK_WORKERS_CLOSED')
        db.close();db=None;budget.check(force=True,dispatch=False);budget.close();budget=None
        receipt={'schema':'BOUNDED_PILOT_FAMILY_D3_RECEIPT_V1',
          'status':'ACTUAL55K_FIXED_RANDOM_FAMILY_AND_10K_SOURCE_QA_COMPLETE_PENDING_ROOT_MODEL_REVIEW' if C.native_mode(plan) else 'ACTUAL55K_FAMILY_AND_10K_SOURCE_QA_COMPLETE_PENDING_ROOT_MODEL_REVIEW',
          'job_id':str(proof['job_id']),'uid':1278,'node':proof['request']['node'],'actual_cpus':16,'plan_reference':C.Q.pin(a.plan),'startup_proof_reference':C.Q.pin(a.startup_proof),
          'pilot_acceptance_reference':plan['pilot_acceptance_reference'],'bounded_export_review_reference':plan['bounded_export_review_reference'],
          'actual_configuration_references':{k:review[k] for k in ('registry_reference','mapping_reference','projection_recipe_reference','target_policy_reference')},
          **C.capabilities(plan),'order_capability_reference':order_capability_reference,
          'source3_reference':gate,'pilot_counts':C.COUNTS,'store_references':stores,'verification_reference':verification,
          'r674_loss_eligibility_counts_by_target_role_reason':eligibility,'phase':state,'source_roundtrip_records':10000,
          'all_Family_SQLite_Sidecar_and_spawn_reader_handles_closed':True,'parent_native_reader_lifecycle':'ORIGINAL_NATIVE_READER_FINALIZATION_AT_ACTUAL_PARENT_EXIT_REQUIRES_EXTERNAL_TERMINAL_ACCOUNTING','errors':[],
          'inherited_complete6_element_structure_bias_raw_mean_F_and_scale_report_reference':components['r674_report_reference'],
          'new_QM_UFF_calls':0,'all_original_source_unknown_masks_retained':True,'training_ready':False,'Model_ACK':False,'full_Common_D6_or_final_D4_release':False}
        I.save(root/'receipt.json',receipt);return 0
    except BaseException as exc:
        errors.append({'type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc()})
        I.save(root/'failure.DATA.json',{'phase':state,'errors':errors,'old_outputs_unchanged':True,'closed_groups_preserved_no_retry':True,'new_QM_UFF_calls':0})
        return 3
    finally:
        if pool is not None:pool.shutdown(wait=True,cancel_futures=False)
        if db is not None:db.close()
        if budget is not None:budget.close()
def BC_groups(cfg,roots):
    book=D.read(cfg['logical_group_plan_reference'],roots,8<<20);return C.B.logical(book['groups'])
if __name__=='__main__':raise SystemExit(main())
