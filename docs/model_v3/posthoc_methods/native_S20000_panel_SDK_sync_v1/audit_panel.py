"""Read only the one5060 SDK/journal on an actual CPU allocation, never on login."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
import math
import sys
import time
from panel_common import *


def journal_row(value,step):
    require(type(value) is dict and type(value.get('step')) is int and value['step']==step,
        'Missing/duplicate/out-of-order committed panel journal step')
    payload={k:v for k,v in value.items() if k!='step'}
    require(len(payload) in (1,4),'Exact ridge or readout row required')
    scopes=set()
    for key,item in payload.items():
        match=METRIC.fullmatch(key)
        require(match is not None and match[2] in TASKS,'Metric outside frozen panel roles/tasks/readouts')
        require(type(item) in (int,float) and math.isfinite(item) and item>=0,'Finite nonnegative saved panel scalar required')
        if match[4] in ('readout/epoch','readout/observed_labels','readout/update'):
            require(int(item)==item,'Readout counter is not an exact nonnegative integer')
        require((match[3]=='ridge')==(match[4]=='validation_error'),'Readout metric type mismatch')
        scopes.add(key.rsplit('/readout/',1)[0] if '/readout/' in key else key.rsplit('/',1)[0])
    require(len(scopes)==1,'One literal scientific metric scope per journal row required')
    if len(payload)==1:require(next(iter(payload)).endswith('/validation_error'),'Ridge scalar required')
    else:require({k.rsplit('/',1)[1] for k in payload}=={'loss','epoch','observed_labels','update'},'Complete readout4 row required')
    return dict(step=step,commit=True,row=payload)


def selfchecks(inputs,metadata,reader,tap):
    passed=[]
    metadata_gate(inputs,metadata['closure'],metadata['result'],metadata['guard'],metadata['request'],metadata['spec'])
    passed.append('actual_saved_metadata_parser_accepts_original_closed5060')
    def reject(call):
        try:call()
        except (ValueError,KeyError,TypeError):return
        raise ValueError('Inline metadata negative was accepted')
    bad=deepcopy(metadata['result']);bad['wandb_run_id']='another-run'
    reject(lambda:metadata_gate(inputs,metadata['closure'],bad,metadata['guard'],metadata['request'],metadata['spec']))
    passed.append('changed_runID_rejected')
    good=dict(run_id=RUN,display_name=metadata['request']['run_id'],project=metadata['request']['wandb_project'],entity='')
    check_header(good,metadata['request']);bad={**good,'project':'mfm_model_v3_development'}
    reject(lambda:check_header(bad,metadata['request']));passed.append('wrong_old_project_rejected')
    key='candidate/cyp.3A4@ridge/validation_error'
    journal_row({'step':0,key:0.5},0)
    reject(lambda:journal_row({'step':1,key:0.5},0));reject(lambda:journal_row({'step':0,key:True},0))
    passed.append('plain_journal_explicitstep_and_bool_scalar_rejected')
    reject(lambda:journal_row({'step':0,'candidate/not-a-task@ridge/validation_error':0.5},0))
    passed.append('undeclared_panel_task_rejected')
    audit=tap.Audit(reader,{})
    literal={'loss':1.0,'loss/S':2.0};flat=reader.flatten(literal)
    audit.exact_fields(flat,literal,'summary')
    reject(lambda:audit.exact_fields({**flat,'extra':0.0},literal,'summary'))
    reject(lambda:audit.exact_fields({next(iter(flat)):1.0},literal,'summary'))
    passed.append('real_literal749_fullfield_comparison_keeps_slash_and_rejects_extra_missing')
    require(len(passed)==6,'Exact six inline parser checks required')
    return dict(scope='INLINE_METADATA_PARSER_ONLY_NO_MODEL_OR_SDK_FIXTURE',checks=passed,count=6)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--inputs-sha256',required=True)
    parser.add_argument('--pins-sha256',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();started=time.monotonic();deadline=started+180
    process=allocation();pin=verify(args.pins_sha256);input_ref=ref(args.inputs)
    require(input_ref['sha256']==args.inputs_sha256,'Actual explicit panel input SHA differs')
    inputs,metadata,expected_config=bound_inputs(input_ref)
    require(not args.output.exists() and args.output.absolute().parent==HERE.parent,'Fresh direct model-owned output required')
    args.output.mkdir(mode=0o700)
    deps=read(HERE/'dependencies.json');sources={**deps['sources'],'source_pins':pin,'inputs':input_ref}
    for key,value in inputs['refs'].items():sources['closed_'+key]=value
    before={name:ref(value['path']) for name,value in sources.items()};failure=None;proof=None;scanner=None
    try:
        reader=load(deps['sources']['literal_reader'],'panel_literal749')
        tap=load(deps['sources']['tap'],'panel_exact_config_summary_tap2')
        inspector=load(deps['sources']['framing'],'panel_actual_rb_framing')
        check=write(args.output/'INLINE_METADATA_QA.json',selfchecks(inputs,metadata,reader,tap))
        journal=inputs['journal_descriptor'];sdk=inputs['sdk_descriptor']
        require(descriptor(journal['path'],32<<20)==journal and descriptor(sdk['path'],128<<20)==sdk,'SDK/journal changed before audit')
        sources['journal']=ref(journal['path'],32<<20);sources['sdk']=ref(sdk['path'],128<<20)
        rows=[];summary={};scope_counts={}
        with Path(journal['path']).open('rb') as stream:
            while True:
                require(time.monotonic()<deadline,'Inclusive panel audit180s exhausted')
                raw=stream.readline(32769)
                if not raw:break
                require(raw.endswith(b'\n') and len(raw)<=32768 and len(rows)<100000,'Truncated/oversized/full-budget panel journal')
                row=journal_row(reader.strict_json(raw),len(rows));rows.append(row)
                summary.update(row['row'])
                scope=next(iter(row['row'])).rsplit('/readout/',1)[0] if len(row['row'])==4 else next(iter(row['row'])).rsplit('/',1)[0]
                scope_counts[scope]=scope_counts.get(scope,0)+1
        result=metadata['result'];require(len(rows)==result['journal_records'],'Full actual journal count differs')
        expected_scopes={f'{role}/{task}@{method}' for role in ('candidate','reference') for task in TASKS for method in ('ridge','linear64_relu')}
        require(set(scope_counts)==expected_scopes,'All36 candidate/reference task-readout scopes required')
        for scope,n in scope_counts.items():
            detail=result['probe_details'][scope]
            require(n==(1 if scope.endswith('@ridge') else detail['history_records']),'Per-readout journal count differs from saved actual producer')
        summary.update(evaluation_status=result['status'],dev_primary_score=result['summaries']['primary_18_cells']['mean_normalized_improvement'])
        context=dict(run_id=RUN,run_name=metadata['request']['run_id'],project=metadata['request']['wandb_project'],
            expected_config=expected_config,expected_summary=summary,mirror_rows=rows)
        audit=tap.Audit(reader,context);headers=[]
        Scanner,Record,_,installed=inspector.load_decoder(read(deps['sources']['decoder_reference']))
        class Observed:
            def __init__(self):self.value=Record()
            def ParseFromString(self,raw):
                self.value.ParseFromString(raw);audit.observe(self.value)
                if self.value.WhichOneof('record_type')=='run':
                    run=self.value.run
                    header=dict(run_id=run.run_id,display_name=run.display_name,project=run.project,entity=run.entity)
                    check_header(header,metadata['request']);headers.append(header)
            def __getattr__(self,key):return getattr(self.value,key)
        class Sink:
            def write(self,raw):return len(raw)
        scanner=Scanner();scanner.open_for_scan(sdk['path'])
        history=reader.verify_stream(scanner,Observed,Sink(),expected_run_id=RUN,expected_exit=0,expected_rows=len(rows),
            mirror_factory=lambda _:iter(dict(step=r['step'],row=reader.flatten(r['row'])) for r in rows),
            deadline=deadline,max_native_records=500000,max_history_rows=100000,max_record_bytes=4<<20,max_export_bytes=64<<20)
        scanner.close();scanner=None;audit.finish()
        _,_,_,installed_after=inspector.load_decoder(read(deps['sources']['decoder_reference']))
        require(installed_after==installed,'Installed decoder source or protobuf descriptor changed during scan')
        require(len(headers)==1,'One full native RunRecord required')
        require(history['first_explicit_step']==0 and history['last_explicit_step']==len(rows)-1
            and history['status']=='VERIFIED_COMMITTED_HISTORY','Full actual explicit panel steps differ')
        after={name:ref(raw['path'],32<<20 if name=='journal' else 128<<20 if name=='sdk' else 2<<20) for name,raw in sources.items()}
        require(after==sources and all(after[name]==raw for name,raw in before.items()),'Source/metadata/original SDK/journal drift')
        require(time.monotonic()<deadline,'Inclusive panel audit180s exhausted after source closure')
        proof=dict(schema='native_S_dev_panel_full_log_comparison_v1',scope=SCOPE,status='ALL_SAVED_PANEL_LOG_FIELDS_MATCHED',
            run_id=RUN,original_model_job_id=MODEL_JOB,inputs=input_ref,source_pins=pin,source_refs=before,
            sdk=sources['sdk'],journal=sources['journal'],native_RunRecord=headers[0],history=history,
            history_reader_source=deps['sources']['literal_reader'],tap_source=deps['sources']['tap'],installed_decoder_sources=installed,
            full_config_summary_typed_exact=True,raw_before_after_binding_closed=True,
            expected_config_sha256=tap.digest(expected_config),expected_summary_sha256=tap.digest(summary),
            summary_origin='code-derived last-value merge of all saved journal scalar fields plus two original explicit summary assignments',
            all36_history_scope_counts=scope_counts,inline_metadata_QA=check,
            source_mirror_or_model_math_independence_not_asserted=True,SDK_payload_or_journal_exported=False,
            original_result_or_Root_closure_modified=False,scientific_acceptance=False,
            budget=dict(sdk_bytes=128<<20,journal_bytes=32<<20,native_records=500000,history_rows=100000,record_bytes=4<<20,
                normalized_bytes=64<<20,wall_seconds=180),elapsed_seconds=time.monotonic()-started)
        proof=write(args.output/'VERIFICATION.json',proof)
    except BaseException as error:
        failure=dict(type=type(error).__name__,message=str(error)[:400],scope='failed_readonly_panel_audit_no_success_inferred')
    finally:
        if scanner is not None:
            try:scanner.close()
            except BaseException as error:failure=failure or dict(type=type(error).__name__,scope='readonly_scanner_close_failed')
        try:verify(args.pins_sha256)
        except BaseException as error:failure=failure or dict(type=type(error).__name__,scope='source_after_failed')
        if time.monotonic()>deadline:failure=failure or dict(type='TimeoutError',scope='inclusive180s_source_close_deadline_exceeded')
        code=int(failure is not None)
        write(args.output/'RESULT.json',dict(schema='native_S20000_panel_SDK_audit_result_v1',
            status='SDK_MATCHED_PENDING_ROOT_CPU_C0' if not code else 'FAILED_HOLD_PRESERVED',
            actual_job_id=process['job_id'],actual_allocation=process,actual_argv=list(sys.orig_argv),
            inputs=input_ref,source_pins=pin,verification=proof,returncode=code,failure=failure,
            actual_outer_C0_not_self_asserted=True,elapsed_seconds=time.monotonic()-started))
    return code


if __name__=='__main__':raise SystemExit(main())
