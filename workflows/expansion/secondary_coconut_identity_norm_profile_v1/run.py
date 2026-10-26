"""Sample actual A identity rows; direct frozen-key helpers, no all-source release."""
import argparse,concurrent.futures as cf,hashlib,importlib,json,multiprocessing as mp,os,random,stat,sys,time,unittest
from collections import Counter
from pathlib import Path
from . import contracts as c
from .runtime import Budget

FIELDS={'molecules':('id','identifier','canonical_smiles','standard_inchi','standard_inchi_key','parent_id','status','active',
 'has_variants','has_stereo','is_tautomer','is_parent','is_placeholder','is_duplicate','has_issues'),
 'entries':('id','canonical_smiles','standardized_canonical_smiles','parent_canonical_smiles','molecule_id','collection_id','status','is_invalid')}
RAW_COLUMNS=('source_table','copy_block','source_row_ordinal','source_offset','source_bytes','source_row_sha256','identity_fields_json')
WORKER={}

def observe_environment():
    import numpy as np
    import pyarrow as pa
    from rdkit import rdBase
    return {'actual_versions':{'python':sys.version.split()[0],'numpy':str(np.__version__),
        'RDKit':str(rdBase.rdkitVersion),'pyarrow':str(pa.__version__)},
      'observed_before_fixtures_and_A_body_reads':True,'required_Alpha_pyarrow_version':'17.0.0',
      'Main_pyarrow_major_provenance':25,'Alpha_pyarrow_matches_Main_build_claimed':False,
      'Main_pyarrow_version_observed_by_this_Alpha_job':False}

def load_kernel(plan):
    """Direct unchanged function objects; full source-file SHA, not a wrapper AST claim."""
    began=time.process_time();projection=importlib.import_module('workflows.expansion.identity_v2.projection_v2')
    common=importlib.import_module('workflows.expansion.common')
    for name,module in (('projection',projection),('common',common)):
        expected=plan['frozen_identity_source_references'][name];relative,size,sha=c.FROZEN[name]
        c.need(Path(module.__file__).absolute()==c.ROOT/'code'/relative==Path(expected['path']) and
          c.pin(module.__file__)==expected and expected['bytes']==size and expected['sha256']==sha,'ACTUAL_UNCHANGED_FROZEN_MODULE_OBJECT')
    source_pins=[]
    for name,module in list(sys.modules.items()):
        if name=='workflows' or name.startswith('workflows.expansion'):
            file=getattr(module,'__file__',None)
            if file and Path(file).suffix=='.py':
                pin=c.pin(file);c.need(pin in plan['source_references'],'EVERY_ACTUAL_TRANSITIVE_FROZEN_MODULE_PIN');source_pins.append(pin)
    projection.rdkit_identity_modules()
    functions={'full_keys':projection.full_keys,'source_smiles_keys':projection.source_smiles_keys,'wp5_key':common.wp5_key}
    proof={'basis':'DIRECT_FROZEN_FUNCTION_OBJECTS_WITH_EXACT_FULL_FILE_BYTES','new_wrapper_AST_equals_old_claimed':False,
      'function_sources':{name:{'qualified_name':f.__module__+'.'+f.__qualname__,'filename':f.__code__.co_filename,'first_line':f.__code__.co_firstlineno} for name,f in functions.items()},
      'exact_transitive_source_references':source_pins,'RDKit_version':'2025.09.5','initialization_CPU_seconds':time.process_time()-began}
    return functions,proof

def normalize(row,functions):
    """Preserve the complete selected A physical row and all variant observations."""
    c.need(set(row)==set(RAW_COLUMNS) and row['source_table'] in FIELDS,'EXACT_A_RAW_IDENTITY_ROW_SCHEMA')
    text=row['identity_fields_json'];c.need(isinstance(text,str) and len(text.encode())<=2*1024**2,'SOURCE_JSON_CONTAINER_BUDGET_STOP_NO_TRUNCATION')
    fields=json.loads(text);table=row['source_table'];c.need(set(fields)==set(FIELDS[table]),'EXACT_IDENTITY_STATUS_LINK_ALLOWLIST')
    c.need(all(v is None or isinstance(v,str) for v in fields.values()),'ORIGINAL_COPY_TEXT_OR_NULL_ONLY')
    names=('canonical_smiles',) if table=='molecules' else ('canonical_smiles','standardized_canonical_smiles','parent_canonical_smiles')
    stored=fields.get('standard_inchi_key');valid,invalid=functions['full_keys']([stored],strict=False);computed=set();variants=[]
    for name in names:
        value=fields[name]
        if value is None or value=='':variants.append({'source_field':name,'state':'MISSING_OR_EMPTY','keys':[],'errors':[]});continue
        keys,errors=functions['source_smiles_keys']({name:value});computed.update(keys)
        variants.append({'source_field':name,'state':'KEYS_DERIVED' if keys else 'UNRESOLVED_ORIGINAL_VARIANT','keys':keys,'errors':errors})
    union=sorted(set(valid)|computed)
    result={'source':dict(row),'source_full_keys_valid':valid,'source_full_keys_invalid':invalid,'variant_observations':variants,
      'SMILES_derived_full_keys':sorted(computed),'conservative_full_key_union':union,'WP5_keys':sorted({functions['wp5_key'](x) for x in union}),
      'stored_vs_computed_disagreement':bool(valid and computed and set(valid)!=computed),'has_any_valid_full_key':bool(union),
      'unresolved_present_variants':sum(v['state']=='UNRESOLVED_ORIGINAL_VARIANT' for v in variants),'missing_variants':sum(v['state']=='MISSING_OR_EMPTY' for v in variants),
      'original_status_and_invalid_flags_retained':True,'X_or_feature_filter_applied':False,'MolFromInchi_or_chemical_edit_applied':False}
    raw=json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode();c.need(len(raw)<=8*1024**2,'RESULT_CONTAINER_BUDGET_STOP_NO_TRUNCATION')
    return result

def init_worker(plan):
    global WORKER
    functions,proof=load_kernel(plan);WORKER={'functions':functions,'proof':proof}

def work(row):
    started=time.monotonic();cpu=time.process_time();result=normalize(row,WORKER['functions'])
    return {'observation':result,'worker_pid':os.getpid(),'worker_kernel_proof':WORKER['proof'],
      'wall_seconds':time.monotonic()-started,'CPU_seconds':time.process_time()-cpu}

def selected_ordinals(table,n):
    seed=int(hashlib.sha256(('20261026|'+table).encode()).hexdigest(),16)
    return sorted(random.Random(seed).sample(range(n),min(n,10000)))

def verify_source(ref,table,n,budget):
    import pyarrow as pa
    import pyarrow.parquet as pq
    path=c.literal(ref['path']);h=hashlib.sha256();started=time.monotonic();cpu=time.process_time()
    c.need(c.ROOT/'artifacts' in path.parents and not any(p.is_symlink() for p in (path,*path.parents)),'ONLY_REAL_A_OWNED_PARQUET_SOURCE')
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno());c.need(stat.S_ISREG(before.st_mode) and before.st_uid==c.UID and before.st_size==ref['bytes'],'CURRENT_A_PARQUET_UID_BYTES')
        for block in iter(lambda:stream.read(1024**2),b''):budget.dispatch_check();h.update(block)
        after=os.fstat(stream.fileno())
    c.need(h.hexdigest()==ref['sha256'] and c.frame(before)==c.frame(after)==c.frame(path.stat()),'A_PARQUET_CURRENT_FULL_SHA_AND_FRAME')
    parquet=pq.ParquetFile(path);expected=pa.schema([('source_table',pa.string()),('copy_block',pa.int64()),('source_row_ordinal',pa.int64()),
      ('source_offset',pa.int64()),('source_bytes',pa.int64()),('source_row_sha256',pa.string()),('identity_fields_json',pa.string())])
    c.need(parquet.schema_arrow.equals(expected) and parquet.metadata.num_rows==n and sum(parquet.metadata.row_group(i).num_rows for i in range(parquet.num_row_groups))==n,
      'CURRENT_A_FOOTER_SCHEMA_AND_ROW_COUNT')
    c.need(all(parquet.metadata.row_group(i).total_byte_size<=256*1024**2 for i in range(parquet.num_row_groups)),'SOURCE_ROWGROUP_METADATA_CONTAINER_LIMIT_STOP_UNKNOWN')
    return {'reference':ref,'table':table,'current_frame':c.frame(after),'footer_rows':n,'row_groups':parquet.num_row_groups,
      'wall_seconds':time.monotonic()-started,'CPU_seconds':time.process_time()-cpu}

def selected_rows(verified,ordinals,budget):
    import pyarrow.parquet as pq
    path=Path(verified['reference']['path']);c.need(c.frame(path.stat())==verified['current_frame'],'A_FILE_CHANGED_BEFORE_SELECTED_EXTRACTION')
    parquet=pq.ParquetFile(path);cursor=0;position=0
    for group in range(parquet.num_row_groups):
        n=parquet.metadata.row_group(group).num_rows;wanted=[]
        while cursor<len(ordinals) and ordinals[cursor]<position+n:wanted.append(ordinals[cursor]-position);cursor+=1
        if wanted:
            budget.dispatch_check();batch=parquet.read_row_group(group,columns=list(RAW_COLUMNS),use_threads=False)
            for index in wanted:
                row=batch.slice(index,1).to_pylist()[0];c.need(row['source_table']==verified['table'],'SOURCE_TABLE_DIFFERS')
                yield row
        position+=n
    c.need(cursor==len(ordinals) and position==verified['footer_rows'] and c.frame(path.stat())==verified['current_frame'],'SELECTED_ORDINAL_AND_FINAL_FSTAT_CONSERVATION')

class KernelFixtures(unittest.TestCase):
    functions=None
    def test_exact_stored_key_and_WP5_suffix(self):
        key='LFQSCWFLJHTTHZ-UHFFFAOYSA-N';valid,invalid=self.functions['full_keys']([key,'bad',None],strict=False)
        self.assertEqual((valid,invalid),([key],['bad']));self.assertEqual(self.functions['wp5_key'](key),'LFQSCWFLJHTTHZ:N')
    def test_null_invalid_and_status_physical_row_preserved(self):
        fields=dict.fromkeys(FIELDS['entries']);fields.update(id='orphan',status='inactive',is_invalid='t',molecule_id='missing')
        row={x:0 for x in RAW_COLUMNS};row.update(source_table='entries',source_row_sha256='0'*64,identity_fields_json=json.dumps(fields))
        result=normalize(row,self.functions);self.assertEqual(result['source'],row);self.assertFalse(result['has_any_valid_full_key']);self.assertEqual(result['missing_variants'],3)
    def test_original_variants_union_is_direct_helper_output(self):
        fields=dict.fromkeys(FIELDS['entries']);fields.update(canonical_smiles='CCO',standardized_canonical_smiles='CCN',parent_canonical_smiles='CCO',status='invalid')
        row={x:0 for x in RAW_COLUMNS};row.update(source_table='entries',source_row_sha256='0'*64,identity_fields_json=json.dumps(fields))
        actual=normalize(row,self.functions);expected=set()
        for name in ('canonical_smiles','standardized_canonical_smiles','parent_canonical_smiles'):
            keys,errors=self.functions['source_smiles_keys']({name:fields[name]});self.assertFalse(errors);expected.update(keys)
        self.assertEqual(actual['conservative_full_key_union'],sorted(expected));self.assertEqual(actual['source'],row)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--startup-proof',type=Path,required=True)
    args=parser.parse_args();plan,proof,a=c.startup(args.plan,args.startup_proof,__file__)
    out=c.literal(plan['output_directory']);c.need(c.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_PROFILE_OUTPUT_ONLY');out.mkdir(parents=True)
    began=time.monotonic();cpu=time.process_time();budget=Budget(plan,proof,out);writer=None;counts=Counter();worker_counts=Counter();worker_proofs={};verified=[];errors=[];seen=set();observed_n=0
    table_phases={};worker_CPU=Counter();worker_wall=Counter();identity_counts=Counter()
    try:
        environment=observe_environment();c.write_new(out/'actual_environment.json',environment)
        c.need(environment['actual_versions']['pyarrow']=='17.0.0','ACTUAL_ALPHA_ARROW17_REQUIRED_NOT_MAIN25')
        c.need(environment['actual_versions']['RDKit']=='2025.09.5','ACTUAL_FROZEN_RDKIT25095_REQUIRED')
        functions,kernel=load_kernel(plan);KernelFixtures.functions=functions
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(KernelFixtures);c.need(suite.countTestCases()==3,'EXACT_THREE_NEW_NORMALIZATION_FIXTURES')
        tested=unittest.TextTestRunner(verbosity=2).run(suite);fixtures={'tests_run':tested.testsRun,'failures':len(tested.failures),'errors':len(tested.errors),'skips':len(tested.skipped),'before_A_body_IO':True}
        c.write_new(out/'fixtures.json',fixtures);c.need(tested.wasSuccessful() and tested.testsRun==3 and not tested.skipped,'GUARDED_FIXTURES_BEFORE_A_BODY_IO')
        budget.thread.start();budget.dispatch_check();ordinals={}
        for table,ref in zip(('molecules','entries'),plan['data_references']):
            n=a['inventory']['reconciliation']['projected_rows_by_table'][table];verified.append(verify_source(ref,table,n,budget));ordinals[table]=selected_ordinals(table,n)
        c.write_new(out/'selected_ordinals.json',{'seed':20261026,'sampler_python_version':sys.version.split()[0],'algorithm':plan['scope_parameters']['ordinal_sampler'],
          'A_full_receipt':plan['a_full_receipt_reference'],'zero_based_Parquet_physical_ordinals':ordinals})
        total=sum(map(len,ordinals.values()));c.need(total>=16,'SAMPLE_TOO_SMALL_TO_CLAIM_SIXTEEN_NONEMPTY_WORKERS')
        import pyarrow as pa
        import pyarrow.parquet as pq
        schema=pa.schema([('source_table',pa.string()),('copy_block',pa.int64()),('source_row_ordinal',pa.int64()),('observation_json',pa.string())])
        writer=pq.ParquetWriter(out/'normalization_observations.parquet',schema,compression='zstd');buffer=[]
        def save(value):
            nonlocal observed_n
            row=value['observation']['source'];key=(row['source_table'],row['copy_block'],row['source_row_ordinal']);c.need(key not in seen,'DUPLICATE_SELECTED_PHYSICAL_A_ROW')
            raw=(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode();c.need(len(raw)<=8*1024**2,'BOUNDED_DURABLE_OBSERVATION')
            budget.capacity(2*len(raw));journal.write(raw);journal.flush();os.fsync(journal.fileno())
            seen.add(key)
            pid=value['worker_pid'];worker_counts[pid]+=1;worker_proofs.setdefault(pid,value['worker_kernel_proof']);observed_n+=1
            worker_CPU[row['source_table']]+=value['CPU_seconds'];worker_wall[row['source_table']]+=value['wall_seconds']
            observation=value['observation'];identity_counts['rows_with_any_valid_full_key']+=int(observation['has_any_valid_full_key'])
            identity_counts['rows_without_any_valid_full_key']+=int(not observation['has_any_valid_full_key'])
            identity_counts['invalid_stored_key_values']+=len(observation['source_full_keys_invalid'])
            identity_counts['unresolved_present_variants']+=observation['unresolved_present_variants'];identity_counts['missing_variants']+=observation['missing_variants']
            identity_counts['rows_stored_vs_computed_disagreement']+=int(observation['stored_vs_computed_disagreement'])
            blob=json.dumps(value['observation'],ensure_ascii=False,separators=(',',':'),allow_nan=False)
            buffer.append({'source_table':key[0],'copy_block':key[1],'source_row_ordinal':key[2],'observation_json':blob})
            counts[row['source_table']]+=1
            if len(buffer)>=16:writer.write_table(pa.Table.from_pylist(buffer,schema=schema));buffer.clear()
        with (out/'completed_observations.jsonl').open('xb') as journal:
            with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=init_worker,initargs=(plan,)) as pool:
                active={};stop=False
                for source in verified:
                    table_started=time.monotonic();table_CPU=time.process_time()
                    iterator=iter(selected_rows(source,ordinals[source['table']],budget));exhausted=False
                    while active or not exhausted:
                        if not stop:
                            try:budget.dispatch_check()
                            except Exception as exc:stop=True;errors.append({'stage':'stop_new_dispatch','type':type(exc).__name__,'reason':str(exc)})
                        while not stop and not exhausted and len(active)<32:
                            try:row=next(iterator)
                            except StopIteration:exhausted=True;break
                            except Exception as exc:stop=True;errors.append({'stage':'selected_source','type':type(exc).__name__,'reason':str(exc)});break
                            if len(row['identity_fields_json'].encode())>2*1024**2:
                                stop=True;errors.append({'stage':'source_record_IPC_budget','source_table':row['source_table'],'copy_block':row['copy_block'],'source_row_ordinal':row['source_row_ordinal'],'no_truncation_or_exclusion':True});break
                            try:active[pool.submit(work,row)]=row;budget.workers=list(pool._processes.values())
                            except Exception as exc:
                                stop=True;errors.append({'stage':'submission_failure_natural_drain','source':row,'type':type(exc).__name__,'reason':str(exc)});break
                        if not active:break
                        done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                        for future in done:
                            original=active.pop(future)
                            try:save(future.result())
                            except Exception as exc:
                                stop=True;errors.append({'stage':'technical_observation_failure','source':original,'type':type(exc).__name__,'reason':str(exc)})
                        if stop and not active:break
                    table_phases[source['table']]={'read_decode_dispatch_result_write_wall_seconds':time.monotonic()-table_started,
                      'parent_process_CPU_seconds':time.process_time()-table_CPU,'sum_worker_key_derivation_CPU_seconds':worker_CPU[source['table']],
                      'sum_worker_key_derivation_wall_seconds_not_parent_wall':worker_wall[source['table']]}
                    if stop:break
        if buffer:writer.write_table(pa.Table.from_pylist(buffer,schema=schema));buffer.clear()
        writer.close();writer=None
        for source in verified:c.need(c.frame(Path(source['reference']['path']).stat())==source['current_frame'],'A_INPUT_CHANGED_DURING_PROFILE')
        c.need(pq.ParquetFile(out/'normalization_observations.parquet').metadata.num_rows==observed_n,'ACTUAL_PARQUET_OUTPUT_ROW_COUNT')
        complete=not errors and budget.stop is None and observed_n==total and len(worker_counts)==16 and all(counts[t]==len(ordinals[t]) for t in ordinals)
        budget.close();budget.capacity();outputs=[]
        for path in sorted(out.iterdir()):
            if not path.is_file():continue
            digest=hashlib.sha256();before=path.stat()
            with path.open('rb') as stream:
                for block in iter(lambda:stream.read(1024**2),b''):digest.update(block)
            c.need(c.frame(before)==c.frame(path.stat()),'OWNED_OUTPUT_CHANGED_DURING_FINAL_SHA');outputs.append({'path':str(path),'bytes':before.st_size,'sha256':digest.hexdigest()})
        c.write_new(out/'receipt.json',{'schema':'SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_RECEIPT_V1',
          'status':'SAMPLED_FROZEN_IDENTITY_KEY_OBSERVATIONS_COMPLETE' if complete else 'INCOMPLETE_IDENTITY_PROFILE_UNKNOWNS_PRESERVED',
          'mode':'profile','job_id':str(proof['job_id']),'uid':c.UID,'endpoint':c.q.ENDPOINT,'node':plan['node'],'allocated_cpus':16,
          'plan':c.pin(args.plan),'startup_proof':c.pin(args.startup_proof),'A_full_receipt':plan['a_full_receipt_reference'],'A_full_accounting':plan['a_full_accounting_reference'],
          'A_complete_scope_and_status_orphan_observations':a['inventory']['reconciliation'],'A_other_raw_identity_outputs_preserved':a['physical_output_references'],
          'selected_rows_by_table':{k:len(v) for k,v in ordinals.items()},'observed_rows_by_table':dict(counts),'observed_rows':observed_n,'actual_nonempty_workers':dict(worker_counts),
          'identity_observation_counts_not_exclusions':dict(identity_counts),'table_phase_timings':table_phases,
          'actual_environment':environment,'kernel_proof':kernel,'worker_kernel_proofs':worker_proofs,'fixtures':fixtures,'source_SHA_footer_phases':verified,'outputs':outputs,'errors':errors,
          'maximum_pending':32,'runtime':budget.receipt(),'wall_seconds':time.monotonic()-began,'parent_process_CPU_seconds':time.process_time()-cpu,
          'full_source_normalization_or_identity_acceptance':False,'active_invalid_missing_rows_filtered':False,'source_inputs_modified':False,
          'X_features_neutralization_tautomer_stereo_isotope_edits':False,'UFF_QM_or_pool_training_release':False,'actual_terminal_parent_cost_closure_pending':True,
          'cost_overrun_action':'REPORT_AND_CONTINUE','signals_sent':False})
        return 0 if complete else 1
    except BaseException as exc:
        c.write_new(out/'failure.json',{'status':'IDENTITY_PROFILE_PARTIALS_PRESERVED','type':type(exc).__name__,'error':str(exc),'no_input_modified':True,'signals_sent':False})
        raise
    finally:
        if writer is not None:writer.close()
        if budget.thread.ident is not None and budget.thread.is_alive():budget.close()

if __name__=='__main__':raise SystemExit(main())
