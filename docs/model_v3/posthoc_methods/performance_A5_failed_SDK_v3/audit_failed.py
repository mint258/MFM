"""Two source-bound failed A5 SDKs: full typed config, no user history/summary."""
from __future__ import annotations
import argparse
import io
import time
import traceback
from failed_common import *


def finish_zero_history(audit,context):
    # tap2.finish requires mirror[-1]; this exact pre-trajectory failure has none.
    # Keep the original tap's config/update/private-key classification, never ignore summary.
    audit.exact_fields(audit.config,context['expected_config'],'config')
    require(audit.headers==[dict(run_id=context['run_id'],display_name=context['run_name'],project=context['project'])]
        and audit.history_started is False,'One actual run and no scientific history required')
    public=audit.public(audit.summary)
    require(public=={},'Original failure path wrote no user summary; unexpected public summary is HOLD')
    return dict(source_summary_file=None,source_user_summary_update_calls=0,scientific_summary_leaf_count=0,
        actual_allowed_SDK_private_summary_keys=sorted(audit.summary),
        actual_native_summary_digest=hashlib.sha256(audit.reader.encoded(audit.summary)).hexdigest(),
        policy='Original tap2.public private-field allowlist only; all other summary fields rejected; no invented final step')


def selfchecks(reader,tap):
    def reject(call):
        try:call()
        except (ValueError,KeyError):return
        raise ValueError('Inline metadata negative accepted')
    require(list(reader.mirror_rows(io.BytesIO(b''),'A_plain'))==[],'Original parser empty population differs')
    header=dict(run_id=IDS[0],display_name='A_reference_'+JOB,project='mfm_model_v3_development',entity='')
    header_check(header,'reference')
    reject(lambda:header_check(header,'candidate'))
    expected=dict(paired_role='reference',source='same',nested={'literal/a':True})
    context=dict(run_id=IDS[0],run_name=header['display_name'],project=header['project'],expected_config=expected)
    audit=tap.Audit(reader,context);audit.config=reader.flatten(expected)
    audit.headers=[{k:header[k] for k in ('run_id','display_name','project')}]
    audit.summary={'_runtime':1.0};finish_zero_history(audit,context)
    audit.summary['loss']=0.;reject(lambda:finish_zero_history(audit,context))
    audit.summary={'unknown_private':None};reject(lambda:finish_zero_history(audit,context))
    audit.summary={'_unrecognized':None};reject(lambda:finish_zero_history(audit,context))
    audit.summary={};audit.config['paired_role']='candidate';reject(lambda:finish_zero_history(audit,context))
    return dict(scope='INLINE_PURE_METADATA_EXISTING_LITERAL_AND_TAP_NO_SDK_FIXTURE',count=4,
        checks=['zero_plain_history_population','actual_header_role_binding',
                'original_private_summary_allowlist_and_public_summary_rejection','full_typed_role_config_mismatch_rejected'])


def audit_one(item,metadata,reader,tap,inspector,deps,pin,input_ref,sources,out,deadline):
    key=item['run_id'];sdk=item['descriptor']
    require(descriptor(sdk['path'],128<<20)==sdk,'Exact original failed SDK descriptor differs')
    sdk_ref=ref(sdk['path'],128<<20);Scanner,Record,_,installed=inspector.load_decoder(read(deps['sources']['decoder_reference']))
    state={'audit':None,'role':None,'header':None};scanner=None
    class Observed:
        def __init__(self):self.value=Record()
        def ParseFromString(self,raw):
            self.value.ParseFromString(raw);kind=self.value.WhichOneof('record_type')
            if kind=='run':
                require(state['audit'] is None,'Duplicate actual RunRecord')
                values=reader.native_items(self.value.run.config.update);role=values.get('paired_role')
                run=self.value.run;header=dict(run_id=run.run_id,display_name=run.display_name,project=run.project,entity=run.entity)
                require(header['run_id']==key,'Exact explicit failed SDK ID differs');header_check(header,role)
                context=dict(run_id=key,run_name='A_'+role+'_'+JOB,project='mfm_model_v3_development',
                    expected_config={**metadata['configuration'],'paired_role':role})
                state.update(role=role,header=header,context=context,audit=tap.Audit(reader,context))
            if state['audit'] is None:
                require(kind not in ('history','config','summary'),'Scientific native content before role-bound RunRecord')
            else:
                state['audit'].observe(self.value)
                if kind in ('run','config'):
                    state['audit'].exact_fields(state['audit'].config,state['context']['expected_config'],'config')
        def __getattr__(self,name):return getattr(self.value,name)
    def mirror_factory(config):
        require(state['audit'] is not None and config.get('paired_role')==state['role'],
            'Actual paired role required and cannot be removed or changed')
        return iter(())
    class Sink:
        def write(self,raw):return len(raw)
    try:
        scanner=Scanner();scanner.open_for_scan(sdk['path'])
        history=reader.verify_stream(scanner,Observed,Sink(),expected_run_id=key,expected_exit=1,expected_rows=0,
            mirror_factory=mirror_factory,deadline=deadline,max_native_records=500000,max_history_rows=100000,
            max_record_bytes=4<<20,max_export_bytes=64<<20)
        summary_observation=finish_zero_history(state['audit'],state['context'])
    finally:
        if scanner is not None:scanner.close()
    _,_,_,after_installed=inspector.load_decoder(read(deps['sources']['decoder_reference']))
    require(installed==after_installed and history['history_rows']==0 and history['first_explicit_step'] is None
        and history['last_explicit_step'] is None and ref(sdk['path'],128<<20)==sdk_ref
        and time.monotonic()<deadline,'Full zero-history/decoder/source/180s binding differs')
    return write(out,dict(schema='A5_failed_zero_history_verification_v2',scope=SCOPE,
        status='FULL_CONFIG_ZERO_HISTORY_FAILED_EXIT_AND_SOURCE_SUMMARY_RULE_MATCHED',model_job_id=JOB,
        run_id=key,paired_role=state['role'],native_RunRecord=state['header'],source_pins=pin,inputs=input_ref,
        sdk=sdk_ref,history=history,summary_observation=summary_observation,
        history_reader_source=deps['sources']['literal_reader'],tap_source=deps['sources']['tap'],
        installed_decoder_sources=installed,source_refs=sources,full_config_typed_exact=True,
        source_summary_rule_exact=True,raw_before_after_binding_closed=True,
        expected_config_sha256=tap.digest(state['context']['expected_config']),
        expected_summary_file=None,expected_summary_values_not_synthesized=True,
        original_failure_preserved=True,scientific_acceptance=False,trajectory500_or_R1_acceptance=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--inputs-sha256',required=True)
    parser.add_argument('--pins-sha256',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();started=time.monotonic();process=allocation();require(process['uid']==1278,'Actual owned CPU UID required')
    pin=verify(args.pins_sha256);input_ref=ref(args.inputs)
    require(input_ref['sha256']==args.inputs_sha256,'Exact failed-log input rawSHA required');inputs=bound_inputs(input_ref)
    require(args.output.absolute().parent==HERE.parent and not args.output.exists(),'Fresh explicit failed-log audit output required')
    args.output.mkdir(mode=0o700);deps=read(HERE/'dependencies.json');metadata=metadata_inputs(inputs)
    files=[HERE/row['relative_path'] for row in read(pin)['files']]+[HERE/'source_pins.json',args.inputs]
    files += [Path(row['path']) for row in deps['sources'].values()]
    files += [Path(row['path']) for row in inputs['refs'].values()]+[Path(inputs['root_closure']['path'])]
    before={str(path):ref(path) for path in files};proofs=[];failure=None;mapping={}
    gate=metadata['Root_negative']['fixed_batch_gate']
    try:
        # Only the exact6.24MB v2 fixed gate has a16MiB raw-hash allowance; never decode it.
        bind(gate,16<<20)
        reader=load(deps['sources']['literal_reader'],'A5_failed_literal749');tap=load(deps['sources']['tap'],'A5_failed_actual_tap2')
        inspector=load(deps['sources']['framing'],'A5_failed_actual_full_rb')
        write(args.output/'INLINE_METADATA_QA.json',selfchecks(reader,tap))
        roles=set()
        for item in inputs['sdks']:
            require(time.monotonic()-started<800,'Finite two-SDK CPU audit window exceeded')
            proof=audit_one(item,metadata,reader,tap,inspector,deps,pin,input_ref,before,
                args.output/(item['run_id']+'_VERIFICATION.json'),time.monotonic()+180)
            cert=read(proof);require(cert['paired_role'] not in roles,'Duplicate actual paired role')
            roles.add(cert['paired_role']);proofs.append(proof);mapping[item['run_id']]=cert['paired_role']
        require(roles=={'reference','candidate'} and set(mapping)==set(IDS),'Both distinct actual native roles and IDs required')
        metadata_inputs(inputs);verify(args.pins_sha256);bind(gate,16<<20)
        require(before=={str(path):ref(path) for path in files},'Source/metadata drift during failed-log audit')
    except BaseException as error:
        failure=dict(type=type(error).__name__,frames=[dict(file=f.filename,line=f.lineno,function=f.name)
            for f in traceback.extract_tb(error.__traceback__)[-32:]],reason='Inspect owned metadata; no messages, credentials or SDK payload exported')
    finally:
        write(args.output/'RESULT.json',dict(schema='A5_failed_log_audit_result_v2',scope=SCOPE,
            status='BOTH_FAILED_ZERO_HISTORY_LOGS_MATCHED_PENDING_ACTUAL_CPU_C0' if failure is None else 'FAILED_HOLD_PRESERVED',
            actual_job_id=process['job_id'],actual_allocation=process,actual_argv=list(sys.orig_argv),
            source_pins=pin,inputs=input_ref,verifications=proofs,actual_native_role_mapping=mapping,
            fixed_gate_raw_binding=gate,fixed_gate_numerical_recomputation=False,returncode=int(failure is not None),failure=failure,
            source_refs_before=before,source_refs_after={str(path):ref(path) for path in files},
            elapsed_seconds=time.monotonic()-started,original_failed_parent_and_SDKs_retained=True,
            actual_outer_C0_not_self_asserted=True,scientific_acceptance=False,trajectory500_or_R1_acceptance=False))
    return int(failure is not None)


if __name__=='__main__':raise SystemExit(main())
