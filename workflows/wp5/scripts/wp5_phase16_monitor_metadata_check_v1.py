import ast,copy,hashlib,json,tempfile
from pathlib import Path
import wp5_hourly_observe_v10 as O
import wp5_recovery_hourly_watch_v11 as W
R=O.ROOT
old=ast.parse((R/'scripts/wp5_recovery_hourly_watch_v10.py').read_text());new=ast.parse((R/'scripts/wp5_recovery_hourly_watch_v11.py').read_text())
def fn(t,n):return next(x for x in t.body if isinstance(x,ast.FunctionDef) and x.name==n)
class Scope(ast.NodeTransformer):
 def visit_Constant(self,n):
  if type(n.value)==int and n.value==463:n.value=541
  elif isinstance(n.value,str):n.value=n.value.replace('All6formalphases_only','All7formalphases_only').replace('ALL463_ACCOUNTING','ALL541_ACCOUNTING')
  return n
assert ast.dump(Scope().visit(fn(old,'evaluate_stop_conditions')),include_attributes=False)==ast.dump(fn(new,'evaluate_stop_conditions'),include_attributes=False)
assert ast.dump(fn(old,'publisher_guard'),include_attributes=False)==ast.dump(fn(new,'publisher_guard'),include_attributes=False)
with tempfile.TemporaryDirectory(prefix='wp5_phase16_monitor_metadata_') as tmp:
 paths=list(O.SUBMISSIONS[:6]);d=copy.deepcopy(O.read(paths[-1]));d['prepared_plan']['version']=16
 for i,row in enumerate(d['main']+d['cleanup']):row['job_id']=str(8000000+i)
 p=Path(tmp)/'synthetic_future_receipt.json';p.write_text(json.dumps(d));sel=O.effective_jobs(tuple(paths+[p]))
 assert sel['ready'] and len(sel['actual_cost_job_ids'])==541 and len(sel['effective_job_ids'])==78
 d['main'][0]['node']='synthetic_wrong_node';p.write_text(json.dumps(d));assert not O.effective_jobs(tuple(paths+[p]))['ready']
report={'status':'PHASE16_MONITOR_PRIVATE_METADATA_STATIC_PASS','synthetic_future_receipt_only':True,'actual_future_jobs_claimed':False,'cost_scope_test':541,'latest_scope_test':78,'evaluate_AST_same_except_actual_scope463to541':True,'publisher_guard_AST_identical':True,'queue_read':False,'SCI_read':False,'STOP_written':False,'watch_started':False,'source_shas':{n:hashlib.sha256((R/'scripts'/n).read_bytes()).hexdigest() for n in ('wp5_hourly_observe_v10.py','wp5_recovery_hourly_watch_v11.py')}}
p=R/'reports/phase16_monitor_private_metadata_static_check_v1.json'
with p.open('x') as f:json.dump(report,f,indent=2)
print(json.dumps(report))