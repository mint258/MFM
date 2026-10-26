"""Export only32 canonical raw KV values; never generate or consume an attempt."""
from __future__ import annotations
import argparse,copy,json,os,pathlib,socket,sys,traceback
from . import common as U,driver,guard,source
from .signatures import canonical,sha,compare_signatures

def grouping(rows):
    groups={};seen=set()
    for row in rows:
        origin=row['actual_opened_LMDB'];key=U.raw_key(row['origin_pointer']);identity=(origin,key)
        U.need(identity not in seen,'DUPLICATE_ORIGIN_KEY_STOP_NOT_SILENT_DEDUPLICATION');seen.add(identity)
        groups.setdefault(origin,[]).append(row)
    U.need(sum(len(v) for v in groups.values())==len(rows),'PER_ORIGIN_KEY_GROUP_CONSERVATION')
    return groups

def target(reference,main_root,alpha_root):
    path=pathlib.Path(reference['path']);U.need(main_root in path.parents,'EXPORTED_CHILD_LOCATOR_REQUIRED')
    return dict(reference,path=str(alpha_root/path.relative_to(main_root)))

def export_database(path,rows,budget):
    import lmdb
    size=U.map_size(sum(row['raw_bytes'] for row in rows),os.sysconf('SC_PAGE_SIZE'))
    budget.observe(reserve=size);U.need(budget.stop is None,budget.stop or 'PREWRITE_RESOURCE_STOP')
    expected={U.raw_key(row['origin_pointer']):row['opaque_original_value'] for row in rows}
    U.need(len(expected)==len(rows),'DUPLICATE_ORIGIN_KEYS_NOT_ACCEPTED')
    env=lmdb.open(str(path),subdir=False,map_size=size,readonly=False,create=True,lock=True,sync=True,metasync=True,max_dbs=1)
    try:
        with env.begin(write=True) as tx:
            for key,value in sorted(expected.items()):U.need(tx.put(key,value,overwrite=False),'NEW_DB_OVERWRITE_FORBIDDEN')
        env.sync(True)
    finally:env.close()
    # A genuinely reopened read-only environment compares original value bytes,
    # not an object obtained by serializing the decoded PyG value again.
    with lmdb.open(str(path),subdir=False,readonly=True,create=False,lock=False,readahead=False) as verify:
        with verify.begin() as tx:
            observed={bytes(key):bytes(value) for key,value in tx.cursor()}
            U.need(observed==expected and verify.stat()['entries']==len(expected),'REOPENED_SPARSE_LMDB_KEY_VALUE_BYTES_DRIFT')
    return {'reference':U.pin(path),'map_size_bytes':size,'logical_records':len(rows),'unique_keys':len(expected),
        'raw_value_bytes':sum(map(len,expected.values())),'all_original_KV_bytes_equal_after_reopen':True,
        'key_value_hashes':[{'key_hex':key.hex(),'value_bytes':len(value),'value_sha256':sha(value)} for key,value in sorted(expected.items())]}

def selected_inputs(prepared,authority):
    tasks={};baselines={}
    for reference in prepared['baseline_packets']:
        value=U.load(reference);mid=value['molecule_id']
        U.need(mid not in baselines and value['schema']=='N1_ORIGINAL_BASELINE_PACKET_V2','UNIQUE_ORIGINAL_BASELINE32')
        baselines[mid]=(reference,value)
    for reference in prepared['tasks']:
        value=U.load(reference);mid=value['meta']['molecule_id']
        U.need(mid not in tasks and value['schema']=='N1_PPRIME2_PILOT_TASK_V2' and len(value['records'])==1
            and len(value['existing_conformers'])==1 and value['meta']['source_N']==1
            and value['meta']['accepted_baseline_count']==1 and value['final_common_reference'] is None,'EXACT_ORIGINAL_N1_TASK32')
        baseline_ref,baseline=baselines[mid];pointer=value['records'][0]
        U.need(value['authority_references']['accepted_baseline_evidence']==baseline_ref
            and value['authority_references']['source_population_authority']==prepared['source_population_authority']
            and baseline['source_population_authority']==prepared['source_population_authority']
            and pointer['molecule_id']==mid and sha(canonical(baseline['original_row']))==value['baseline_row_sha256']
            and value['existing_conformers'][0]==baseline['original_row'],'TASK_BASELINE_POINTER_IDENTITY_DRIFT')
        U.raw_key(pointer)
        tasks[mid]=(reference,value)
    U.need(len(tasks)==len(baselines)==32 and set(tasks)==set(baselines)==set(authority['selected_molecule_ids'])
        and len({value['records'][0]['record_id'] for _,value in tasks.values()})==32,'EXACT_AUTHORITATIVE32_MOLECULE_RECORD_ROSTER')
    return tasks,baselines

def run(plan,proof,prepared,authority,quota):
    root=U.new_output(plan['output_directory'],U.RUN/'artifacts/conformers/n1_sparse32_readchain_v1')
    budget=U.Budget(root,proof,quota)
    try:
        fixture=driver.fixtures(root,proof['request']['source_references'])
        budget.check();tasks,baselines=selected_inputs(prepared,authority)
        selected_metadata=sum(r['bytes'] for r in [*prepared['tasks'],*prepared['baseline_packets']])
        U.need(selected_metadata+U.TOTAL_RAW_CAP<=U.CAP,'FINITE_SELECTED_INPUT2GIB_UPPER_BOUND')
        inputs=[{'origin_pointer':value['records'][0],'execution_pointer':value['records'][0],'return_raw_value':True}
            for mid,(_,value) in sorted(tasks.items())]
        original=driver.read_pool(inputs,source.context(plan,proof,plan['science_sources'],plan['recipe_reference']),budget)
        U.need(sum(row['raw_bytes'] for row in original)<=U.TOTAL_RAW_CAP,'THIRTY_TWO_RAW_VALUES_TOTAL_SOFTWARE_BOUND')
        by_record={row['record_id']:row for row in original}
        for row in original:
            task=tasks[row['molecule_id']][1];baseline=baselines[row['molecule_id']][1]
            source.validate_graph_against_baseline(row['graph_signature'],baseline['validation'],row['origin_pointer'])
            U.need(row['graph_signature']['atomic_numbers']==task['source_atomic_numbers'],'ORIGINAL_TASK_ATOM_ORDER_DRIFT')
        for name in ('sparse_lmdb','origin_tasks','origin_baselines','main_signatures','original_sources','metadata'):(root/name).mkdir()
        groups=grouping(original);databases=[];map_total=0
        U.need(sum(U.map_size(sum(row['raw_bytes'] for row in rows),os.sysconf('SC_PAGE_SIZE')) for rows in groups.values())<=U.MAP_TOTAL_CAP,
            'AGGREGATE_MAP_SOFTWARE_BOUND_BEFORE_ANY_SPARSE_DB_WRITE')
        for origin,rows in sorted(groups.items()):
            budget.check();group_id=sha(origin.encode());database=export_database(root/'sparse_lmdb'/(group_id+'.lmdb'),rows,budget)
            map_total+=database['map_size_bytes'];U.need(map_total<=U.MAP_TOTAL_CAP,'AGGREGATE_MAP1GIB_SOFTWARE_BOUND')
            database.update(origin_source_path=origin,group_id=group_id,
                origin_source_file_frame=rows[0]['actual_file_frame'],original_whole_LMDB_SHA256=None)
            U.need(all(row['actual_file_frame']==rows[0]['actual_file_frame'] for row in rows),'SAME_ORIGIN_FILE_IDENTITY')
            for row in rows:row['main_sparse_pointer']=U.execution_pointer(row['origin_pointer'],database['reference']['path'])
            databases.append(database)
        # The same frozen original reader also opens the new sparse databases on
        # Main. Only source_path in a separate execution pointer has changed.
        sparse_items=[{'origin_pointer':row['origin_pointer'],'execution_pointer':row['main_sparse_pointer']} for row in original]
        reread=driver.read_pool(sparse_items,source.context(plan,proof,plan['science_sources'],plan['recipe_reference']),budget)
        comparisons={}
        for actual in reread:
            expected=by_record[actual['record_id']]
            comparison=compare_signatures(expected['field_signature'],actual['field_signature'])
            U.need(actual['raw_sha256']==expected['raw_sha256'] and actual['graph_signature']==expected['graph_signature'] and actual['native_idx']==expected['native_idx']
                and comparison!='FIELD_SIGNATURE_DRIFT','MAIN_SPARSE_ORIGINAL_READ_DRIFT')
            comparisons[actual['record_id']]={'field_comparison':comparison,'actual_sparse_read':actual}
        alpha_root=pathlib.Path(plan['alpha_input_root']);source_copies=[];alpha_sources={}
        for name,reference in plan['science_sources'].items():
            body=U.require(reference,True).read_bytes();copied=U.write_bytes(root/'original_sources'/pathlib.Path(reference['path']).name,body)
            U.need(all(copied[k]==reference[k] for k in ('bytes','sha256')),'ORIGINAL_READER_SOURCE_COPY_BYTES_DRIFT')
            locator=target(copied,root,alpha_root);alpha_sources[name]=locator
            source_copies.append({'name':name,'origin_reference':reference,'main_copy_reference':copied,'alpha_target_locator':locator})
        recipe_origin=plan['recipe_reference'];original_recipe=U.write_bytes(root/'metadata/original_recipe.json',U.require(recipe_origin,True).read_bytes())
        relocated=copy.deepcopy(U.load(recipe_origin))
        relocated['science_source_pins']=[dict(relocated['science_source_pins'][0],path=alpha_sources['legacy']['path']),dict(relocated['science_source_pins'][1],path=alpha_sources['prepare']['path'])]
        relocated['external_output_root']=str(U.ALPHA/'artifacts/n1_sparse32_readchain_v1')
        recipe=U.save(root/'metadata/alpha_recipe.json',relocated)
        records=[];data=[]
        for database in databases:
            locator=target(database['reference'],root,alpha_root);database['alpha_target_locator']=locator;data.append(locator)
        for row in sorted(original,key=lambda r:r['molecule_id']):
            mid=row['molecule_id'];task_ref,task=tasks[mid];base_ref,baseline=baselines[mid];name=sha(mid.encode())+'.json'
            task_copy=U.write_bytes(root/'origin_tasks'/name,U.require(task_ref,True).read_bytes())
            base_copy=U.write_bytes(root/'origin_baselines'/name,U.require(base_ref,True).read_bytes())
            signature=U.save(root/'main_signatures'/name,{k:v for k,v in row.items() if k not in ('opaque_original_value','main_sparse_pointer')})
            database=next(db for db in databases if db['origin_source_path']==row['actual_opened_LMDB'])
            data.extend([target(task_copy,root,alpha_root),target(base_copy,root,alpha_root),target(signature,root,alpha_root)])
            records.append({'molecule_id':mid,'record_id':row['record_id'],'origin_task_reference':task_ref,'origin_baseline_reference':base_ref,
                'main_task_copy_reference':task_copy,'main_baseline_copy_reference':base_copy,'main_signature_reference':signature,
                'alpha_task_reference':target(task_copy,root,alpha_root),'alpha_baseline_reference':target(base_copy,root,alpha_root),
                'alpha_signature_reference':target(signature,root,alpha_root),'group_id':database['group_id'],
                'origin_pointer':row['origin_pointer'],'origin_pointer_sha256':sha(canonical(row['origin_pointer'])),
                'main_sparse_execution_pointer':row['main_sparse_pointer'],
                'alpha_execution_pointer':U.execution_pointer(row['origin_pointer'],database['alpha_target_locator']['path']),
                'key_hex':row['key_hex'],'raw_value_bytes':row['raw_bytes'],'raw_value_sha256':row['raw_sha256'],
                'main_sparse_original_reader_comparison':comparisons[row['record_id']]['field_comparison']})
        U.need(len({r['path'] for r in data})==len(data) and sum(r['bytes'] for r in data)<=U.CAP,'UNIQUE_EXPECTED_ALPHA_TRANSFER_INPUTS2GIB')
        budget.check()
        manifest={'schema':'MAIN_N1_SPARSE32_EXACT_READCHAIN_EXPORT_V1','status':'ALL32_RAW_KV_EXPORTED_AND_REOPEN_VERIFIED_NO_GENERATION',
            'endpoint':'202.38.247.57:22','uid':os.getuid(),'job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname().split('.')[0],
            'scope_key':guard.MAIN_KEY,'scope_parameters':guard.PARAMETERS,'source_references':proof['request']['source_references'],
            'upstream_references':{k:plan[k] for k in ('prepared_reference','pilot_receipt_reference','science_cost_review_reference','accounting_reference','catalog_reference')},
            'actual_parent_proof_reference':U.pin(plan['actual_proof_path'],True),'fixture_reference':fixture,
            'records':records,'databases':databases,'logical_record_count':32,'unique_molecule_count':32,'unique_KV_count':sum(d['unique_keys'] for d in databases),
            'raw_value_bytes':sum(r['raw_bytes'] for r in original),'selected_input_bytes':selected_metadata+sum(r['raw_bytes'] for r in original),
            'source_LMDB_bodies_fully_hashed':False,'source_record_values_SHA_verified':32,'new_sparse_LMDBs_whole_SHA_verified':len(databases),
            'science_source_copies':source_copies,'alpha_science_sources':alpha_sources,'origin_recipe_reference':recipe_origin,
            'original_recipe_copy_reference':original_recipe,'alpha_original_recipe_reference':target(original_recipe,root,alpha_root),
            'alpha_recipe_copy_reference':recipe,'alpha_recipe_reference':target(recipe,root,alpha_root),
            'alpha_data_references':data,'alpha_expected_input_bytes':sum(r['bytes'] for r in data),
            'alpha_transfer_verified':False,'alpha_target_locations_are_expected_only':True,
            'main_original_read_actual_worker_PIDs':sorted({r['runtime']['pid'] for r in original}),
            'main_sparse_read_actual_worker_PIDs':sorted({r['runtime']['pid'] for r in reread}),
            'complete_field_signatures':sum(r['field_signature']['status']=='COMPLETE_TYPED_SIGNATURE' for r in original),
            'unknown_field_signatures':sum(r['field_signature']['status']!='COMPLETE_TYPED_SIGNATURE' for r in original),
            'dataset_membership':False,'common':False,'production_population_release':False,'new_UFF_calls':0,'new_QM_calls':0,
            'once_ledger_opened':False,'canonical32_attempts_consumed':False,'resource_evidence':budget.report()}
        result=U.save(root/'manifest.json',manifest);U.need(U.usage(root)<=U.CAP,'WHOLE_OUTPUT2GIB');print(json.dumps(result),flush=True);return 0
    except BaseException as exc:
        U.save(root/'failure.json',{'schema':'SPARSE32_MAIN_EXPORT_UNKNOWN_STOP_V1','status':'UNKNOWN_STOP_NO_ALPHA_READY',
            'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc()[-12000:],
            'new_UFF_calls':0,'new_QM_calls':0,'once_ledger_opened':False,'resource_evidence':budget.report()})
        raise

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True,type=pathlib.Path);parser.add_argument('--root-preflight',required=True,type=pathlib.Path)
    args=parser.parse_args();return run(*guard.main_startup(args.plan,args.root_preflight))

if __name__=='__main__':sys.exit(main())
