"""Frozen resource predicate metadata controls plus unchanged repository checker."""
import argparse,ast,hashlib,json,pathlib,runpy,subprocess,sys,time,types
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
a=argparse.ArgumentParser();a.add_argument('--output',type=pathlib.Path,required=True);a=a.parse_args()
source=N/'native_B_remaining_GPU_auto_resource_wait_20261029_v5_source/continue_original_B_auto.py'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='4ad45d70b51a7107fe988f5796676a0000af89cad14aafb0fbe245f2b541c273'
mod=ast.parse(source.read_bytes());nodes=[x for x in mod.body if isinstance(x,ast.FunctionDef) and x.name=='foreign_job_terminal'];assert len(nodes)==1
q='4525142|guangyuan|RUNNING|compute-0-21\n';other='4525143|guangyuan|RUNNING|compute-0-21\n'
done='4525142|guangyuan|COMPLETED|0:0|compute-0-21\n';running='4525142|guangyuan|RUNNING|0:0|compute-0-21\n'
cases=[
 ('target_live_between_GPU_processes',[(q+other,0)],False,None),
 ('other_C35_does_not_block',[(other,0),(done,0),(other,0)],True,None),
 ('accounting_lag_stays_live',[('',0),(running,0)],False,None),
 ('cancelled_exact_parent_is_terminal',[('',0),('4525142|guangyuan|CANCELLED by 1275|0:15|compute-0-21\n',0),('',0)],True,None),
 ('queue_owner_mismatch',[('4525142|wrong|RUNNING|compute-0-21\n',0)],None,AssertionError),
 ('target_node_mismatch',[('4525142|guangyuan|RUNNING|compute-0-22\n',0)],None,AssertionError),
 ('failed_queue_transport',[('',1)],None,AssertionError),
 ('duplicate_accounting',[('',0),(done+done,0)],None,AssertionError),
 ('accounting_node_mismatch',[('',0),('4525142|guangyuan|COMPLETED|0:0|compute-0-22\n',0)],None,AssertionError),
 ('requeue_race_after_terminal',[('',0),(done,0),(q,0)],False,None),
 ('missing_parent_accounting',[('',0),('',0)],None,AssertionError),
 ('wrong_parent_accounting',[('',0),('4525143|guangyuan|COMPLETED|0:0|compute-0-21\n',0)],None,AssertionError),
 ('unknown_state_rejected',[('',0),('4525142|guangyuan|UNKNOWN|0:0|compute-0-21\n',0)],None,AssertionError),
 ('completing_target_waits',[(q.replace('RUNNING','COMPLETING'),0)],False,None),
 ('only_unrelated_queue_needs_exact_target_terminal',[(other,0),(running,0)],False,None),
 ('bad_state_suffix_rejected',[('',0),('4525142|guangyuan|COMPLETED invented|0:0|compute-0-21\n',0)],None,AssertionError)]
results=[]
for name,replies,expected,error in cases:
 calls=[];pending=list(replies)
 def fake_run(argv,**kwargs):
  if not pending:raise RuntimeError('Unexpected extra observation')
  calls.append(argv);text,rc=pending.pop(0)
  return types.SimpleNamespace(args=argv,returncode=rc,stdout=text,stderr='' if rc==0 else 'synthetic transport failure')
 namespace=dict(subprocess=types.SimpleNamespace(run=fake_run),time=time)
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),namespace)
 observed_error=None;value=None
 try:value,_=namespace['foreign_job_terminal']()
 except Exception as e:observed_error=type(e)
 assert observed_error is error and (error is not None or value is expected) and not pending,(name,value,observed_error,pending)
 results.append(dict(name=name,PASS=True,observation_calls=len(calls),synthetic_metadata_only=True))
text=source.read_text()
assert text.count("call_command=command+(['--retry-failed'] if finite_index==0 else [])")==1
assert text.count("step=ops.next_member(P,allow_failed=finite_index==0)")==1
assert "assert ops.next_member(P,allow_failed=finite_index==0)==step" in text
assert "assert child.returncode==0,'Original finite coordinator failed/unknown" in text and 'for finite_index in range(81):' in text
out=a.output;assert not out.exists();out.mkdir()
(out/'resource_predicate_controls.json').write_text(json.dumps(dict(schema='Native_B_v5_resource_predicate_metadata_controls_v1',status='PASS',count=len(results),checks=results,source=dict(path=str(source),bytes=len(source.read_bytes()),sha256=hashlib.sha256(source.read_bytes()).hexdigest()),no_live_queue_SSH_sacct_or_GPU_observations=True,no_controller_or_model_execution=True,one_time_first_command_and_future_failure_stop_source_structure_verified=True),indent=2)+'\n')
checker=B/'MFM_model_v3_delivery_integration_v2/tools/check_repository.py'
sys.argv=[str(checker),'--output',str(out/'repository_check.json')]
runpy.run_path(str(checker),run_name='__main__')
