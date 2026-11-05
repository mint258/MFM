"""One CPU-only complete max22 SDK comparison, using existing749/tap2/rb."""
from __future__ import annotations
import argparse
import io
import math
import time
import traceback
from max_common import *


def project_saved_row(value,ordinal):
    require(type(value) is dict and type(value['optimizer_updates']) is int
        and value['optimizer_updates']==ordinal and type(value['SDK_history_projection']) is dict,
        'Actual saved projection and committed ordinal required')
    row=value['SDK_history_projection'];counts=value['valid_label_counts'];rates=value['learning_rates']
    fields={'optimizer_updates','loss','learning_rate','gradient_norm','loader_seconds','compute_seconds',
        'update_seconds_before_SDK_log','base_records','native_atoms','physical_graphs','physical_atoms',
        'base_records_per_compute_second','native_atoms_per_compute_second','physical_graphs_per_compute_second',
        'physical_atoms_per_compute_second','peak_allocated_bytes','peak_reserved_bytes','owned_NVML_memory_bytes',
        'process_rss_sum_bytes','output_bytes','measured_after_warmup','selected_maximum_ordinal','all_maximum_tie_count'}
    require(type(counts) is dict and counts and type(rates) is list and rates,'Actual complete loss/LR population required')
    fields|={'learning_rate/group_'+str(i) for i in range(len(rates))}
    fields|={'valid_label_count/'+key for key in counts}
    require(set(row)==fields and type(row['optimizer_updates']) is int and row['optimizer_updates']==ordinal
        and type(row['measured_after_warmup']) is bool and row['measured_after_warmup']==(ordinal>2)
        and value['measured_after_warmup'] is row['measured_after_warmup']
        and all(type(v) in (int,float) and math.isfinite(v) for k,v in row.items() if k!='measured_after_warmup'),
        'Every original SDK projection field/type required; no extra or missing fields')
    for name in ('loss','gradient_norm','loader_seconds','compute_seconds'):
        require(type(value[name]) in (int,float) and row[name]==value[name],'Saved projection differs: '+name)
    require(row['compute_seconds']>0 and row['update_seconds_before_SDK_log']>=0
        and row['learning_rate']==rates[0] and all(row['learning_rate/group_'+str(i)]==v for i,v in enumerate(rates))
        and all(type(v) is int and v>=0 and row['valid_label_count/'+k]==v for k,v in counts.items()),
        'Original saved LR/count/timing projection differs')
    shape=value['shape'];receipt=value['actual_input']
    require(row['base_records']==receipt['base_records']==1 and row['native_atoms']==receipt['native_atoms']==712
        and row['physical_graphs']==shape['physical_graphs']==3
        and row['physical_atoms']==shape['physical_atoms']==2136
        and type(value['committed_selected_base_exposures']) is int and value['committed_selected_base_exposures']==ordinal,
        'All22 complete native712 three-view updates required')
    for field,amount in [('base_records_per_compute_second',1),('native_atoms_per_compute_second',712),
                         ('physical_graphs_per_compute_second',3),('physical_atoms_per_compute_second',2136)]:
        require(row[field]==amount/row['compute_seconds'],'Code-derived rate projection differs')
    resource=value['resources'];gpu=resource['gpu_observation']
    require(type(gpu['total_bytes']) is int and gpu['total_bytes']>0 and type(gpu['compute_processes']) is list,
        'Known source resource metadata required')
    for process in gpu['compute_processes']:
        require(type(process['own']) is bool and type(process['used_memory_bytes']) is int
            and process['used_memory_bytes']>=0,'Unknown NVML memory is not zero')
    require(row['owned_NVML_memory_bytes']==sum(p['used_memory_bytes'] for p in gpu['compute_processes'] if p['own'])
        and all(row[k]==resource[k] for k in ('peak_allocated_bytes','peak_reserved_bytes','process_rss_sum_bytes','output_bytes')),
        'Exact saved resource projection differs')
    return dict(step=ordinal,row=row)


def selfchecks(reader,tap):
    def reject(call):
        try:call()
        except (ValueError,KeyError):return
        raise ValueError('Metadata negative accepted')
    sample={'optimizer_updates':1,'loss':1.,'literal/a':2,'literal':3}
    line=(json.dumps(sample)+'\n').encode()
    parsed=list(reader.mirror_rows(io.BytesIO(line),'A_plain'))
    require(parsed[0]['step']==1 and parsed[0]['row']==reader.flatten(sample),
        'Actual existing A_plain/literal-key parser differs')
    reject(lambda:list(reader.mirror_rows(io.BytesIO(line+line),'A_plain')))
    reject(lambda:list(reader.mirror_rows(io.BytesIO((json.dumps({**sample,'optimizer_updates':True})+'\n').encode()),'A_plain')))
    audit=tap.Audit(reader,{})
    expected={'literal/a':2,'literal':3,'capacity_diagnostic':{'finished':True,'missing':None}}
    audit.exact_fields(reader.flatten(expected),expected,'summary')
    reject(lambda:audit.exact_fields({},expected,'summary'))
    reject(lambda:project_saved_row({'optimizer_updates':True,'SDK_history_projection':{}},1))
    return dict(scope='INLINE_PURE_METADATA_ORIGINAL_PARSER_AND_TYPED_AUDIT_NO_SDK_FIXTURE',count=4,
        checks=['actual_A_plain_literal_slash_keys','duplicate_or_bool_step_rejected',
                'full_nested_typed_summary_missing_rejected','bool_committed_update_rejected'])


def read_rows(inputs,reader,deadline):
    raw=ref(inputs['step_journal']['path'],16<<20)
    require({k:raw[k] for k in ('path','bytes')}==inputs['step_journal'],'Original steps descriptor changed')
    rows=[]
    with Path(raw['path']).open('rb') as stream:
        while True:
            require(time.monotonic()<deadline,'Finite original22-row input deadline exceeded')
            line=stream.readline(reader.MAX_LINE_BYTES+1)
            if not line:break
            require(len(rows)<22 and line.endswith(b'\n') and len(line)<=reader.MAX_LINE_BYTES,
                'Exactly22 bounded complete saved rows required')
            value=reader.strict_json(line);projected=project_saved_row(value,len(rows)+1)
            require(len(list(reader.mirror_rows(io.BytesIO((json.dumps(projected['row'])+'\n').encode()),'A_plain')))==1,
                'Actual existing parser rejected source projection')
            rows.append(projected)
    require(len(rows)==22 and ref(raw['path'],16<<20)==raw,'Original complete source rows changed')
    return rows,raw


def audit_one(inputs,metadata,reader,tap,inspector,deps,pin,input_ref,sources,output,deadline):
    rows,journal=read_rows(inputs,reader,deadline)
    require(all(row['row']['selected_maximum_ordinal']==metadata['selection']['selected_logical_ordinal']
        and row['row']['all_maximum_tie_count']==metadata['selection']['all_maximum_tie_count'] for row in rows),
        'Every saved maximum/tie projection must match the original selection')
    require(tap.encoded(metadata['expected_summary'])==tap.encoded({**rows[-1]['row'],
        'capacity_diagnostic':metadata['expected_summary']['capacity_diagnostic']}),
        'Original explicit expected summary must be the last SDK row plus its terminal update')
    sdk=ref(inputs['SDK']['path'],128<<20)
    require({k:sdk[k] for k in ('path','bytes')}==inputs['SDK'],'Exact original SDK descriptor differs')
    Scanner,Record,_,installed=inspector.load_decoder(read(deps['sources']['decoder_reference']))
    context=dict(run_id=RUN,run_name='native_S_max712_R1_'+JOB,project='mfm_model_v3_development',
        expected_config=metadata['configuration'],expected_summary=metadata['expected_summary'],mirror_rows=rows)
    audit=tap.Audit(reader,context);headers=[];scanner=None
    class Observed:
        def __init__(self):self.value=Record()
        def ParseFromString(self,raw):
            self.value.ParseFromString(raw)
            if self.value.WhichOneof('record_type')=='run':
                require(not headers,'Exactly one actual RunRecord required')
                run=self.value.run
                header=dict(run_id=run.run_id,display_name=run.display_name,project=run.project,entity=run.entity)
                header_check(header);headers.append(header)
            audit.observe(self.value)
        def __getattr__(self,name):return getattr(self.value,name)
    def mirror_factory(config):
        require(len(headers)==1,'Native RunRecord must precede history')
        return iter(dict(step=row['step'],row=reader.flatten(row['row'])) for row in rows)
    class Sink:
        def write(self,raw):return len(raw)
    try:
        scanner=Scanner();scanner.open_for_scan(sdk['path'])
        history=reader.verify_stream(scanner,Observed,Sink(),expected_run_id=RUN,expected_exit=0,expected_rows=22,
            mirror_factory=mirror_factory,deadline=deadline,max_native_records=500000,max_history_rows=100000,
            max_record_bytes=4<<20,max_export_bytes=64<<20)
        audit.finish()
    finally:
        if scanner is not None:scanner.close()
    _,_,_,after_installed=inspector.load_decoder(read(deps['sources']['decoder_reference']))
    require(installed==after_installed and len(headers)==1 and history['first_explicit_step']==1
        and history['last_explicit_step']==22 and ref(sdk['path'],128<<20)==sdk
        and ref(journal['path'],16<<20)==journal and time.monotonic()<deadline,
        'Original SDK/source/decoder beforeafter or22-step deadline differs')
    return write(output,dict(schema='native_max_R1_full_log_verification_v1',scope=SCOPE,
        status='ALL_SAVED_NATIVE_MAX_LOG_FIELDS_MATCHED',model_job_id=JOB,run_id=RUN,source_pins=pin,
        inputs=input_ref,sdk=sdk,journal=journal,native_RunRecord=headers[0],history=history,
        history_reader_source=deps['sources']['literal_reader'],tap_source=deps['sources']['tap'],
        installed_decoder_sources=installed,source_refs=sources,full_config_summary_typed_exact=True,
        raw_before_after_binding_closed=True,expected_config_sha256=tap.digest(context['expected_config']),
        expected_summary_sha256=tap.digest(context['expected_summary']),
        history_origin='All22 actual saved steps.SDK_history_projection from original log call, commitTrue/step1..22',
        summary_origin='Original SDK_expected_summary.json: last SDK row plus explicit capacity_diagnostic update',
        reserved_runtime_timing_not_recomputed=True,original_SDK_retained=True,scientific_acceptance=False,
        auto_capacity_or_universal8M_or_ABBA_or20plus500_acceptance=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--inputs-sha256',required=True)
    parser.add_argument('--pins-sha256',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();process=allocation();require(process['uid']==1278,'Actual owned CPU UID required')
    pin=verify(args.pins_sha256);input_ref=ref(args.inputs)
    require(input_ref['sha256']==args.inputs_sha256,'Exact input rawSHA required');inputs=bound_inputs(input_ref)
    require(args.output.absolute().parent==HERE.parent and not args.output.exists(),'Fresh explicit external audit output required')
    args.output.mkdir(mode=0o700);deps=read(HERE/'dependencies.json');started=time.monotonic()
    files=[HERE/r['relative_path'] for r in read(pin)['files']]+[HERE/'source_pins.json',args.inputs]
    files += [Path(v['path']) for v in deps['sources'].values()]
    files += [Path(v['path']) for v in inputs['refs'].values()]+[Path(inputs[k]['path']) for k in ('expected_summary','root_closure')]
    before={str(path):ref(path) for path in files};proofs=[];failure=None
    try:
        reader=load(deps['sources']['literal_reader'],'max_literal749');tap=load(deps['sources']['tap'],'max_actual_tap2')
        inspector=load(deps['sources']['framing'],'max_actual_full_rb_decoder')
        write(args.output/'INLINE_METADATA_QA.json',selfchecks(reader,tap))
        metadata=metadata_inputs(inputs)
        proofs.append(audit_one(inputs,metadata,reader,tap,inspector,deps,pin,input_ref,before,
            args.output/'VERIFICATION.json',time.monotonic()+180))
        metadata_inputs(inputs);verify(args.pins_sha256)
        require(before=={str(path):ref(path) for path in files},'Source/metadata drift during full max-log audit')
    except BaseException as error:
        failure=dict(type=type(error).__name__,frames=[dict(file=f.filename,line=f.lineno,function=f.name)
            for f in traceback.extract_tb(error.__traceback__)[-32:]],reason='Inspect owned metadata; no scientific rows or secrets exported')
    finally:
        write(args.output/'RESULT.json',dict(schema='native_max_R1_log_audit_result_v1',scope=SCOPE,
            status='ONE_MAX_RUN_FULL_LOG_MATCHED_PENDING_ACTUAL_CPU_C0' if failure is None else 'FAILED_HOLD_PRESERVED',
            actual_job_id=process['job_id'],actual_allocation=process,actual_argv=list(sys.orig_argv),
            source_pins=pin,inputs=input_ref,verifications=proofs,returncode=int(failure is not None),failure=failure,
            source_refs_before=before,source_refs_after={str(path):ref(path) for path in files},
            elapsed_seconds=time.monotonic()-started,original_SDK_retained=True,actual_outer_C0_not_self_asserted=True,
            scientific_acceptance=False,auto_capacity_or_universal8M_or_ABBA_or20plus500_acceptance=False))
    return int(failure is not None)


if __name__=='__main__':raise SystemExit(main())
