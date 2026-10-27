"""Resource-only bridge; original book/math/reader contracts are unchanged."""
from __future__ import annotations
import csv,io,json,os,sys,unittest
from pathlib import Path
from workflows.data_v1_final.labels.full_recovery_book_v1 import contract as C,io as OI
from workflows.data_v1_final.labels.full_timeout_inventory_cpu13_v1 import contract as IA
HERE=C.REPO/'workflows/data_v1_final/labels/full_recovery_book_cpu13_v1'
FILES=('__init__.py','binding.py','seed.py','run.py','coverage.py','metadata.py','test_binding.py','README.md')
INVENTORY_MODULE=IA.MODULE;INVENTORY_HERE=IA.HERE
MODULE='workflows.data_v1_final.labels.full_recovery_book_cpu13_v1'
ALLOWED_PRODUCERS={INVENTORY_MODULE,MODULE+'.seed',MODULE+'.run'}
REVIEW='ROOT_LABELS_CPU13_INVENTORY_ADOPTION_REVIEW_V1'
load=OI.load;pin=OI.pin;require=OI.require;write_new=OI.write_new;OLD=OI.OLD
frame=OI.frame;reader=OI.reader;hash_stream=OI.hash_stream;read_json=OI.read_json;SoftStop=OI.SoftStop
account_refs=OI.account_refs;start=OI.start;data_ref=OI.data_ref;json_data=OI.json_data;new_root=OI.new_root


def sources():return [*OI.sources(),*(pin(HERE/n) for n in FILES),*(pin(INVENTORY_HERE/n) for n in IA.FILES)]

def actual(refs,module,jid=None):
    C.need(module in ALLOWED_PRODUCERS,'ONLY_EXACT_CPU13_PRODUCERS_NO_LEGACY_NODE_ALIAS')
    account=load(require(refs['accounting']));raw=OLD.small(require(refs['raw'])).decode('utf-8-sig');proof=load(require(refs['proof']))
    req=load(require(proof['request_reference']));sub=load(require(refs['submission']))
    C.need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
      and account['endpoint']=='202.38.247.57:22' and account['uid']==1278 and account['query_returncode']==0
      and account.get('raw_sacct_reference',account.get('raw_sacct_ref'))==refs['raw'] and req==proof['request']==sub['request']
      and sub['sbatch_returncode']==0 and str(sub['job_id'])==str(proof['job_id']),'REAL_REGISTERED_MAIN_PARENT_CHAIN')
    ps=[p for p in account['parents'] if str(p['job_id'])==str(proof['job_id'])]
    C.need(len(ps)==1,'ONE_EXACT_PARENT');p=ps[0]
    C.need((jid is None or str(p['job_id'])==str(jid)) and p['state']=='COMPLETED' and p['exit_code']=='0:0' and p['alloc_cpus']==16,
      'ACTUAL16_C0_REQUIRED_TIMEOUT_ZERO_EXIT_NEVER_C0')
    rows=[r for r in csv.DictReader(raw.splitlines(),delimiter='|') if r.get('JobIDRaw')==str(p['job_id'])]
    C.need(len(rows)==1 and [rows[0][k] for k in ('UID','State','ExitCode','ElapsedRaw','AllocCPUS')]
      ==['1278','COMPLETED','0:0',str(p['elapsed_raw_seconds']),'16'],'RAW_ACTUAL_C0_PARENT_FIELDS')
    C.need(req['execution_argv'][:4]==[C.PY,'-B','-m',module] and proof['request_reference']==sub['request_reference'],
      'EXACT_PRODUCER_MODULE_AND_REQUEST_REFERENCE')
    C.need(proof['schema']=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1' and proof['uid']==1278
      and proof['request']['node']=='compute-0-13' and str(proof['boot_id']).strip(),'ACTUAL_MAIN13_PRODUCER_IDENTITY')
    opt='--plan' if module.endswith(('.seed','.full_timeout_inventory_cpu13_v1.run')) else '--config'
    argv=req['execution_argv'];C.need(len(argv)==10 and argv[4]==opt and argv[6]=='--startup-proof' and argv[8]=='--output'
      and argv[7]==refs['proof']['path'],'EXACT_HISTORICAL_PRIMARY_FULL_OPTIONS')
    declared={r['path']:r for r in req['source_references']}
    C.need(argv[5] in declared,'ACTUAL_CONFIG_OR_PLAN_EXPLICIT_SOURCE_PIN');require(declared[argv[5]])
    C.need(p['node']=='compute-0-13' and proof['node']=='compute-0-13' and rows[0]['NodeList']=='compute-0-13','ACTUAL_PARENT_RAW_PROOF_NODE13_AGREE')
    primary=INVENTORY_HERE/'run.py' if module==INVENTORY_MODULE else HERE/(module.rsplit('.',1)[1]+'.py')
    C.need(declared.get(str(primary))==pin(primary),'ACTUAL_FROZEN_PRIMARY_SOURCE_PIN')
    args=req['execution_argv'];C.need(args.count('--output')==1 and Path(args[args.index('--output')+1])==Path(refs['receipt']['path']).parent,
      'ACTUAL_RECEIPT_ROOT_AND_REGISTERED_OUTPUT')
    return p,req,proof


def admit(proof_path,config_path,key,parameters,cap,wall,required):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    proof=require_startup(proof_path,expected_kind='analysis',expected_source=Path(sys.modules['__main__'].__file__),
      expected_scope_key=key,expected_scope_parameters=parameters,required_references=[pin(config_path),*required])
    req=proof['request'];C.need(req['pilot'] is False and req['cpus']==16 and req['node']=='compute-0-13' and req['wall_seconds']==wall
      and req['estimated_peak_output_bytes']==cap and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED','EXACT_RECOVERY_CPU16_NOMEM_WALL_CAP')
    declared={r['path']:r for r in req['source_references']}
    for r in sources():C.need(declared.get(r['path'])==r,'EXACT_ORIGINAL_AND_NEW_RESOURCE_SOURCE_PINS');require(r)
    return proof


def adoption_shape(review,refs,receipt):
    C.need(review['schema']==REVIEW and review['status']=='ROOT_APPROVED_EXACT_ACTUAL_CPU13_INVENTORY_FOR_NEW_BOOK'
      and review['reviewer']=='root' and review['reason'].strip() and review['endpoint']=='202.38.247.57:22'
      and review['uid']==1278 and review['inventory_node']=='compute-0-13' and review['inventory_module']==INVENTORY_MODULE
      and review['inventory_actual_references']==refs and str(review['inventory_job_id'])==str(receipt['job_id'])
      and str(receipt['job_id']).isdigit() and str(receipt['job_id']) not in ('4521904','4522748')
      and review['original_job_id']=='4521904' and review['original_node']=='compute-0-17'
      and review['original_parent_state']=='TIMEOUT' and review['original_parent_c0'] is False
      and review['old2748_promoted_to_C0'] is False and review['original_allocated_core_seconds']==230592,
      'ROOT_ACTUAL13_ADOPTION_NEVER_PROMOTES_1904_OR_2748')
    C.need(receipt['schema']=='LABELS_FULL_TIMEOUT_READONLY_INVENTORY_RECEIPT_V1' and receipt['status']=='PARTIAL_TIMEOUT_EVIDENCE_NOT_OLD_C0'
      and receipt['node']=='compute-0-13' and receipt['uid']==1278 and receipt['original_parent_c0'] is False
      and receipt['inventory_verification_complete'] is True and receipt['all_old_member_frames_unchanged'] is True
      and receipt['errors']==[] and receipt['quality_hold_fields_verified_windows']==[]
      and receipt['original_parent']['original_parent_state']=='TIMEOUT' and receipt['original_parent']['original_parent_c0'] is False
      and receipt['original_parent']['allocated_core_seconds']==230592 and receipt['resource_adapter']['schema']==IA.ADAPTER
      and receipt['resource_adapter']['current_node']=='compute-0-13' and receipt['resource_adapter']['historical_node']=='compute-0-17'
      and receipt['resource_adapter']['historical_job_id']=='4521904'
      and review['complete_window_part_and_original_quality_evidence_accepted'] is True
      and review['original_science_thresholds_unchanged'] is True,'ACTUAL_COMPLETE_VERIFIED_INVENTORY_NOT_C0_ONLY')
    return review


def inventory_gate(receipt,refs,review_reference):
    review=load(require(review_reference));adoption_shape(review,refs,receipt)
    C.need(load(require(refs['receipt']))==receipt,'ACTUAL_PINNED_INVENTORY_RECEIPT_NOT_CALLER_SUBSTITUTION')
    _,request,_=actual(refs,INVENTORY_MODULE,review['inventory_job_id'])
    plan_reference=next(r for r in request['source_references'] if r['path']==request['execution_argv'][5])
    plan=load(require(plan_reference))
    C.need(receipt['plan_reference']==plan_reference==review['inventory_plan_reference']
      and review['old_parent_actual_references']==plan['original_references']
      and receipt['resource_adapter']['current_primary_reference']==pin(INVENTORY_HERE/'run.py'),
      'ROOT_EXACT_NEW_PLAN_AND_UNCHANGED_HISTORICAL_PARENT_CHAIN')
    expected=[pin(p) for p in sorted(IA.ORIGINAL_HERE.iterdir()) if p.suffix in ('.py','.md')]
    C.need(review['original_inventory_source_references']==expected and all(r in request['source_references'] for r in expected),
      'ROOT_EXACT_ORIGINAL_READONLY_SCIENCE_SOURCES')
    return review


def fixtures(path):
    original=OI.fixtures(Path(path).with_name('original_book_fixtures.json'))
    from .test_binding import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);C.need(suite.countTestCases()==3,'EXACT_THREE_CPU13_BOOK_BINDING_BOUNDARIES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    good=r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses)
    result=write_new(path,{'status':'PASS' if good else 'FAIL_NO_DATA','tests_run':r.testsRun,'transcript':stream.getvalue(),
      'source_reference':pin(HERE/'test_binding.py'),'original_six_reference':original,'scientific_DATA_opened':False})
    C.need(good,'CPU13_BOOK_BINDING3_AFTER_ORIGINAL6_BEFORE_DATA');return result
