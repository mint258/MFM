"""One CPU allocation: four exact standalone SDK audits and unchanged speed CLI."""
from __future__ import annotations
import argparse
import io
import math
import subprocess
import time
import traceback
from abba_common import *


def project_step(value,ordinal,*,role,integrated):
    fields={'optimizer_updates','measured','loss','gradient_norm','loader_seconds','compute_seconds',
        'consumed_base_records','valid_label_counts','input','committed_stream','resources'}
    if integrated and role=='candidate':fields.add('performance_execution')
    require(type(value) is dict and set(value)==fields,'Every actual saved steps field must retain original schema')
    require(type(value['optimizer_updates']) is int and value['optimizer_updates']==ordinal
        and type(value['measured']) is bool and value['measured']==(ordinal>2),'Exact2warmup+20measured step population required')
    receipt=value['input'];counts=value['valid_label_counts']
    require(type(receipt) is dict and type(counts) is dict and counts
        and all(type(k) is str and k and type(v) is int and v>=0 for k,v in counts.items()),'Actual valid-label-count mapping required')
    for key in ('base_records','native_atoms'):
        require(type(receipt[key]) is int and receipt[key]>0,'Actual positive native input counts required')
    require(type(value['consumed_base_records']) is int and value['consumed_base_records']>=receipt['base_records'],
        'Actual committed base cursor required')
    for key in ('loss','compute_seconds','loader_seconds'):
        require(type(value[key]) in (int,float) and math.isfinite(value[key]),'Finite original logged scalar required')
    require(value['compute_seconds']>=0 and value['loader_seconds']>=0,'Nonnegative actual timing required')
    return {'optimizer_updates':ordinal,'loss':value['loss'],'compute_seconds':value['compute_seconds'],
        'loader_seconds':value['loader_seconds'],'base_records':receipt['base_records'],'native_atoms':receipt['native_atoms'],
        'consumed_base_records':value['consumed_base_records'],
        **{'valid_label_count/'+key:count for key,count in counts.items()}}


def mirror_for_observed_role(rows,reader,*,native_role,expected_role,header_count):
    # literal749 intentionally projects only paired_role, never single role.
    # Role is captured from the actual RunRecord; full immutable config is
    # separately compared by Audit before each history row and at clean EOF.
    require(header_count==1 and native_role==expected_role and native_role in ROLES,
        'Actual original Native role must be bound before history')
    return iter(dict(step=r['step'],row=reader.flatten(r['row'])) for r in rows)


def selfchecks(reader,tap):
    checks=[]
    def reject(call):
        try:call()
        except (ValueError,KeyError,TypeError):return
        raise ValueError('Inline metadata negative accepted')
    saved=dict(optimizer_updates=1,measured=False,loss=1.25,gradient_norm=8.,loader_seconds=.1,compute_seconds=.2,
        consumed_base_records=2,valid_label_counts={'S':3,'X/Y':4},input={'base_records':2,'native_atoms':8},
        committed_stream={},resources={})
    row=project_step(saved,1,role='reference',integrated=True)
    require(set(row)=={'optimizer_updates','loss','compute_seconds','loader_seconds','base_records','native_atoms',
        'consumed_base_records','valid_label_count/S','valid_label_count/X/Y'}
        and 'gradient_norm' not in row and 'input_receipt_sha256' not in row,'Actual source SDK projection differs')
    checks.append('single_source_projection_omits_nonSDK_fields')
    require(project_step({**saved,'optimizer_updates':3,'measured':True},3,role='reference',integrated=True)['optimizer_updates']==3,
        'Measured step3 mapping differs')
    reject(lambda:project_step({**saved,'optimizer_updates':True},1,role='reference',integrated=True))
    reject(lambda:project_step({**saved,'measured':True},1,role='reference',integrated=True))
    checks.append('exact_warmup_and_integer_update')
    reject(lambda:project_step({k:v for k,v in saved.items() if k!='input'},1,role='reference',integrated=True))
    reject(lambda:project_step({**saved,'unexpected':1},1,role='reference',integrated=True))
    checks.append('saved_schema_missing_extra_rejected')
    line=(json.dumps(row)+'\n').encode()
    require(list(reader.mirror_rows(io.BytesIO(line),'A_plain'))[0]['step']==1,'Actual existing A_plain step parser differs')
    reject(lambda:list(reader.mirror_rows(io.BytesIO(line+line),'A_plain')))
    from types import SimpleNamespace
    projected_config={}
    reader._apply_config(projected_config,SimpleNamespace(update=[
        SimpleNamespace(key='role',nested_key=[],value_json='"reference"')],remove=[]))
    require(projected_config=={},'Actual literal749 single-role projection contract changed')
    rows=[dict(step=1,row=row)]
    require(list(mirror_for_observed_role(rows,reader,native_role='reference',expected_role='reference',header_count=1))[0]['step']==1,
        'RunRecord-bound role must work without a projected config.role')
    reject(lambda:mirror_for_observed_role(rows,reader,native_role=None,expected_role='reference',header_count=0))
    reject(lambda:mirror_for_observed_role(rows,reader,native_role='candidate',expected_role='reference',header_count=1))
    checks.append('actual_A_plain_and_literal749_RunRecord_role_boundary')
    item=dict(run_id='r1000001',job_id='123',role='reference')
    h=dict(run_id=item['run_id'],display_name='A_speed_reference_123',project='mfm_model_v3_development',entity='')
    header_check(h,item,'reference')
    reject(lambda:header_check({**h,'project':'phychem-model-v3'},item,'reference'))
    reject(lambda:header_check(h,item,'candidate'));checks.append('native_role_name_project_exact')
    audit=tap.Audit(reader,{})
    scientific={'loss':1.,'valid_label_count/S':2,'source/a.py':'sha','source':{'a.py':'other'}}
    flat=reader.flatten(scientific);audit.exact_fields(flat,scientific,'config')
    reject(lambda:audit.exact_fields({**flat,'extra':1},scientific,'config'))
    reject(lambda:audit.exact_fields({},scientific,'summary'));checks.append('literal_fullconfig_summary_typed_missing_extra')
    require(len(checks)==6,'Six inline checks required')
    return dict(scope='INLINE_PURE_METADATA_NO_ORIGINAL_SDK_FIXTURE',count=6,checks=checks)


def read_journal(item,metadata,reader,deadline):
    raw=item['step_journal'];require(descriptor(raw['path'],32<<20)==raw,'Exact original steps descriptor differs')
    binding=ref(raw['path'],32<<20);rows=[];receipts=[];consumed=0;base=atoms=0
    integrated='performance_execution_request' in metadata['configuration']
    with Path(raw['path']).open('rb') as stream:
        for number in range(23):
            require(time.monotonic()<deadline,'Bounded source steps deadline exceeded')
            line=stream.readline(reader.MAX_LINE_BYTES+1)
            if not line:break
            require(number<22 and line.endswith(b'\n') and len(line)<=reader.MAX_LINE_BYTES,'Exactly22 complete saved step rows required')
            value=reader.strict_json(line);projected=project_step(value,number+1,role=item['role'],integrated=integrated)
            require(projected['consumed_base_records']==consumed+projected['base_records'],'All committed source base draws must be retained')
            consumed=projected['consumed_base_records']
            if number>=2:
                receipt=value['input']['receipt_sha256']
                require(type(receipt) is str and re.fullmatch('[0-9a-f]{64}',receipt),'Original measured input-receipt SHA required')
                receipts.append(receipt);base+=projected['base_records'];atoms+=projected['native_atoms']
            parsed=list(reader.mirror_rows(io.BytesIO((json.dumps(projected)+'\n').encode()),'A_plain'))
            require(len(parsed)==1 and parsed[0]['step']==number+1,'Existing A_plain explicit step differs')
            rows.append(dict(step=number+1,row=projected))
    require(len(rows)==22 and len(receipts)==20 and base==metadata['summary']['measured_base_records']
        and atoms==metadata['summary']['measured_native_atoms'],'Original full22/measured20 source population differs')
    digest=hashlib.sha256(json.dumps(receipts,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    require(digest==metadata['summary']['input_receipts_sha256'],'All20 measured original receipt identities differ')
    return rows,binding


def audit_one(item,metadata,rows,journal_ref,reader,tap,inspector,deps,pin,input_ref,source_refs,out,deadline):
    key=item['run_id'];sdk=item['SDK'];require(descriptor(sdk['path'],128<<20)==sdk,'Exact original SDK descriptor differs')
    sdk_ref=ref(sdk['path'],128<<20)
    Scanner,Record,_,installed=inspector.load_decoder(read(deps['sources']['decoder_reference']))
    context=dict(run_id=key,run_name=f'A_speed_{item["role"]}_{item["job_id"]}',project='mfm_model_v3_development',
        expected_config=metadata['configuration'],expected_summary=tap.merged_summary(rows),mirror_rows=rows)
    audit=tap.Audit(reader,context);headers=[];native={'role':None};scanner=None
    class Observed:
        def __init__(self):self.value=Record()
        def ParseFromString(self,raw):
            self.value.ParseFromString(raw)
            if self.value.WhichOneof('record_type')=='run':
                require(not headers,'Exactly one actual RunRecord required')
                role=reader.native_items(self.value.run.config.update).get('role')
                run=self.value.run;h=dict(run_id=run.run_id,display_name=run.display_name,project=run.project,entity=run.entity)
                header_check(h,item,role);headers.append(h);native['role']=role
            audit.observe(self.value)
        def __getattr__(self,name):return getattr(self.value,name)
    def mirror_factory(config):
        return mirror_for_observed_role(rows,reader,native_role=native['role'],
            expected_role=item['role'],header_count=len(headers))
    class Sink:
        def write(self,raw):return len(raw)
    try:
        scanner=Scanner();scanner.open_for_scan(sdk['path'])
        history=reader.verify_stream(scanner,Observed,Sink(),expected_run_id=key,expected_exit=0,expected_rows=22,
            mirror_factory=mirror_factory,deadline=deadline,max_native_records=500000,max_history_rows=100000,
            max_record_bytes=4<<20,max_export_bytes=64<<20)
        audit.finish()
    finally:
        if scanner is not None:scanner.close()
    _,_,_,after_installed=inspector.load_decoder(read(deps['sources']['decoder_reference']))
    require(installed==after_installed and len(headers)==1 and history['first_explicit_step']==1 and history['last_explicit_step']==22,
        'Installed decoder or exact original22 rows differs')
    require(ref(sdk['path'],128<<20)==sdk_ref and ref(journal_ref['path'],32<<20)==journal_ref,'Original SDK/steps changed during full scan')
    require(time.monotonic()<deadline,'Inclusive per-SDK180s deadline exceeded')
    return write(out,dict(schema='performance_manual_R1_ABBA_log_verification_v1',scope=SCOPE,
        status='ALL_SAVED_STANDALONE_LOG_FIELDS_MATCHED',position=item['position'],role=item['role'],
        model_job_id=item['job_id'],run_id=key,source_pins=pin,inputs=input_ref,sdk=sdk_ref,journal=journal_ref,
        native_RunRecord=headers[0],history=history,history_reader_source=deps['sources']['literal_reader'],
        tap_source=deps['sources']['tap'],installed_decoder_sources=installed,full_config_summary_typed_exact=True,
        raw_before_after_binding_closed=True,source_refs=source_refs,
        expected_config_sha256=tap.digest(context['expected_config']),expected_summary_sha256=tap.digest(context['expected_summary']),
        summary_origin='Recursive last-leaf merge of all22 code-derived saved-step SDK projections; producer has no explicit summary write',
        history_origin='Original steps.jsonl projected exactly by original single_a_benchmark tracker.log fields',
        role_source='Actual initial Native config.role cross-checked to actual closed member; never directory inference',
        omitted_from_SDK_by_original_source=['gradient_norm','input_receipt_sha256','resources','committed_stream','performance_execution','measured'],
        original_20plus500_numeric_gate_not_invented_as_SDK_rows=True,scientific_acceptance=False))


def original_speed_cli(inputs,deps,output,deadline):
    members=inputs['members'];target=output/'ORIGINAL_A_SPEED_REPORT.json'
    argv=[str(PYTHON),'-B',deps['sources']['speed_report']['path'],'--runs',
        *[str(Path(m['refs']['configuration']['path']).parent) for m in members],
        '--supervisors',*[m['refs']['supervisor']['path'] for m in members],
        '--numeric-gate',inputs['numeric_gate']['directory'],'--output',str(target)]
    intent=write(output/'speed_report_intent.json',dict(argv=argv,source=deps['sources']['speed_report'],
        job_id=os.environ['SLURM_JOB_ID'],status='INTENT_DURABLE_START_NOT_CONFIRMED'))
    tick=time.monotonic();remaining=deadline-tick
    require(remaining>0,'No original speed-report admission window remains')
    with (output/'speed_report.stdout').open('xb') as out,(output/'speed_report.stderr').open('xb') as err:
        done=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=min(120,remaining))
    report=ref(target) if target.exists() else None
    invocation=write(output/'SPEED_REPORT_INVOCATION.json',dict(intent=intent,argv=argv,returncode=done.returncode,
        elapsed_seconds=time.monotonic()-tick,source=deps['sources']['speed_report'],report=report,
        stdout=ref(output/'speed_report.stdout',4<<20),stderr=ref(output/'speed_report.stderr',4<<20),
        job_id=os.environ['SLURM_JOB_ID'],method_or_speed_rules_changed=False))
    require(done.returncode==0 and report is not None,'Original unchanged speed-report CLI failed')
    return report,invocation


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--inputs-sha256',required=True)
    parser.add_argument('--pins-sha256',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();started=time.monotonic();process=allocation();pin=verify(args.pins_sha256);input_ref=ref(args.inputs)
    require(input_ref['sha256']==args.inputs_sha256,'Explicit actual input SHA differs');inputs=bound_inputs(input_ref)
    require(args.output.absolute().parent==HERE.parent and not args.output.exists(),'Fresh explicit owned output required')
    args.output.mkdir(mode=0o700);deps=read(HERE/'dependencies.json')
    refs={**deps['sources'],'source_pins':pin,'inputs':input_ref,'numeric_gate_Root':inputs['numeric_gate']['Root_closure']}
    for name,raw in inputs['numeric_gate']['files'].items():refs['numeric_'+name]=raw
    for item in inputs['members']:
        refs[str(item['position'])+'_Root']=item['root']
        refs.update({str(item['position'])+'_'+key:raw for key,raw in item['refs'].items()})
    before={key:ref(raw['path'],16<<20) for key,raw in refs.items()}
    require(before==refs,'All actual current metadata/source and original gate rawrefs must match')
    proofs=[];failure=None;speed=invocation=None
    try:
        reader=load(deps['sources']['literal_reader'],'R1_actual_literal749');tap=load(deps['sources']['tap'],'R1_exact_tap2')
        inspector=load(deps['sources']['framing'],'R1_actual_rb_framing')
        write(args.output/'INLINE_METADATA_QA.json',selfchecks(reader,tap))
        for item in inputs['members']:
            require(time.monotonic()-started<800,'Finite whole audit/report window exhausted')
            metadata=metadata_member(item);rows,journal_ref=read_journal(item,metadata,reader,time.monotonic()+180)
            proofs.append(audit_one(item,metadata,rows,journal_ref,reader,tap,inspector,deps,pin,input_ref,refs,
                args.output/(item['run_id']+'_VERIFICATION.json'),time.monotonic()+180))
        require(len(proofs)==4,'Every explicit ABBA SDK must close')
        speed,invocation=original_speed_cli(inputs,deps,args.output,started+800)
        verify(args.pins_sha256)
        require(before=={key:ref(raw['path'],16<<20) for key,raw in refs.items()},'All original source/metadata/gate bindings changed')
    except BaseException as error:
        failure=dict(type=type(error).__name__,frames=[dict(file=f.filename,line=f.lineno,function=f.name)
            for f in traceback.extract_tb(error.__traceback__)[-32:]],reason='Bounded_R1_readonly_audit_or_original_speed_report_failed_no_payload_messages')
    finally:
        write(args.output/'BATCH_RESULT.json',dict(schema='performance_manual_R1_ABBA_log_batch_v1',scope=SCOPE,
            status='ALL_FOUR_STANDALONE_LOGS_AND_ORIGINAL_SPEED_REPORT_CLOSED_PENDING_ROOT_C0' if failure is None else 'FAILED_HOLD_PRESERVED',
            actual_job_id=process['job_id'],actual_argv=list(sys.orig_argv),actual_allocation=process,
            source_pins=pin,inputs=input_ref,verifications=proofs,speed_report=speed,speed_report_invocation=invocation,
            returncode=int(failure is not None),failure=failure,source_refs_before=before,
            source_refs_after={key:ref(raw['path'],16<<20) for key,raw in refs.items()},
            actual_outer_C0_not_self_asserted=True,elapsed_seconds=time.monotonic()-started,
            original_SDKs_retained=True,scientific_acceptance=False))
    return int(failure is not None)


if __name__=='__main__':raise SystemExit(main())
