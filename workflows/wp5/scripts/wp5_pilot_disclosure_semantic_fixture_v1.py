"""Synthetic local-temp semantic checks of frozen delivery3 disclosure gating; no QM."""
from __future__ import annotations
import argparse,ast,copy,hashlib,importlib.util,json,os,tempfile
from pathlib import Path
BINDINGS=json.loads(r'''{"delivery":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts/wp5_acceptance_delivery_v3.py","sha256":"d8af3311a0de17cec43df7f93a4613dfca99c69d6f5ca6af219fed6921516aaa","bytes":13011},"template":{"path":"/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/acceptance/final_20261016_v1/pilot_disclosure_review_v1.template.json","sha256":"4a004845b832f48ea41ca9071fb75a6a053f06aef31d0f610f898c6b5ad04b93","bytes":72654}}''')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
def save(p,d):
 with p.open('x') as f:json.dump(d,f,sort_keys=True,indent=2);f.write('\n')
def checked(r):
 p=Path(r['path'])
 if p.stat().st_size!=r['bytes'] or sha(p)!=r['sha256'] or len(r['sha256'])!=64:raise ValueError('FROZEN_FIXTURE_SOURCE_OR_TEMPLATE_CHANGED')
 return p
def actual_upper_pilot_gate(source):
 tree=ast.parse(source);main=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='main');nodes=[]
 for node in ast.walk(main):
  if not isinstance(node,ast.If) or not isinstance(node.test,ast.Compare):continue
  test=node.test
  if len(test.ops)!=1 or not isinstance(test.ops[0],ast.NotIn):continue
  if isinstance(test.left,ast.Subscript) and isinstance(test.left.value,ast.Name) and test.left.value.id=='pilot' and isinstance(test.left.slice,ast.Constant) and test.left.slice.value=='status':nodes.append(node)
 if len(nodes)!=1:raise ValueError('UNIQUE_ACTUAL_UPPER_PILOT_GATE_REQUIRED')
 tree=ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(nodes[0])],type_ignores=[]))
 return compile(tree,'<frozen_delivery3_actual_upper_pilot_gate>','exec')
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 if a.out.exists():raise FileExistsError(a.out)
 source_path=checked(BINDINGS['delivery']);template_path=checked(BINDINGS['template']);source=source_path.read_text();template=json.loads(template_path.read_text());upper=actual_upper_pilot_gate(source)
 spec=importlib.util.spec_from_file_location('owned_synthetic_frozen_delivery3',source_path);delivery=importlib.util.module_from_spec(spec);spec.loader.exec_module(delivery)
 import pyarrow as pa,pyarrow.parquet as pq
 cases=[];temp_name=None
 with tempfile.TemporaryDirectory(prefix='wp5_pilot_disclosure_fixture_'+str(os.getuid())+'_',dir='/tmp') as folder:
  temp=Path(folder);temp_name=str(temp)
  if temp.parent!=Path('/tmp') or temp.lstat().st_uid!=os.getuid():raise ValueError('OWNED_LOCAL_SYNTHETIC_TEMP_REQUIRED')
  fake_project=temp/'SYNTHETIC_PROJECT';fake_root=fake_project/'runs/SYNTHETIC_WP5';fake_root.mkdir(parents=True)
  # Only this imported module instance changes ROOT. Its source file and every
  # original report/SCI stay untouched; the guide reference is synthetic too.
  delivery.ROOT=fake_root
  guide=fake_project/'WP5 正式计算行动指南（Codex）.md';guide.write_text('SYNTHETIC GUIDE ONLY. Never production evidence.\n')
  registry=temp/'synthetic_registry.json';save(registry,{'synthetic':True,'entries':[]})
  table=temp/'synthetic_differences.parquet';pq.write_table(pa.table({'synthetic_only':[True,True,True],'record_id':['SYNTHETIC_A','SYNTHETIC_A','SYNTHETIC_B']}),table)
  table_ref={**ref(table),'rows':3}
  pilot={'status':'DIFFERENCES_REQUIRE_REVIEW','difference_rows':3,'unresolved_difference_rows':3,
   'field_counts':[{'registry_id':60,'comparison':'DIFF','count':1},{'registry_id':68,'comparison':'DIFF','count':1},{'registry_id':1,'comparison':'MATCH_BITS','count':1}],
   'comparison_counts_before_scope_classification':{'DIFF':2,'STATUS_OR_N_DIFF':1,'MATCH_BITS':1},
   'classified_difference_counts':{'DIFF':2,'STATUS_OR_N_DIFF':1},'bindings':{'registry_sha256':sha(registry)},'differences':str(table),'synthetic':True}
  pilot_path=temp/'synthetic_pilot.json';save(pilot_path,pilot)
  positive=copy.deepcopy(template);positive.update(status='REVIEWED_DIFFERENCES_DISCLOSED',reviewed_by='SYNTHETIC_FIXTURE_NOT_ROOT_REVIEW',review_statement='SYNTHETIC valid disclosure only. No numerical equality or real review claimed.',synthetic=True,requires_user_scientific_decision=False,individual_causal_attribution_complete=False,not_individually_attributed_rows=3,raw_pilot_status=pilot['status'],raw_field_counts=copy.deepcopy(pilot['field_counts']),evidence=[])
  positive['raw_counts']={k:copy.deepcopy(pilot[k]) for k in ('difference_rows','unresolved_difference_rows','comparison_counts_before_scope_classification','classified_difference_counts')}
  positive['sources']={'pilot':ref(pilot_path),'registry':ref(registry),'guide':ref(guide),'difference_table':table_ref}
  def run(name,value,rejection=None):
   path=temp/(name+'.synthetic_review.json');save(path,value)
   try:result=delivery.pilot_disclosure_review(pilot,pilot_path,path)
   except ValueError as exc:
    if rejection is None or rejection not in str(exc):raise AssertionError(name+': unexpected rejection '+str(exc)) from exc
    cases.append({'case':name,'result':'EXPECTED_REJECTION','guard':str(exc)});return None
   if rejection is not None:raise AssertionError(name+': invalid disclosure was accepted')
   if result['status']!='REVIEWED_DIFFERENCES_DISCLOSED' or result['pilot_numerical_PASS_claimed'] is not False:raise AssertionError('SYNTHETIC_DISCLOSURE_IS_NOT_NUMERICAL_PASS')
   cases.append({'case':name,'result':'EXPECTED_DISCLOSURE_ACCEPTANCE_NOT_NUMERIC_PASS'});return result
  accepted=run('valid_disclosure',positive)
  original_template=copy.deepcopy(template);original_template['synthetic']=True
  run('original_prepared_template_is_not_completed_review',original_template,'CLOSED_EXPLICIT_PILOT_DISCLOSURE_REVIEW_REQUIRED')
  mutations=[('changed_raw_status',lambda v:v.update(raw_pilot_status='PASS'),'PILOT_RAW_STATUS_OR_ALL_FIELD_COUNTS_CHANGED'),
   ('changed_field_counts',lambda v:v['raw_field_counts'][0].update(count=2),'PILOT_RAW_STATUS_OR_ALL_FIELD_COUNTS_CHANGED'),
   ('changed_raw_difference_count',lambda v:v['raw_counts'].update(difference_rows=4),'PILOT_RAW_DIFFERENCE_COUNTS_CHANGED'),
   ('changed_unresolved_count',lambda v:v['raw_counts'].update(unresolved_difference_rows=0),'PILOT_RAW_DIFFERENCE_COUNTS_CHANGED'),
   ('changed_classification_counts',lambda v:v['raw_counts']['classified_difference_counts'].update(DIFF=3),'PILOT_RAW_DIFFERENCE_COUNTS_CHANGED'),
   ('changed_difference_table_row_count',lambda v:v['sources']['difference_table'].update(rows=4),'PILOT_FULL_DIFFERENCE_TABLE_COUNT_DIFFERS'),
   ('changed_difference_table_sha',lambda v:v['sources']['difference_table'].update(sha256='0'*64),'PILOT_REVIEW_REFERENCE_SHA_DIFFERS'),
   ('changed_tolerance_flag',lambda v:v.update(tolerances_relaxed=True),'PILOT_REVIEW_MUTATION_OR_TOLERANCE_EXCEPTION_FORBIDDEN')]
  for name,mutate,guard in mutations:
   value=copy.deepcopy(positive);mutate(value);run(name,value,guard)
  environment={'pilot':pilot,'disclosure':accepted,'decision':[]};exec(upper,environment)
  if environment['decision']:raise AssertionError('VALID_DISCLOSURE_WAS_NOT_RELEASED_BY_ACTUAL_UPPER_GATE')
  cases.append({'case':'actual_upper_gate_valid_disclosure','result':'NO_NEW_PENDING_DECISION'})
  pending_value=copy.deepcopy(positive);pending_value['requires_user_scientific_decision']=True
  pending=run('valid_disclosure_with_scientific_decision_required',pending_value)
  environment={'pilot':pilot,'disclosure':pending,'decision':[]};exec(upper,environment)
  if len(environment['decision'])!=1:raise AssertionError('ACTUAL_UPPER_GATE_DID_NOT_PRESERVE_SCIENTIFIC_DECISION_PENDING')
  cases.append({'case':'actual_upper_gate_scientific_decision_required','result':'EXPECTED_PENDING_DECISION','message':environment['decision'][0]})
 for r in BINDINGS.values():checked(r)
 if Path(temp_name).exists():raise AssertionError('SYNTHETIC_TEMP_NOT_CLEANED')
 a.out.parent.mkdir(parents=True,exist_ok=True)
 report={'status':'SEMANTIC_FIXTURE_PASS_SYNTHETIC_ONLY','cases':cases,'case_count':len(cases),'source_bindings':BINDINGS,'script_sha256':sha(__file__),
  'fixture_temp':temp_name,'fixture_temp_absent':True,'valid_case_is_not_a_final_review':True,'original_SCI_or_report_mutated':False,'original_scientific_data_opened':False,'original_metadata_read':['delivery3 source','prepared review template'],
  'actual_upper_pending_gate_compiled_from_frozen_source_AST':True,'module_instance_ROOT_redirected_only_to_owned_synthetic_tree':True,'new_QM_calls':0}
 save(a.out,report);print(json.dumps({'status':report['status'],'cases':len(cases),'report':str(a.out)}))
if __name__=='__main__':main()
