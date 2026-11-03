"""Closed native observations only, in one allocation and persistent pool."""
import argparse,collections,concurrent.futures as cf,io,json,multiprocessing as mp,os,sqlite3,sys,time,unittest
from pathlib import Path
from . import contracts as C,kernel as K,io as I
from secondary_coconut_identity_norm_profile_v1.runtime import Budget

def fixtures(root,plan):
    from . import test_v1,source_inverse
    synthetic=root/'source_fixture_io';synthetic.mkdir();test_v1.ROOT=str(synthetic)
    K.configure(plan);transcript=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromTestCase(test_v1.Boundaries)
    C.need(suite.countTestCases()==3,'EXACT_THREE_SOURCE_IDENTITY_BOUNDARIES_BEFORE_DATA');r=unittest.TextTestRunner(stream=transcript,verbosity=2).run(suite)
    result={'tests':r.testsRun,'errors':len(r.errors),'failures':len(r.failures),'skips':len(r.skipped),'transcript':transcript.getvalue(),
      'status':'PASS' if r.wasSuccessful() and r.testsRun==3 and not r.skipped else 'FAIL_BEFORE_DATA','inverse':source_inverse.proof()}
    C.write_new(root/'fixture_gate.json',result);C.need(result['status']=='PASS','SOURCE3_FAIL_NO_REAL_IDENTITY_BODY');return C.pin(root/'fixture_gate.json')

def database(root):
    tmp=root/'sqlite_scratch';tmp.mkdir();os.environ['SQLITE_TMPDIR']=str(tmp)
    db=sqlite3.connect(root/'identity_links.sqlite');db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA cache_size=-65536');db.execute('PRAGMA temp_store=FILE')
    db.executescript('CREATE TABLE properties(mid TEXT,payload TEXT);CREATE INDEX properties_mid ON properties(mid);'
      'CREATE TABLE molecules(mid TEXT PRIMARY KEY,payload TEXT);CREATE TABLE physical(t TEXT,b INTEGER,o INTEGER,PRIMARY KEY(t,b,o)) WITHOUT ROWID;')
    return db

def norm_rows(part,budget):
    seen=0
    for batch in I.parquet(part['reference'],budget,'norm',part['rows']):
        values=[]
        for row in batch:
            C.need(row['source_table']==part['table'],'NORM_PART_TABLE_CHANGED');o=json.loads(row['observation_json']);src=o['source']
            C.need(all(row[k]==src[k] for k in ('source_table','copy_block','source_row_ordinal')),'CLOSED_OUTER_INNER_PHYSICAL_LOCATOR')
            C.need(type(src['copy_block'])is int and type(src['source_row_ordinal'])is int and src['source_row_ordinal']>=0,'ORIGINAL_PHYSICAL_ORDINAL')
            o['_strict_parent_locator']={'reference':part['reference'],'source_table':src['source_table'],'copy_block':src['copy_block'],'source_row_ordinal':src['source_row_ordinal']}
            values.append(o);seen+=1
        yield values
    C.need(seen==part['rows'],'WHOLE_CLOSED_NORM_PART_MASS')

def execute(plan,proof,root,gate,budget):
    receipt,old,parts,properties,native=C.norm_parent(plan);db=database(root);ident=I.Jsonl(root/'identities.jsonl',budget)
    audit=I.Jsonl(root/'physical_coverage.jsonl',budget);unknown=I.Jsonl(root/'unknown_identity_locators.jsonl',budget)
    counters=collections.Counter();tables=collections.Counter();original=collections.Counter();expected_fk={'NULL':2454,'ORPHAN':26}
    pending=collections.deque();processed=0;complete=False;hold=False
    def accept(rows):
        nonlocal processed
        for value in rows:
            table=value['table'];locator=value.pop('_locator')
            db.execute('INSERT INTO physical VALUES(?,?,?)',(table,value['copy_block'],value['ordinal']));tables[table]+=1;processed+=1
            original.update(value['original_norm_counters']);counters['FK_'+value['FK_state']]+=1;counters['formula_conflicts_or_multiple_native_compositions']+=value['formula_conflict']
            if table=='molecules':
                payload={'molecule_id':value['molecule_id'],'keys':value['keys'],'compositions':value['all_native_compositions'],'locator':locator}
                db.execute('INSERT INTO molecules VALUES(?,?)',(value['molecule_id'],json.dumps(payload,ensure_ascii=False,separators=(',',':'))))
            base={'source_id':value['source_id'],'role':plan['role'],'subdataset':table,'inchikeys':value['keys'],'non_h_composition':None}
            if value['keys']:K.STATE['consumer'](base);ident.add(base);counters['strict_rows']+=1
            for j,comp in enumerate(value['compositions']):
                row=dict(base,source_id=value['source_id']+':composition:'+str(j),inchikeys=[],non_h_composition=comp)
                K.STATE['consumer'](row);ident.add(row);counters['strict_rows']+=1;counters['composition_rows']+=1
            if not value['covered']:
                counters['unresolved_without_identity_or_composition']+=1;unknown.add({'locator':locator,'original_id':value['original_id'],
                  'reason':value['unknown_reason'],'FK_state':value['FK_state'],'field_availability':value['field_availability']})
            audit.add({'locator':locator,'source_id':value['source_id'],'covered':value['covered'],'FK_state':value['FK_state'],
                'source_row_sha256':value['source_row_sha256'],'needs_conservative_fallback':value['needs_conservative_fallback'],
                'original_norm_counters':value['original_norm_counters'],'evidence':value['evidence'],'graph_identity_repaired':False})
            if processed%4096==0:db.commit()
    def collect():
        future,locators=pending.popleft();values=future.result();C.need(len(values)==len(locators),'BOUNDED_WORKER_BATCH_RETURN_MASS')
        for value,locator in zip(values,locators):value['_locator']=locator
        accept(values)
    try:
        aux=0
        for batch in I.parquet(properties,budget,'raw',1140133):
            for row in batch:
                fields=json.loads(row['identity_fields_json']);C.need(row['source_table']=='properties' and set(fields)=={'id','molecule_id','molecular_formula'},'ORIGINAL_A_FORMULA_ONLY_NO_TARGETS')
                locator={'reference':properties,'source_table':'properties','copy_block':row['copy_block'],'source_row_ordinal':row['source_row_ordinal'],'source_row_sha256':row['source_row_sha256']}
                db.execute('INSERT INTO properties VALUES(?,?)',(fields['molecule_id'],json.dumps({'value':fields['molecular_formula'],'locator':locator},ensure_ascii=False,separators=(',',':'))));aux+=1
                if aux%4096==0:db.commit()
        C.need(aux==1140133,'FULL_ORIGINAL_PROPERTY_FORMULA_ROWS');db.commit()
        ctx=mp.get_context('spawn')
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=K.configure,initargs=(plan,)) as pool:
            for table in ('molecules','entries'):
                for part in [p for p in parts if p['table']==table]:
                    for batch in norm_rows(part,budget):
                        budget.dispatch_check();items=[];locators=[]
                        for observation in batch:
                            fields=json.loads(observation['source']['identity_fields_json']);C.need(isinstance(fields['id'],str) and fields['id'],'ORIGINAL_NONEMPTY_NATIVE_ID_NOT_INVENTED')
                            if table=='molecules':
                                formulas=[json.loads(x[0]) for x in db.execute('SELECT payload FROM properties WHERE mid=?',(fields['id'],))];parent=None
                            else:
                                formulas=[];row=db.execute('SELECT payload FROM molecules WHERE mid=?',(fields['molecule_id'],)).fetchone() if fields['molecule_id'] is not None else None;parent=json.loads(row[0]) if row else None
                            C.need(len(json.dumps(formulas).encode())<=8<<20,'COMPLETE_NATIVE_FORMULA_LIST_NO_TRUNCATION')
                            items.append((observation,formulas,parent));locators.append(observation['_strict_parent_locator'])
                        pending.append((pool.submit(K.work,items),locators));budget.workers=list(pool._processes.values())
                        if len(pending)>=32:collect()
                while pending:collect()
                db.commit()
        C.need(dict(tables)==C.COUNTS and processed==C.TOTAL,'EVERY_ORIGINAL_PHYSICAL_ROW_EXACT_ONCE')
        C.need(original=={'rows':2939137,'no_key':2207,'present_unresolved':2970,'missing':3777,'disagreement':30},'ORIGINAL_UNKNOWN_VARIANT_DISAGREEMENT_COUNTERS_PRESERVED')
        C.need(all(counters['FK_'+k]==n for k,n in expected_fk.items()),'ORIGINAL_ENTRY_NULL_AND_ORPHAN_COUNTS_RETAINED')
        C.need(db.execute('SELECT count(*) FROM properties p LEFT JOIN molecules m ON p.mid=m.mid WHERE m.mid IS NULL').fetchone()[0]==0,'ORIGINAL_PROPERTY_FK_ALL_SOURCE_CROSSCHECK')
        complete=True
    except RuntimeError:
        if not budget.stop:raise
        while pending:collect()
    finally:
        db.commit();db.close()
    refs={'identities':ident.close(),'physical_audit':audit.close(),'unknown_locators':unknown.close()}
    replay=0
    if complete:
        for row in I.read_jsonl(refs['identities'],budget):K.STATE['consumer'](row);replay+=1
        C.need(replay==counters['strict_rows'],'ORIGINAL_STRICT5_WHOLE_FILE_READBACK')
    coverage={'schema':'expansion_all_source_identity_coverage_v1','dataset':'coconut','all_splits':complete,
      'covered_roles':[plan['role']],'covered_subdatasets':['molecules','entries'],'source_splits_observed':False,
      'expected_identity_records':counters['strict_rows'],'identities':refs['identities'],'raw_artifacts':plan['data_references'],
      'unresolved_without_identity_or_composition':counters['unresolved_without_identity_or_composition'],
      'expected_physical_rows_by_table':C.COUNTS,'observed_physical_rows_by_table':dict(tables),'physical_rows':processed,
      'original_norm_counters':dict(original),'native_FK_counts':{k:counters['FK_'+k] for k in ('MATCHED','NULL','ORPHAN')},
      'original_consumer_all_identity_rows_readback':replay,'no_status_invalid_or_parsefail_drop':True,'norm_recomputed':False,
      'input_receipt_reference':plan['norm_parent']['receipt'],'formula_auxiliary_rows':aux,'global_pool_release':False}
    C.write_new(root/'coverage.json',coverage)
    ready=complete and counters['unresolved_without_identity_or_composition']==0
    C.write_new(root/'receipt.json',{'schema':'COCONUT_STRICT5_DAY_RECEIPT_V1','status':'FULL_STRICT5_CONSERVATIVE_COVERAGE_REQUIRES_ROOT_REVIEW' if ready else 'PHYSICAL_PROJECTED_UNKNOWN_OR_RESOURCE_HOLD_NOT_READY',
      'job_id':str(proof['job_id']),'uid':1264,'node':plan['node'],'endpoint':C.q.ENDPOINT,'plan_reference':C.pin(plan['plan_path']),
      'startup_proof_reference':plan['startup_proof_reference'],'fixture_gate_reference':gate,'coverage_reference':C.pin(root/'coverage.json'),
      'outputs':refs,'complete_physical_source':complete,'READY_candidate':ready,'counters':dict(counters),'actual_C0_not_self_claimed':True,
      'norm_parent':plan['norm_parent'],'input_body_count':47,'runtime':budget.receipt(),'new_QM_UFF_calls':0,
      'raw_inputs_or_norm_outputs_modified':False,'global_decontamination_or_pool_release':False})
    return 0

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    plan,proof=C.startup(Path(a.plan),Path(a.startup_proof),__file__);root=C.literal(plan['output_directory']);C.need(not root.exists(),'FRESH_STRICT5_PARENT_OUTPUT');root.mkdir(parents=True,mode=0o700)
    budget=Budget(plan,proof,root);budget.thread.start()
    try:
        gate=fixtures(root,plan);plan['plan_path']=a.plan;plan['startup_proof_reference']=C.pin(a.startup_proof)
        return execute(plan,proof,root,gate,budget)
    except BaseException as exc:
        import traceback
        C.write_new(root/'failure.json',{'status':'TECHNICAL_FAILURE_NOT_CHEMICAL_EXCLUSION','error':repr(exc),'traceback':traceback.format_exc(),
          'partials_retained':True,'native_or_normalization_retry':False});raise
    finally:budget.close()

if __name__=='__main__':raise SystemExit(main())
