"""Small metadata race checks; no training, labels, geometry or scientific metrics."""
import ast,json
from prepare import ROOT,save,sha
source=ROOT/'scripts/report_s_experiment_current_v8.py'
tree=ast.parse(source.read_text());helper=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='wait_for_actual_publication')
class Clock:
    def __init__(self):self.elapsed=0.;self.sleeps=[]
    def time(self):return 1000.+self.elapsed
    def monotonic(self):return self.elapsed
    def sleep(self,seconds):assert 0<seconds<=30;self.sleeps.append(seconds);self.elapsed+=seconds
class Snapshots:
    def __init__(self,rows):self.rows=rows;self.reads=0
    def __truediv__(self,unused):return self
    def read_text(self):i=min(self.reads,len(self.rows)-1);self.reads+=1;return json.dumps(self.rows[i])
def snapshot(parents,**updates):
    row={'status':'ACTUAL_SONMI_REGISTERED_S_PARENT_TIMING_PUBLISHED','publisher_uid':1278,'publisher_hostname':'sonmi','publisher_source_sha256':'bound-source','timestamp':1000.,'parents':parents};row.update(updates);return row
cases=[]
def run(name,rows,deadline=70,expect_error=None):
    clock=Clock();path=Snapshots(rows);ns={'json':json,'ROOT':path,'sha':lambda _: 'bound-source','time':clock,'print':lambda *a,**k:None}
    exec(compile(ast.Module(body=[helper],type_ignores=[]),'<publication-metadata-guard>','exec'),ns)
    try:result=ns['wait_for_actual_publication'](['a','b'],deadline)
    except Exception as exc:
        assert expect_error and isinstance(exc,expect_error),(name,type(exc));result=None
    else:assert expect_error is None and set(result['parents'])>={'a','b'}
    cases.append({'case':name,'reads':path.reads,'simulated_sleep_seconds':clock.elapsed,'expected_error':expect_error.__name__ if expect_error else None})
run('new_segment_appears_after_root_precheck',[snapshot({'a':{}}),snapshot({'a':{},'b':{}})])
assert cases[-1]['simulated_sleep_seconds']==30
run('old_accounting_is_refreshed',[snapshot({'a':{},'b':{}},timestamp=0.),snapshot({'a':{},'b':{}})])
run('missing_parent_never_bypassed',[snapshot({'a':{}})],deadline=65,expect_error=TimeoutError)
assert cases[-1]['simulated_sleep_seconds']==65
run('spoofed_publisher_uid_rejected',[snapshot({'a':{},'b':{}},publisher_uid=0)],expect_error=AssertionError)
run('changed_publisher_source_rejected',[snapshot({'a':{},'b':{}},publisher_source_sha256='changed')],expect_error=AssertionError)
old=ast.parse((ROOT/'scripts/report_s_experiment_current_v7.py').read_text());old_j=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name=='joint_judgment');new_j=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='joint_judgment');assert ast.dump(old_j)==ast.dump(new_j)
out=ROOT/'reports/s_report_publication_race_guard_validation_v1.json';assert not out.exists()
save(out,{'status':'BOUNDED_REAL_PUBLICATION_RACE_WAIT_AND_ORIGINAL_INTEGRITY_GUARDS_PASS','cases':cases,'scientific_metrics_or_rules_changed':False,'source_sha256':sha(source),'metadata_only_validation':True})
print('BOUNDED_PUBLICATION_RACE_GUARD_PASS',len(cases))
