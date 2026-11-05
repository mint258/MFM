"""One CPU-only explicit four-SDK full config/role/history/summary audit."""
from __future__ import annotations
import argparse
import io
import time
import traceback
from paired_common import *


def selfchecks(reader,tap):
    checks=[]
    def reject(call):
        try:call()
        except (ValueError,KeyError,TypeError):return
        raise ValueError('Inline negative accepted')
    row={'optimizer_updates':1,'loss':1.25,'valid_label_counts':{'S':2}}
    encoded_row=(json.dumps(row)+'\n').encode()
    parsed=list(reader.mirror_rows(io.BytesIO(encoded_row),'A_plain'))
    require(len(parsed)==1 and parsed[0]['step']==1,'Actual A_plain parser differs');checks.append('A_plain_optimizer_update_step')
    reject(lambda:list(reader.mirror_rows(io.BytesIO(encoded_row+encoded_row),'A_plain')));checks.append('duplicate_committed_update_rejected')
    bad={**row,'optimizer_updates':True}
    reject(lambda:list(reader.mirror_rows(io.BytesIO((json.dumps(bad)+'\n').encode()),'A_plain')));checks.append('boolean_step_rejected')
    header=dict(run_id=next(iter(IDS)),display_name='A_reference_4523976',project='mfm_model_v3_development',entity='')
    header_check(header,'4523976','reference')
    reject(lambda:header_check({**header,'project':'phychem-model-v3'},'4523976','reference'));checks.append('original_paired_project_exact')
    reject(lambda:header_check(header,'4523976','other'));checks.append('undeclared_role_rejected')
    audit=tap.Audit(reader,{})
    scientific={'source/a.py':'sha','source':{'a.py':'different'},'valid_label_counts':{'S':2}}
    flat=reader.flatten(scientific);audit.exact_fields(flat,scientific,'config')
    reject(lambda:audit.exact_fields({**flat,'extra':1},scientific,'config'))
    reject(lambda:audit.exact_fields({},scientific,'summary'));checks.append('literal_fullconfig_summary_missing_extra_rejected')
    require(len(checks)==6,'Six inline parser checks required')
    return dict(scope='INLINE_METADATA_ONLY_NO_ORIGINAL_SDK_FIXTURE',checks=checks,count=6)


def read_journal(raw,reader,deadline):
    require(descriptor(raw['path'],32<<20)==raw,'Exact role journal descriptor differs')
    binding=ref(raw['path'],32<<20);plain=[]
    with Path(raw['path']).open('rb') as stream:
        for number in range(501):
            require(time.monotonic()<deadline,'Paired role-journal deadline exceeded')
            line=stream.readline(reader.MAX_LINE_BYTES+1)
            if not line:break
            require(number<500 and line.endswith(b'\n') and len(line)<=reader.MAX_LINE_BYTES,'Exact bounded500 complete role rows required')
            value=reader.strict_json(line)
            require(set(value)=={'optimizer_updates','loss','gradient_norm','compute_seconds','base_records','native_atoms',
                'consumed_base_records','input_receipt_sha256','valid_label_counts','peak_allocated_bytes'},
                'Every actual paired producer scientific field must remain present')
            require(type(value) is dict and type(value.get('optimizer_updates')) is int
                and value['optimizer_updates']==number+1,'Actual committed role updates1..500 required')
            # The actual existing A_plain parser is the only flattening/step policy.
            parsed=list(reader.mirror_rows(io.BytesIO(line),'A_plain'))
            require(len(parsed)==1 and parsed[0]['step']==number+1,'Original A_plain step mapping differs')
            plain.append(dict(step=number+1,row=value))
    require(len(plain)==500 and plain[-1]['step']==500,'No fixed20 rows may be invented in SDK history')
    return plain,binding


def audit_one(item,case,metadata,journals,reader,tap,inspector,deps,pin,input_ref,source_refs,out,deadline):
    key=item['run_id'];sdk=item['descriptor'];require(descriptor(sdk['path'],128<<20)==sdk,'Exact original SDK descriptor differs')
    sdk_ref=ref(sdk['path'],128<<20);Scanner,Record,_,installed=inspector.load_decoder(read(deps['sources']['decoder_reference']))
    state={'role':None,'audit':None,'header':None};scanner=None
    class Observed:
        def __init__(self):self.value=Record()
        def ParseFromString(self,raw):
            self.value.ParseFromString(raw);kind=self.value.WhichOneof('record_type')
            if kind=='run':
                require(state['role'] is None,'Duplicate actual RunRecord')
                values=reader.native_items(self.value.run.config.update);role=values.get('paired_role')
                require(role in ('reference','candidate'),'Actual original Native config must declare paired_role')
                run=self.value.run;header=dict(run_id=run.run_id,display_name=run.display_name,project=run.project,entity=run.entity)
                require(header['run_id']==key,'Explicit SDK ID differs');header_check(header,case['job_id'],role)
                rows,journal_ref=journals[role]
                context=dict(run_id=key,run_name=f'A_{role}_{case["job_id"]}',project='mfm_model_v3_development',
                    expected_config={**metadata['configuration'],'paired_role':role},expected_summary=tap.merged_summary(rows),mirror_rows=rows)
                state.update(role=role,header=header,audit=tap.Audit(reader,context),context=context,journal_ref=journal_ref)
            if state['audit'] is not None:state['audit'].observe(self.value)
            else:require(kind not in ('history','config','summary'),'Scientific Native content before actual role-bound RunRecord')
        def __getattr__(self,name):return getattr(self.value,name)
    def mirror_factory(config):
        require(state['role'] is not None and config.get('paired_role')==state['role'],'Immutable actual paired role before history required')
        return iter(dict(step=r['step'],row=reader.flatten(r['row'])) for r in journals[state['role']][0])
    class Sink:
        def write(self,raw):return len(raw)
    try:
        scanner=Scanner();scanner.open_for_scan(sdk['path'])
        history=reader.verify_stream(scanner,Observed,Sink(),expected_run_id=key,expected_exit=0,expected_rows=500,
            mirror_factory=mirror_factory,deadline=deadline,max_native_records=500000,max_history_rows=100000,
            max_record_bytes=4<<20,max_export_bytes=64<<20)
        state['audit'].finish()
    finally:
        if scanner is not None:scanner.close()
    _,_,_,after_installed=inspector.load_decoder(read(deps['sources']['decoder_reference']))
    require(installed==after_installed and history['first_explicit_step']==1 and history['last_explicit_step']==500,
        'Actual decoder source or original500-step population differs')
    require(ref(sdk['path'],128<<20)==sdk_ref and ref(state['journal_ref']['path'],32<<20)==state['journal_ref'],
        'Original SDK/journal changed during independent full scan')
    require(time.monotonic()<deadline,'Inclusive per-SDK180s deadline exceeded')
    return write(out,dict(schema='performance_R2_paired_log_verification_v1',scope=SCOPE,status='ALL_SAVED_PAIRED_LOG_FIELDS_MATCHED',
        run_id=key,paired_role=state['role'],model_job_id=case['job_id'],source_pins=pin,inputs=input_ref,
        sdk=sdk_ref,journal=state['journal_ref'],native_RunRecord=state['header'],history=history,
        history_reader_source=deps['sources']['literal_reader'],tap_source=deps['sources']['tap'],installed_decoder_sources=installed,
        full_config_summary_typed_exact=True,raw_before_after_binding_closed=True,source_refs=source_refs,
        expected_config_sha256=tap.digest(state['context']['expected_config']),expected_summary_sha256=tap.digest(state['context']['expected_summary']),
        summary_origin='Per-role recursive last-leaf-value merge over all500 actual journal rows; no global paired summary.json or fixed20 invented as SDK metrics',
        role_source='Actual initial Native config.paired_role; never directory order',
        fixed20_numeric_gate_only_original_GPU_metadata=True,SDK_or_original_journal_payload_exported=False,
        scientific_acceptance=False,standalone_speed_or_R1_capacity_or_B_D5_acceptance=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--inputs-sha256',required=True)
    parser.add_argument('--pins-sha256',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();started=time.monotonic();process=allocation();pin=verify(args.pins_sha256);input_ref=ref(args.inputs)
    require(input_ref['sha256']==args.inputs_sha256,'Actual explicit paired input SHA differs');inputs=bound_inputs(input_ref)
    require(args.output.absolute().parent==HERE.parent and not args.output.exists(),'Fresh explicit owned audit output required')
    args.output.mkdir(mode=0o700);deps=read(HERE/'dependencies.json')
    refs={**deps['sources'],'source_pins':pin,'inputs':input_ref}
    for case in inputs['cases']:
        refs.update({case['job_id']+'_'+key:raw for key,raw in case['refs'].items()})
    before={key:ref(raw['path']) for key,raw in refs.items()};proofs=[];failure=None;mapping={}
    try:
        reader=load(deps['sources']['literal_reader'],'paired_literal749');tap=load(deps['sources']['tap'],'paired_exact_tap2')
        inspector=load(deps['sources']['framing'],'paired_actual_rb_framing')
        write(args.output/'INLINE_METADATA_QA.json',selfchecks(reader,tap))
        for case in inputs['cases']:
            metadata=metadata_case(case);role_rows={role:read_journal(raw,reader,time.monotonic()+180) for role,raw in case['journals'].items()}
            require(role_rows['reference'][0][-1]['row']['consumed_base_records']==role_rows['candidate'][0][-1]['row']['consumed_base_records']
                ==metadata['summary']['consumed_trajectory_base_records'],'Actual paired consumed base-record cursor differs')
            require(all(all(a['row'][key]==b['row'][key] for key in ('base_records','native_atoms','consumed_base_records','input_receipt_sha256'))
                for a,b in zip(role_rows['reference'][0],role_rows['candidate'][0])),'Paired source corpus identity or consumption differs')
            roles=set()
            for item in case['sdks']:
                require(time.monotonic()-started<800,'Finite whole four-SDK audit window exhausted')
                proof=audit_one(item,case,metadata,role_rows,reader,tap,inspector,deps,pin,input_ref,refs,
                    args.output/(item['run_id']+'_VERIFICATION.json'),time.monotonic()+180)
                value=read(proof);require(value['paired_role'] not in roles,'Duplicate role within actual pair')
                roles.add(value['paired_role']);proofs.append(proof);mapping[item['run_id']]=dict(model_job_id=case['job_id'],paired_role=value['paired_role'])
            require(roles=={'reference','candidate'},'Both actual roles required')
        require(len(proofs)==4 and set(mapping)==IDS,'Full four explicit SDKs must close')
        verify(args.pins_sha256);require(before=={key:ref(raw['path']) for key,raw in refs.items()},'Full source/metadata input binding drift')
    except BaseException as error:
        failure=dict(type=type(error).__name__,frames=[dict(file=f.filename,line=f.lineno,function=f.name) for f in traceback.extract_tb(error.__traceback__)[-32:]],
            reason='Bounded_readonly_paired_audit_failed_no_messages_or_payload_exported')
    finally:
        write(args.output/'BATCH_RESULT.json',dict(schema='performance_R2_paired_log_batch_v1',scope=SCOPE,
            status='ALL_FOUR_PAIRED_LOGS_MATCHED_PENDING_ROOT_C0' if failure is None else 'FAILED_HOLD_PRESERVED',
            actual_job_id=process['job_id'],actual_argv=list(sys.orig_argv),actual_allocation=process,
            source_pins=pin,inputs=input_ref,verifications=proofs,actual_native_role_mapping=mapping,
            returncode=int(failure is not None),failure=failure,source_refs_before=before,
            source_refs_after={key:ref(raw['path']) for key,raw in refs.items()},
            actual_outer_C0_not_self_asserted=True,elapsed_seconds=time.monotonic()-started,
            original_SDKs_retained=True,scientific_acceptance=False))
    return int(failure is not None)


if __name__=='__main__':raise SystemExit(main())
