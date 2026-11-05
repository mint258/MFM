"""Historical failed1915 and its six PASS fixtures are evidence, never C0."""
from pathlib import Path
from workflows.data_v1_final.labels.bounded_projection_v1.materialize import load,pin,require,unique,need


def failed_parent(proof_path,accounting_path,fixture_path):
    proof=load(proof_path);request=proof['request'];accounting=load(accounting_path)
    need(str(proof['job_id'])=='4521915' and accounting['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1'
      and accounting['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED' and accounting['query_returncode']==0
      and accounting['uid']==1278,'ACTUAL_KNOWN_FAILED1915_ACCOUNTING')
    parents=[r for r in accounting['parents'] if str(r['job_id'])==str(proof['job_id'])]
    need(len(parents)==1 and parents[0]['state']=='FAILED' and parents[0]['alloc_cpus']==16
      and parents[0]['exit_code']!='0:0','FAILED1915_NOT_PROMOTED_TO_C0')
    raw=accounting['raw_sacct_reference'];path=require(raw);lines=Path(path).read_text(encoding='utf-8-sig').splitlines()
    header=lines[0].split('|');rows=[dict(zip(header,s.split('|'))) for s in lines[1:] if s.split('|')[0]==str(proof['job_id'])]
    need(len(rows)==1 and rows[0]['UID']=='1278' and rows[0]['AllocCPUS']=='16' and rows[0]['State']=='FAILED'
      and rows[0]['ExitCode']==parents[0]['exit_code'],'RAW_FAILED1915_FIELDS')
    need(load(require(proof['request_reference']))==request,'HISTORICAL_FAILED_REQUEST_BINDING')
    argv=request['execution_argv'];need('workflows.data_v1_final.labels.normalization_cache_v1.run' in argv
      and argv.count('--output')==1,'EXACT_OLD_FAILED_PRIMARY')
    output=Path(argv[argv.index('--output')+1]);need(Path(fixture_path)==output/'fixture_gate.json','FAILED1915_FIXTURE_OUTPUT_BINDING')
    fixture=load(fixture_path)
    need(fixture['status']=='PASS' and fixture['tests_run']==6 and fixture['old_fixture_suites_rerun'] is False
      and fixture['real_cache_owner_or_histogram_body_read'] is False,'ACTUAL_OLD_SIX_PASS_DISTINCT_FROM_FAILED_PARENT')
    require(fixture['source_reference'])
    failure=load(output/'failure.json');need('SELECTED_FLOAT_POOL_OWNERSHIP' in failure['error'],'ACTUAL_OLD_BASE_PROJECTION_FAILURE')
    return unique([pin(proof_path),pin(accounting_path),raw,proof['request_reference'],pin(fixture_path),
      fixture['source_reference'],pin(output/'failure.json')])
