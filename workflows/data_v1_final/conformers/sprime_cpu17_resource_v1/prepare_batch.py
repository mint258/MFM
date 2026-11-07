"""CPU-only original-pointer/baseline preparation for one frozen finite-wave slot."""
from __future__ import annotations
import argparse,json,pathlib,sys
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.sprime_cpu17_resource_v1 import contract as C,runtime_io as R
from workflows.data_v1_final.conformers.sprime_cpu17_resource_v1 import mapping as M

OPTIONS=('config','plan','batch-id','root-preflight','quota-reuse-review','source-mapping-review','output')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in OPTIONS:p.add_argument('--'+name,type=str if name=='batch-id' else pathlib.Path,required=True)
    args=p.parse_args();value,proof,session,config_ref=R.admit(__file__,args,'prepare',OPTIONS)
    M.source_proof();M.fixtures();R.authorized(proof,[C.ref(M.HERE/'mapping.py'),C.ref(M.HERE/'prepare_batch.py')])
    plan_ref=R.input_ref(args.root_preflight,args.plan);plan=C.read(plan_ref)
    C.need(plan['schema']==C.SCHEMAS['plan'] and plan['status']=='BOUNDED_WAVE_FROZEN_IMPORTS_CLOSED'
        and plan['config']==config_ref and plan['imports320_durably_verified'] is True,'FROZEN_SAME_CONFIG_WAVE_REQUIRED')
    R.authorized(proof,[plan['root_review'],plan['draft'],plan['pilot_imports']]);draft=C.read(plan['draft'])
    C.approve_wave(plan['draft'],draft,plan['root_review'],config_ref)
    imports=C.read(plan['pilot_imports'])
    C.need(len(imports)==320 and all(C.read(C.ref(C.ledger_path(row['task_key'])))==row for row in imports),'ALL320_ONCE_IMPORTS_MUST_STILL_MATCH')
    matches=[b for b in plan['batches'] if b['batch_id']==args.batch_id];C.need(len(matches)==1,'UNIQUE_FROZEN_BATCH_REQUIRED');batch=matches[0]
    R.authorized(proof,[batch['tasks']]);C.pinned(batch['tasks'])
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(16);pa.set_io_thread_count(4);selected=pq.read_table(batch['tasks']['path']);metas=selected.to_pylist()
    C.need(len(metas)==batch['molecules'] and len({m['molecule_id'] for m in metas})==len(metas),'EXACT_BATCH_MEMBERSHIP_REQUIRED')
    for meta in metas:
        C.need(meta['task_key']==C.task_key(meta['molecule_id'],meta['cohort']) and meta['cohort'] in {'retry_once','fill_10N'}
            and not C.ledger_path(meta['task_key']).exists(),'CONSUMED_OR_UNKNOWN_ATTEMPT_CANNOT_BE_PREPARED_AGAIN')
    out=R.new_output_directory(args.output,value);budget=R.Budget(proof,session,value,out)
    C.need(budget.observe() is None,'CURRENT_SHARED_ACCOUNT_QUOTA_REQUIRED')
    budget.start_monitor()
    source=M.formal_source(value,proof,args.source_mapping_review)
    db=duckdb.connect();db.execute('SET threads=16');db.execute("SET memory_limit='12GB'");db.register('selected',selected)
    columns=('record_id','molecule_id','source_path','real_index','record_payload_sha256','total_atoms','energy_raw','smiles',
        'QC_molecule_chirality_conflict','QC_molecule_ez_conflict')
    rows=db.execute('SELECT '+','.join('r.'+col for col in columns)+' FROM read_parquet('+C.q(source['path'])+
        ') r JOIN selected USING(molecule_id) ORDER BY r.molecule_id,r.record_id').fetch_arrow_table().to_pylist()
    pointers={m['molecule_id']:[] for m in metas};previous={mid:[] for mid in pointers}
    for row in rows:pointers[row['molecule_id']].append(row)
    manifest=C.read(value['sprime_manifest']);old_refs=[C.triple(r) for r in manifest['references']
        if r['kind']=='conformers' and int(r['file_group']) in {int(m['file_group']) for m in metas}]
    R.authorized(proof,old_refs);observed=[]
    for reference in old_refs:
        path=C.pinned(reference);info=path.stat()
        table=pq.read_table(path,filters=[('molecule_id','in',list(pointers)),('status','=','SUCCESS'),('converged','=',True)])
        for row in table.to_pylist():previous[row['molecule_id']].append(row)
        after=path.stat();C.need((info.st_ino,info.st_size,info.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),'BASELINE_CHANGED_DURING_SELECTED_READ')
        observed.append({'reference':reference,'inode':info.st_ino,'mtime_ns':info.st_mtime_ns,'full_SHA_verified_on_actual_CPU':True})
    tasks=[]
    for meta in metas:
        mid=meta['molecule_id'];old=sorted(previous[mid],key=lambda r:r['sprime_conf_idx'])
        C.need(len(pointers[mid])==meta['expected_conformers']==meta['S_conformers'] and len(old)==meta['Sprime_conformers']
            and len({r['sprime_conf_idx'] for r in old})==len(old),'ORIGINAL_PM7_POINTER_OR_BASELINE_COUNT_ID_CHANGED')
        tasks.append({'meta':meta,'records':pointers[mid],'existing_conformers':old})
    tasks_ref=R.atomic_bytes(out/'tasks.jsonl',b''.join(C.canonical(t)+b'\n' for t in tasks))
    R.write_json_new(out/'prepared.json',{'schema':C.SCHEMAS['prepared'],'status':'ORIGINAL_BATCH_INPUTS_READY_NOT_GENERATED',
        'plan':plan_ref,'batch':batch,'config':config_ref,'tasks':tasks_ref,'formal_source':source,'old_sprime_sources':observed,
        'recipe_config':value['recipe_config'],'kernel_sha256':C.KERNEL_SHA,'molecules':len(tasks),
        'runtime':{'job_id':str(proof['job_id']),'node':proof['node'],'uid':1278},'budget':budget.report(),
        'new_UFF_calls':0,'new_QM_calls':0,'original_data_modified':False,'common_frozen':False})
    db.close()
    budget.close_monitor()


if __name__=='__main__':main()
