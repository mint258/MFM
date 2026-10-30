"""One real16CPU Parent: adopt old lists, true40k geometry/children and distributions."""
import argparse,io,json,os,pathlib,sqlite3,traceback,unittest
from . import contract as C,adopt as A,produce as P,children as H
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup

def fixtures(root):
    from . import test_boundaries,source_inverse
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_boundaries.Boundaries)
    C.need(suite.countTestCases()==3,'EXACT_THREE_BOUNDED_D5_BOUNDARIES_BEFORE_DATA')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    proof=source_inverse.proof();ref=I.save(root/'preflight.json',{'tests':r.testsRun,'errors':len(r.errors),'failures':len(r.failures),'transcript':stream.getvalue(),
        'status':'PASS' if r.wasSuccessful() and r.testsRun==3 and not r.skipped else 'FAIL_NO_DATA','source_inverse':proof,'scientific_DATA_read':False})
    C.need(r.wasSuccessful() and r.testsRun==3 and not r.skipped,'SOURCE_OR_BOUNDARIES_FAILED_NO_DATA');return ref

def lists_and_distributions(ctx,db,pre,children,targets):
    from . import distributions as D
    from workflows.data_v1_final.export.d5_materialize_cpu_v1.produce import originals
    Original,_,_,_,_=originals()
    import pyarrow as pa
    q=lambda x:"'"+str(x).replace("'","''")+"'"
    db.execute('CREATE TABLE subset_members(subset VARCHAR,molecule_id VARCHAR,effective_role VARCHAR,selection_rank BIGINT,PRIMARY KEY(subset,molecule_id))')
    db.execute("INSERT INTO subset_members SELECT CASE WHEN effective_role='TRAIN' THEN 'train_all' ELSE 'val_all' END,molecule_id,effective_role,selection_rank FROM mother")
    for n in C.NESTED:
        db.execute('INSERT INTO subset_members SELECT ?,molecule_id,effective_role,selection_rank FROM read_parquet(?)',['train_'+str(n),pre['tables']['train_'+str(n)]['path']])
    for role,name in (('TRAIN','pilot_train'),('VAL','pilot_val')):
        db.execute('INSERT INTO subset_members SELECT ?,molecule_id,effective_role,selection_rank FROM read_parquet(?) WHERE effective_role=?',[name,pre['tables']['pilot55k']['path'],role])
    counts=dict(db.execute('SELECT subset,count(*) FROM subset_members GROUP BY subset').fetchall())
    C.need(all(counts['train_'+str(n)]==n for n in C.NESTED) and counts['pilot_train']==50000 and counts['pilot_val']==5000,'NO_GUIDE_SUBSET_COUNT_DOWNGRADE')
    db.execute('CREATE TABLE excluded(gid VARCHAR PRIMARY KEY)');db.executemany('INSERT INTO excluded VALUES(?)',[(gid,) for gid in sorted(targets)])
    db.execute('CREATE TABLE training_random AS SELECT b.*,row_number() OVER(PARTITION BY b.molecule_id,b.geometry_source ORDER BY b.rank)-1 AS training_rank FROM base_index b ANTI JOIN excluded e ON e.gid=b.geometry_id')
    C.need(db.execute('SELECT count(*) FROM training_random t JOIN excluded e ON t.geometry_id=e.gid').fetchone()[0]==0,'ALL_BASE_TRAINING_CONDITIONS_ANTI_JOIN_BEFORE_FIRST_K')
    C.need(db.execute('SELECT count(*) FROM (SELECT m.molecule_id FROM mother m LEFT JOIN training_random t USING(molecule_id) GROUP BY m.molecule_id HAVING sum(t.geometry_source=\'pm7\')<1 OR sum(t.geometry_source=\'uff_sprime\')<1)').fetchone()[0]==0,'DIAGNOSTIC_MIDS_REMAIN_SEEN_WITH_OTHER_GEOMETRIES')
    tables={}
    for name in counts:tables[name]=P.parquet_query(ctx,db,'SELECT * FROM subset_members WHERE subset=? ORDER BY selection_rank',ctx.out/(name+'.parquet'),[name])
    eligible=P.parquet_query(ctx,db,'SELECT b.*,m.effective_role,m.source_role FROM training_random b JOIN mother m USING(molecule_id) ORDER BY molecule_id,geometry_source,training_rank',ctx.out/'training_fixed_random_base_index.parquet')
    index=P.parquet_query(ctx,db,'SELECT b.*,m.effective_role,m.source_role FROM base_index b JOIN mother m USING(molecule_id) ORDER BY molecule_id,geometry_source,rank',ctx.out/'all_fixed_random_base_index.parquet')
    feature_ref=P.parquet_query(ctx,db,'SELECT * FROM native_features ORDER BY molecule_id',ctx.out/'all_old_complete_native_features.parquet')
    # Exact original input schema/normalizer and dimension SQL, bounded IO status only.
    path=ctx.out/'distribution_inputs.sqlite';dest=sqlite3.connect(path)
    dest.executescript('CREATE TABLE features('+Original.SCHEMA['features']+');CREATE TABLE subset_members(subset TEXT,molecule_id TEXT,effective_role TEXT,selection_rank INTEGER,PRIMARY KEY(subset,molecule_id));')
    try:
        cur=db.execute('SELECT * FROM native_features ORDER BY molecule_id')
        while True:
            ctx.check();rows=cur.fetchmany(4096)
            if not rows:break
            values=[Original.normalize('features',{'molecule_id':r[0],'element_z':r[1],'heavy_atoms':r[2],'scaffold_id':r[3]}) for r in rows]
            dest.executemany('INSERT INTO features VALUES(?,?,?,?)',values);dest.commit()
        cur=db.execute('SELECT subset,molecule_id,effective_role,selection_rank FROM subset_members')
        while True:
            ctx.check();rows=cur.fetchmany(4096)
            if not rows:break
            dest.executemany('INSERT INTO subset_members VALUES(?,?,?,?)',rows);dest.commit()
        C.need(dest.execute('SELECT count(*),count(DISTINCT molecule_id) FROM features').fetchone()==(sum(counts[k] for k in ('train_all','val_all')),)*2,'ALL_FEATURES_REOPEN_EQUAL_FULL_OLD_MOTHER')
    finally:dest.close()
    database=I.allow(I.pin(path));manifest=I.save(ctx.out/'bounded_lists_for_original_distributions.json',{'status':'BOUNDED_OLD_COMPLETE_D5_LISTS_CPU_VERIFIED_PENDING_ROOT',
        'database':database,'subsets':tables,'subset_counts':counts,'scope_version':ctx.plan['scope_version'],'final_Common_or_D6_release':False})
    ctx.check();distribution=D.run(pathlib.Path(manifest['path']),ctx.out/'distributions',fixture=False);ctx.check()
    distref=I.allow(I.pin(ctx.out/'distributions/manifest.json'))
    # CPU readback of every list, rank, native ID and all target keys; no filename acceptance.
    for name,ref in tables.items():
        C.need(db.execute('SELECT count(*) FROM (SELECT * FROM read_parquet(?) EXCEPT ALL SELECT * FROM subset_members WHERE subset=?)',[ref['path'],name]).fetchone()[0]==0
          and db.execute('SELECT count(*) FROM (SELECT * FROM subset_members WHERE subset=? EXCEPT ALL SELECT * FROM read_parquet(?))',[name,ref['path']]).fetchone()[0]==0,'ALL_SUBSET_ROWS_ROLES_RANKS_TWO_WAY_REOPEN')
    ddb=sqlite3.connect('file:'+str(ctx.out/'distributions/distributions.sqlite')+'?mode=ro',uri=True)
    try:C.need(ddb.execute('SELECT count(*) FROM totals').fetchone()[0]==len(counts),'ORIGINAL_DISTRIBUTIONS_ALL_SUBSETS_PRESENT')
    finally:ddb.close()
    return {'subsets':tables,'subset_counts':counts,'all_fixed_random_base_index_reference':index,'training_fixed_random_base_index_reference':eligible,
      'all_old_complete_native_features_reference':feature_ref,'distribution_inputs_reference':database,'distributions_manifest_reference':distref,
      'diagnostic_base_reference':children['diagnostic_base_reference'],'diagnostic_targets_reference':children['diagnostic_target_reference'],
      'actual_heldout_geometry_reference':children['table_references']['geometries'],'actual_input_views_reference':children['actual_program_input_view_reference'],
      'actual_field_input_binding_reference':children['cell_binding_reference'],'diagnostic_TRAIN_molecules':20000,'heldout_PM7_bases':20000,'heldout_ordinary_Sprime_bases':20000,
      'all_training_lists_anti_join_global_base_child_inputview_targets_before_first_k':True,'fixed_random_only_not_D7_energy_diversity':True}

def execute(plan,proof,root,gate,budget):
    ctx=A.Context(plan,proof,root,budget);db=None;phase='CLOSED_PRESELECTION';components=None
    try:
        db,base,pre_ref,pre,policy=A.restore(ctx);ctx.db=db
        I.save(root/'closed_preselection_adoption.json',{'preselection_reference':pre_ref,'old_FAILED_not_C0':True,'same_original_lists_not_reselected':True,'actual_parent_job_id':str(proof['job_id'])})
        phase='ALL_REAL_BASE_IDENTITIES';P.scalar_indices(ctx,db,pre)
        phase='ORIGINAL_NATIVE_ANCHOR_FEATURES_AND_REAL40K';physical,selected=P.features_and_bases(ctx,db)
        phase='ALL_ACTUAL_WP5_CHILDREN_INPUT_VIEWS';children,targets=H.run(ctx,physical,selected)
        phase='NESTED_LISTS_ANTI_JOIN_AND_DISTRIBUTIONS';components=lists_and_distributions(ctx,db,pre,children,targets)
        return I.save(root/'receipt.json',{'schema':'BOUNDED_OLD_COMPLETE_D5_DAY_RECEIPT_V1','status':'BOUNDED_OLD_COMPLETE_D5_COMPONENTS_COMPLETE_PENDING_ACTUAL_C0_ROOT',
          'job_id':str(proof['job_id']),'uid':1278,'node':proof['request']['node'],'cpus':16,'plan_reference':C.P.pin(plan['plan_path']),
          'startup_proof_reference':C.P.pin(plan['startup_proof_path']),'scope_version':plan['scope_version'],'fixture_reference':gate,
          'preselection_reference':pre_ref,'closed_native_feature_readback_reference':physical['closed_feature_readback_reference'],'components':components,'held':False,'errors':[],'new_QM_UFF_calls':0,'new_RMSD_HOF_calls':0,
          'all_original_source_roles_and_f64_retained':True,'actual_accepted_UFF_Pprime_training_children':0,'global_native_QM_call_count_claimed':False,
          'accepted_training_source_inventory_scope_verified':True,'final_Common_D3_D4_D6_or_joint_release':False})
    except BaseException as exc:
        I.save(root/'failure.json',{'schema':'BOUNDED_OLD_COMPLETE_D5_FAILURE_V1','phase':phase,'error':repr(exc),'traceback':traceback.format_exc(),
          'held':True,'closed_evidence_preserved':True,'pending_availability_not_new_scientific_exclusion':True,'new_QM_UFF_calls':0,'old_FAILED_or_UNKNOWN_changed':False})
        raise
    finally:
        if db is not None:db.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    plan=C.plan(C.meta(C.P.pin(a.plan)));plan=dict(plan,plan_path=a.plan,startup_proof_path=a.startup_proof)
    proof=require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.scope(plan),expected_execution_argv=[C.PY,'-B','-m',C.MODULE,'--plan',a.plan,'--startup-proof',a.startup_proof],
        expected_source=pathlib.Path(__file__),expected_kind='analysis',required_references=[C.P.pin(a.plan),*plan['source_references']])
    req=proof['request'];C.need(req['cpus']==16 and req['node']==plan['node'] and req['wall_seconds']==86400 and req['pilot']is False
      and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['estimated_peak_output_bytes']==32<<30
      and {r['path']:r for r in req['data_references']}=={r['path']:r for r in plan['data_references']},'TRUE_CURRENT_GENERIC16_DAY32GIB_EXACT_DATA')
    C.need(all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'ORIGINAL_SINGLE_THREAD_LIBRARIES')
    I.configure(plan);root=I.new_root(plan['output_directory']);budget=None
    try:gate=fixtures(root);budget=I.Budget(plan,proof,root);budget.check(force=True);execute(plan,proof,root,gate,budget)
    finally:
        if budget is not None:budget.close()
if __name__=='__main__':main()
