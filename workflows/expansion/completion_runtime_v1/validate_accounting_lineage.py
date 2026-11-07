"""Reproduce legacy/modern scope inheritance against real frozen native metadata."""
import argparse,copy,hashlib,json,os,pathlib,runpy,socket,time
def need(value,message):
    if not value:raise RuntimeError(message)
def ref(path):
    path=pathlib.Path(path);before=path.stat();raw=path.read_bytes();after=path.stat()
    need((before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),'Closed metadata frame')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write(path,value):
    with path.open('x')as f:json.dump(value,f,sort_keys=True);f.write('\n')
    return ref(path)
def key(item):return(item['endpoint'],item['uid'],str(item['job_id']))
def selected(value):
    return {key(item)for name in('parents','active_or_pending_parents_observation_only','missing_native_parent_rows_not_assumed_zero')for item in value[name]}
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in('config','base','old','new','output'):parser.add_argument('--'+name,required=True,type=pathlib.Path)
    args=parser.parse_args()
    need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20','Bounded Main20 metadata validation only')
    wall=time.monotonic();cpu=time.process_time();out=args.output;out.mkdir(mode=0o700,parents=True,exist_ok=False)
    config=json.loads(args.config.read_bytes());base=json.loads(args.base.read_bytes())
    need(base['schema']=='PUBCHEM_INCREMENTAL_ACCOUNTING_SCOPE_DRAFT_V2'and 'active_parents_observation_only'not in base,'Actual current modern-field base, not a synthetic job history')
    active=base['active_or_pending_parents_observation_only'];expected={key(item)for item in base['parents']+active}
    need(len(active)==13 and len(expected)==467,'Actual frozen scope454 terminal plus13 active parents')
    # Isolate inheritance from coincidental rediscovery through runtime or ID lists.
    config.update(base_scope_reference=ref(args.base),declared_alpha_job_ids=[],alpha_runtime_sources_reference=write(out/'empty_runtime_fixture.json',dict(runtime_parent_sources=[])))
    old=runpy.run_path(str(args.old),run_name='_old_lineage')['build']
    new=runpy.run_path(str(args.new),run_name='_new_lineage')['build']
    before=old(copy.deepcopy(config));after=new(copy.deepcopy(config))
    lost=expected-selected(before)
    need(lost=={key(item)for item in active}and selected(after)==expected,'Real modern scope reproduces13 omissions; fixed reader preserves every original parent')
    need(not after['missing_native_parent_rows_not_assumed_zero'],'All restored parents have actual existing native rows')
    details=[dict(case='ACTUAL_MODERN_BASE',old_selected=len(selected(before)),new_selected=len(selected(after)),restored=len(lost))]
    legacy=copy.deepcopy(base);legacy['active_parents_observation_only']=legacy.pop('active_or_pending_parents_observation_only')
    legacy['validation_only_field_layout_view']=True
    legacy_config=copy.deepcopy(config);legacy_config['base_scope_reference']=write(out/'legacy_field_fixture.json',legacy)
    need(selected(old(copy.deepcopy(legacy_config)))==selected(new(copy.deepcopy(legacy_config)))==expected,'Legacy layout remains compatible')
    details.append(dict(case='LEGACY_LAYOUT_COMPATIBILITY',selected=len(expected)))
    dual=copy.deepcopy(base);dual['active_parents_observation_only']=copy.deepcopy(active);dual['validation_only_field_layout_view']=True
    dual_config=copy.deepcopy(config);dual_config['base_scope_reference']=write(out/'dual_field_fixture.json',dual)
    duplicate=new(dual_config)
    need(selected(duplicate)==expected and len(duplicate['parents'])+len(duplicate['active_or_pending_parents_observation_only'])==len(expected),'Dual layouts do not double count native parents')
    details.append(dict(case='DUAL_LAYOUT_DEDUPLICATION',selected=len(expected)))
    missing_config=copy.deepcopy(config);missing_config['accounting_documents']=[]
    missing=new(missing_config)
    need(selected(missing)==expected and len(missing['missing_native_parent_rows_not_assumed_zero'])==467 and not missing['parents']and not missing['active_or_pending_parents_observation_only']and missing['inventory_complete_for_declared_goal_scope']is False,'Missing actual rows stay unavailable, never a completed zero-cost inventory')
    details.append(dict(case='MISSING_NATIVE_REMAINS_EXPLICIT',unavailable_native_parents=467))
    result=dict(schema='PUBCHEM_ACCOUNTING_LINEAGE_NATIVE_REGRESSION_V1',status='PASS',tests=4,actual=dict(uid=os.getuid(),node=socket.gethostname(),pid=os.getpid()),original_base_reference=ref(args.base),original_config_reference=ref(args.config),old_source_reference=ref(args.old),fixed_source_reference=ref(args.new),validator_source_reference=ref(__file__),cases=details,restored_original_parent_identities=[dict(endpoint=a,uid=b,job_id=c)for a,b,c in sorted(lost)],original_history_and_sources_changed=False,artificial_runtime_and_id_rediscovery_disabled_only_to_isolate_lineage=True,native_inputs_still_original_frozen_snapshots=True,current_goal_accounting_or_scientific_completion_not_certified=True,wall_seconds=time.monotonic()-wall,process_CPU_seconds=time.process_time()-cpu)
    result_ref=write(out/'result.json',result)
    print(json.dumps(dict(result_reference=result_ref,status='PASS',tests=4,restored_native_parents=len(lost),old_selected=len(selected(before)),new_selected=len(selected(after)))),flush=True)
if __name__=='__main__':main()
