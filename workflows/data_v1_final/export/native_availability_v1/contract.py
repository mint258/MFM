"""Exact finite native-raw metadata scope; no scientific body operations."""
from __future__ import annotations
import csv,io,json,pathlib,re
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q
ROOT=Q.ROOT;REPO=Q.REPO;PY=Q.PY
HERE=REPO/'workflows/data_v1_final/export/native_availability_v1'
MODULE='workflows.data_v1_final.export.native_availability_v1.run'
FILES=('__init__.py','contract.py','prepare.py','reader.py','run.py','metadata.py','test_v1.py','README.md')
CAP=128<<20;WALL=900;METADATA_CAP=2<<20;FRAME_CAP=4<<20
CALCS=('pm7_B','pm7_cation','pm7_anion','pm7_water','pm7_octanol','xtb_singlepoint','xtb_vipea','xtb_vfukui',
       'xtb_ALPB_water','xtb_ALPB_octanol','xtb_fod','xtb_perturbed_gradient')
ARCHIVE=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts/wp5_archive_v4.py')
ARCHIVE5=ARCHIVE.with_name('wp5_archive_v5.py')
OBSERVER=REPO/'workflows/data_v1_final/labels/source_status_cpu_auto_memory_v1'
INPUT_KEYS={'source_prepared','audit_membership','witness','dictionary_manifest','registry'}


def need(ok,code):
    if not ok:raise ValueError(code)


def triple(v):
    r={k:v[k] for k in ('path','bytes','sha256')};p=pathlib.Path(r['path'])
    need(p.is_absolute() and '..' not in p.parts and type(r['bytes']) is int and r['bytes']>=0
         and re.fullmatch('[0-9a-f]{64}',r['sha256']) is not None,'EXACT_LITERAL_DATA_REFERENCE')
    return r


def unique(refs):
    out={}
    for r in refs:
        r=triple(r);need(r['path'] not in out or out[r['path']]==r,'CONFLICTING_REFERENCE');out[r['path']]=r
    return [out[k] for k in sorted(out)]


def meta(r):
    r=triple(r);need(r['bytes']<=METADATA_CAP and Q.pin(r['path'])==r,'EXACT_SMALL_METADATA_PIN')
    return Q.load(r['path'])


def parameters(mode):
    need(mode in {'prepare','probe'},'EXACT_TWO_STAGE_MODE')
    return {'mode':mode,'maximum_records':32,'maximum_explicit_execution_keys':384,'workers':16,
        'new_pure_methods':3,'fixtures_before_resource_observer':True,'new_QM_calls':0,'new_UFF_calls':0,
        'catalog_and_archives_are_DATA':True,'archive_open_allowed':mode=='probe',
        'raw_frame_or_parsed_or_wire_BLOB_allowed':False,'metadata_frame_only':True,
        'maximum_metadata_bytes':METADATA_CAP,'maximum_metadata_frame_bytes':FRAME_CAP,
        'input_body_state':'HASH_ONLY_NOT_SAVED','native_tokens_and_frame':'PENDING',
        'whole_output_cap_bytes':CAP,'cost_overrun_action':'REPORT_AND_CONTINUE'}


def scope(mode):return 'native_raw_availability_'+mode+'_v1'


def dictionary_references(reference):
    value=meta(reference);out=[];names=set();base=pathlib.Path(reference['path']).parent
    for row in value['dictionaries']:
        calc=row['calc_type'];need(calc in CALCS and calc not in names,'EXACT12_DICTIONARY_TYPES');names.add(calc)
        path=pathlib.Path(row['path']);path=path if path.is_absolute() else base/path
        r=triple({**row,'path':str(path)});need(0<r['bytes']<=METADATA_CAP,'BOUNDED_DICT_BYTES');out.append(r)
    need(names==set(CALCS) and sum(r['bytes'] for r in out)<=16<<20,'BOUNDED12_DICT_DECLARATIONS')
    return unique(out)


def prepare_data(inputs):
    need(set(inputs)==INPUT_KEYS,'EXACT_PREPARATION_SMALL_AUTHORITIES')
    prepared=meta(inputs['source_prepared']);audit=meta(inputs['audit_membership'])
    need(audit['status']=='AUDIT_MEMBERSHIP_CLOSED' and audit['selection']['unit']=='record'
         and audit['selection']['selected_record_all12_complete_outputs'] is True,'ORIGINAL_RECORD_AUDIT_ONLY')
    loc=prepared['authority_locators']
    return unique([audit['selected_records'],prepared['canonical_index'],loc['latest_molecules'],loc['catalog']])


def expected_probe_data(prepared):
    need(prepared['schema']=='NATIVE_RAW_LOCATORS_PREPARATION_V1'
         and prepared['status']=='EXACT_NATIVE_ARCHIVE_LOCATORS_PREPARED_NOT_OPENED'
         and prepared['archives_opened']==0 and len(prepared['selected_records'])==32
         and len(prepared['execution_keys'])==384,'ACTUAL_FINITE_CLOSED_PREPARATION_REQUIRED')
    archives=unique(prepared['archive_data_references'])
    declared={r['path']:r for r in archives}
    for row in prepared['execution_keys']:
        need(row['calc_type'] in CALCS and triple(row['archive_reference'])==declared.get(row['archive_reference']['path'])
             and type(row['execution_id']) is str and bool(row['execution_id']),'EVERY_ARCHIVE_LOCATOR_EXPLICITLY_DECLARED')
    ids=[r['record_id'] for r in prepared['selected_records']]
    need(len(set(ids))==32 and {(r['record_id'],r['calc_type']) for r in prepared['execution_keys']}=={(rid,calc) for rid in ids for calc in CALCS},'EXACT32_BY12_KEY_MATRIX')
    need({r['archive_reference']['path'] for r in prepared['execution_keys']}==set(declared),'NO_UNREFERENCED_ARCHIVE_AUTHORIZATION')
    need(len(archives)<=32 and all(r['bytes']>0 for r in archives),'FINITE_NONEMPTY_ARCHIVE_SET')
    return unique([*archives,*dictionary_references(prepared['input_authority_references']['dictionary_manifest'])])


def closed_preparation(refs):
    need(set(refs)=={'manifest','startup_proof','accounting','raw_accounting'},'EXACT_PREPARATION_CLOSURE_PINS')
    manifest=meta(refs['manifest']);proof=meta(refs['startup_proof']);account=meta(refs['accounting'])
    request=proof['request'];planref=manifest['plan_reference'];plan=meta(planref)
    need(proof['schema']=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1' and proof['uid']==1278
         and request['partition']=='cpu' and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED','MAIN_CPU_PREPARATION_PROOF_IDENTITY')
    need(request['scope_key']==scope('prepare') and request['scope_parameters']==parameters('prepare')
         and manifest['job_id']==str(proof['job_id']) and request['cpus']==16 and request['kind']=='analysis'
         and meta(proof['request_reference'])==request,'EXACT_ACTUAL_PREPARATION_PROOF')
    need(request['execution_argv']==[PY,'-B','-m',MODULE,'--plan',planref['path'],'--startup-proof',refs['startup_proof']['path']]
         and planref in request['source_references'] and pathlib.Path(refs['manifest']['path']).parent==pathlib.Path(plan['output_directory'])
         and manifest['input_authority_references']==plan['input_authority_references'],'EXACT_PARENT_ARGV_PLAN_AND_OUTPUT')
    need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
         and account['endpoint']=='202.38.247.57:22' and account['query_returncode']==0 and account['uid']==1278 and account['raw_sacct_reference']==refs['raw_accounting'],'ACTUAL_PREPARATION_ACCOUNTING')
    raw=pathlib.Path(Q.pin(refs['raw_accounting']['path'])['path']).read_text()
    need(Q.pin(refs['raw_accounting']['path'])==refs['raw_accounting'],'RAW_ACCOUNTING_PIN')
    rows=[r for r in csv.DictReader(io.StringIO(raw),delimiter='|') if r['JobIDRaw']==str(proof['job_id'])]
    need(len(rows)==1 and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0'
         and rows[0]['AllocCPUS']=='16' and rows[0]['UID']=='1278','REAL_PARENT_C0_16_CPU')
    parents=[r for r in account['parents'] if str(r['job_id'])==str(proof['job_id'])]
    need(len(parents)==1 and parents[0]['state']=='COMPLETED' and parents[0]['exit_code']=='0:0'
         and parents[0]['alloc_cpus']==16 and int(rows[0]['ElapsedRaw'])==parents[0]['elapsed_raw_seconds'],'ACCOUNTING_PARENT_PARITY')
    observer=meta(manifest['resource_observation_reference'])
    need(observer['job_id']==str(proof['job_id']) and observer['status']=='RESOURCE_OBSERVATION_CLOSED'
         and observer['soft_stop_requested'] is False and observer['forced_signals_sent'] is False
         and observer['startup_proof_request_reference']==proof['request_reference'],'PREPARATION_OBSERVER_CLOSED_NO_STOP')
    expected_probe_data(manifest)
    return manifest,unique([*refs.values(),planref,proof['request_reference'],manifest['resource_observation_reference']])