"""Original full48 H0 replay, then complete fixed-input local AV diagnostics."""
from __future__ import annotations
import argparse
import csv
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback

B = Path('/share/home/zixiao/descriptor_analysis')
HERE = Path(__file__).absolute().parent
OLD_HEAD = B/'runs/model_v3_20261026/numeric_fixed_h0_shadow_v3_source'
sys.path.insert(0,str(OLD_HEAD))
import shadow_common as common
if Path(common.__file__).absolute() != OLD_HEAD/'shadow_common.py':
    raise ValueError('Original published helper namespace differs')
require, ref, bound, save = common.require, common.ref, common.bound, common.save_plain
verify_publication, metadata_selfcheck = common.verify_publication, common.metadata_selfcheck

def load_file(path,name):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def sources(request,pins_sha):
    pins = bound({**ref(HERE/'source_pins_v1.json'),'sha256':pins_sha})
    require(pins['schema'] == 'model_v3_attention_av_diagnostic_launch_source_pins_v1'
            and pins['role'] == 'LOCAL_ATTENTION_AV_CENTERING_DIAGNOSTIC_ONLY', 'Dedicated source pins required')
    rows = {x['path']:x for x in request['source_refs']+pins['files']+pins['protected_dependencies']}
    rows[str(HERE/'source_pins_v1.json')] = ref(HERE/'source_pins_v1.json')
    for value in rows.values():
        require(ref(value['path']) == value, 'Source drift: '+value['path'])
    verify_publication(request)
    return pins,rows

def compare_saved(actual,expected,name):
    from av_capture import header
    a,b = header(actual),header(expected)
    # Historical captures do not preserve GPU pointer/layout, only typed values.
    keys = ('shape','dtype','bytes','sha256')
    return {'name':name,'actual':{k:a[k] for k in keys},'original1492':{k:b[k] for k in keys},
            'bitwise_equal':all(a[k] == b[k] for k in keys)}

def snapshot_bytes(output):
    return sum(path.stat().st_size for path in output.rglob('*') if path.is_file())

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',type=Path,required=True)
    parser.add_argument('--request-sha256',required=True)
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--admit-only',action='store_true')
    args = parser.parse_args()
    request = bound({**ref(args.request),'sha256':args.request_sha256})
    require(os.environ.get('MODEL_V3_NUMERIC_GPU_REQUEST_SHA') == args.request_sha256
        and os.environ.get('MODEL_V3_EXPECTED_NODE') == request['node'] == socket.gethostname().split('.')[0]
        and os.environ.get('CUDA_VISIBLE_DEVICES') == request['gpu_uuid']
        and os.environ.get('SLURM_JOB_ID','').isdigit(), 'Actual assigned GPU diagnostic required')
    pins,before = sources(request,os.environ['MODEL_V3_NUMERIC_GPU_LAUNCH_PINS_SHA'])
    if args.admit_only:
        leaf = request['UUID_admission_source']; require(ref(leaf['path']) == leaf,'Frozen CUuuid source differs')
        admission = load_file(leaf['path'],'AV_original_actual_CUuuid_admission')
        save(args.output_root/'CUDA_UUID_ADMISSION.json',admission.admit_runtime({
            'device':'cuda:0','gpu_uuid':request['gpu_uuid'],'expected_node':request['node']}))
        return 0
    protocol = bound(pins['analysis_protocol'])
    require(protocol['schema'] == 'model_v3_attention_av_centering_protocol_v1'
        and protocol['expected_encoder_forwards'] == 192 and protocol['expected_AV_observations'] == 1152
        and protocol['centered_controls_per_AV'] == 1, 'Fixed complete48 local protocol required')
    complete = bound(protocol['capture_complete']); capture = bound(complete['manifest'])
    require(capture['status'] == 'CAPTURE_COMPLETE' and capture['source_before_after_equal'] is True
        and capture['failure'] is None and capture['job_id'] == '4521492'
        and capture['completed_case_encoder_forwards'] == capture['encoder_forwards'] == 192
        and capture['source_pins'] == protocol['capture_producer_source_pins']
        and [x['case_id'] for x in capture['cases']] == request['expected_case_ids'], 'Actual complete1492 input capture required')
    supervisor = bound(protocol['capture_supervisor'])
    require(supervisor['job_id'] == '4521492' and supervisor['status'] == 'COMPLETED' and supervisor['exit_code'] == 0
        and supervisor['first_failure'] is None and supervisor['remaining_recorded_processes_before_retirement'] == []
        and supervisor['private_storage_cleanup_errors'] == [] and supervisor['gpu_uuid'] == request['gpu_uuid']
        and supervisor['supervisor_source_sha256'] == request['supervisor_source']['sha256']
        and supervisor['foreign_gpu_processes_signalled'] is False, 'Actual capture successful supervisor required')
    require(capture['request']['sha256'] == args.request_sha256 and bound(capture['request']) == request,
            'Original capture request must be unchanged')
    accounting = load_file(OLD_HEAD/'cpu_metadata_v3.py','av_original_capture_accounting')
    accounting_validation = accounting.validate_capture_accounting(bound(protocol['capture_accounting']),'4521492')
    input_root = Path(protocol['capture_complete']['path']).parent
    input_files = [path for path in input_root.rglob('*') if path.is_file()]
    require(all(not path.is_symlink() for path in input_files) and sum(x.stat().st_size for x in input_files) <= 128<<20,
            'Original input scope128MiB required')
    require(not args.output_root.exists(),'Fresh independent output required')
    args.output_root.mkdir(); save(args.output_root/'sources_before.json',before)
    child_cap = int(os.environ['MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES'])
    require(0 < child_cap <= (2<<30)-(96<<20),'Preserve supervisor-derived child ceiling')
    counts = {'scientific_encoder_forwards':0,'captured_AV':0,'original_AV_replays':0,'centered_controls':0,
              'FP64_Rraw_calls':0,'FP64_Rnorm_calls':0,'FP64_Cexact_calls':0}
    cache,cache_bytes,result,failure = [],0,None,None
    try:
        subprocess.run([sys.executable,'-B',str(Path(__file__).absolute()),'--request',str(args.request),
            '--request-sha256',args.request_sha256,'--output-root',str(args.output_root),'--admit-only'],check=True)
        import torch
        from av_capture import AVCapture
        from av_analysis import analyze,tiny_controls
        old_head = load_file(OLD_HEAD/'shadow_terminals_v1.py','av_original_fixed_H0_decoder')
        adapter_leaf = next(x for x in request['source_refs'] if x['path'].endswith('/candidate_composed_adapter.py'))
        adapter = load_file(adapter_leaf['path'],'av_original_candidate_composed_adapter')
        equation = adapter.load_equation()
        require([x.identity for x in equation.CASE_SPECS] == request['expected_case_ids'],'Original complete48 order required')
        with equation.numerical_policy(threads=1),torch.inference_mode(),torch.autocast(device_type='cuda',enabled=False):
            tiny = tiny_controls(); save(args.output_root/'INLINE_TINY_CONTROLS.json',tiny)
            for ordinal,(spec,leaf) in enumerate(zip(equation.CASE_SPECS,capture['cases'])):
                case,old_bank,original_calls = old_head.decode_case(leaf)
                holder,handles = {},[]
                original_builder = equation.build_composition
                def build(actual_spec):
                    model,registry = original_builder(actual_spec)
                    require(equation.weight_summary(model)['all_named_parameter_sha256'] ==
                        case['original_measurement']['weight_summary']['all_named_parameter_sha256'],'Original parameter identity differs')
                    arrays,names,extras = common.state_arrays(model.pd_heads)
                    require(common.tensor_state_identity(arrays,names,extras) == case['bank_state_identity'],'Original bank state differs')
                    recorder = AVCapture([layer.attn for layer in model.encoder.backbone.layers])
                    original_forward = model.forward_pretrain
                    holder.update(model=model,recorder=recorder,roles=0,original_forward=original_forward,
                        had_override='forward_pretrain' in model.__dict__)
                    def count(module,inputs,output): counts['scientific_encoder_forwards'] += 1
                    def bank_before(module,inputs,kwargs): holder['bank_input'] = inputs
                    handles.append(model.encoder.backbone.register_forward_hook(count))
                    handles.append(model.pd_heads.register_forward_pre_hook(bank_before,with_kwargs=True))
                    def forward(*positional,**keywords):
                        nonlocal cache_bytes
                        with recorder.scope(): output = original_forward(*positional,**keywords)
                        role = holder['roles']; require(role < 4,'Unexpected fifth scientific forward')
                        h,batch,pos = holder.pop('bank_input'); eh,ep,eb,_ = original_calls[role]
                        comparisons = [compare_saved(h,eh,'actual_bank_H0'),compare_saved(pos,ep,'actual_bank_pos'),
                                       compare_saved(batch,eb,'actual_bank_batch')]
                        frames = recorder.take_cpu()
                        require(len(frames) == 6 and all(x['meta']['heads'] == 8 and x['meta']['head_dim'] == 64 for x in frames),
                                'Original six-layer eight-head64 attention required')
                        save(args.output_root/('replay_case%02d_role%d.json' % (ordinal,role)),{
                            'case_id':spec.identity,'role':role,'comparisons':comparisons,'captured_AV':len(frames)})
                        require(all(x['bitwise_equal'] for x in comparisons),'REPLAY_MISMATCH against actual1492')
                        for frame in frames:
                            cache_bytes += frame['mask'].numel()*frame['mask'].element_size()
                            cache_bytes += sum(x.numel()*x.element_size() for x in frame['values'].values())
                            require(cache_bytes <= protocol['CPU_cache_payload_cap_bytes'],'Finite CPU cache cap exceeded')
                            frame['case_id'],frame['case_ordinal'],frame['role'] = spec.identity,ordinal,role
                            cache.append(frame); counts['captured_AV'] += 1
                        holder['roles'] += 1
                        return output
                    model.forward_pretrain = forward
                    return model,registry
                try:
                    with adapter.composition_mode(equation,'compensated_fp32_v1'):
                        equation.build_composition = build
                        measured = equation.measure_case(spec,device='cuda:0',threads=1)
                    save(args.output_root/('replay_case%02d.json' % ordinal),measured)
                    require(holder['roles'] == 4 and measured['encoder_configuration'] == case['original_measurement']['encoder_configuration']
                        and measured['registry_sha256'] == case['original_measurement']['registry_sha256']
                        and measured['case'] == case['case'],'Original case/config/registry differs')
                    nodes = 88 if spec.views == 'two' else 132
                    require(measured['encoder_forward_shapes'] == [[nodes,512]]*4
                        and measured['original_view_identity_sha256'] == case['original_measurement']['original_view_identity_sha256']
                        and measured['original_physical_geometry_sha256'] == case['original_measurement']['original_physical_geometry_sha256']
                        and measured['fixture_geometry_sha256'] == case['original_measurement']['fixture_geometry_sha256'],
                        'Original full physical views/geometry differ')
                    require(equation.weight_summary(holder['model'])['all_named_parameter_sha256'] ==
                        case['original_measurement']['weight_summary']['all_named_parameter_sha256'],'Original model changed')
                finally:
                    equation.build_composition = original_builder
                    for handle in handles: handle.remove()
                    if 'recorder' in holder: holder['recorder'].close()
                    if 'model' in holder:
                        if holder['had_override']: holder['model'].forward_pretrain = holder['original_forward']
                        else: del holder['model'].forward_pretrain
                holder.clear(); del old_bank,original_calls
            require(counts['scientific_encoder_forwards'] == 192 and counts['captured_AV'] == len(cache) == 1152,
                    'Complete192/1152 gate required before scientific AV controls')
            save(args.output_root/'FP32_REPLAY_GATE.json',{'status':'ALL48_192_ROLES_BITWISE_MATCH_ACTUAL1492',
                'counts':dict(counts),'CPU_cache_payload_bytes':cache_bytes,'AV_controls_started_before_gate':False,
                'source_capture':protocol['capture_complete'],'tiny_controls_separate':True})
            cases,rows = [],[]
            with (args.output_root/'AV_metrics.csv').open('x',newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['case_id','role','layer','metric','components','maxabs','rms','signed_mean','components_gt_1e_5','argmax'])
                for index in range(len(cache)):
                    frame = cache[index]; row = analyze(frame)
                    row.update(case_id=frame['case_id'],role=frame['role'])
                    for name,value in row['metrics'].items():
                        writer.writerow([frame['case_id'],frame['role'],row['layer'],name,value['components'],
                            value['maxabs'],value['rms'],value['signed_mean'],value['components_gt_1e_5'],json.dumps(value['argmax'])])
                    counts['original_AV_replays'] += 1; counts['centered_controls'] += 1
                    for key in ('FP64_Rraw_calls','FP64_Rnorm_calls','FP64_Cexact_calls'): counts[key] += 1
                    rows.append(row); cache[index] = None
                    if len(rows) == 24:
                        ordinal = frame['case_ordinal']; path = args.output_root/('AV_case%02d.json' % ordinal)
                        save(path,{'schema':'model_v3_AV_local_case_v1','case_id':frame['case_id'],'observations':rows,
                            'operation_count':24,'physics_acceptance':False})
                        cases.append({'case_id':frame['case_id'],'result':ref(path)}); rows = []
                    require(snapshot_bytes(args.output_root) < min(child_cap-(16<<20),128<<20), 'Bounded diagnostic output reserve exceeded')
                stream.flush(); os.fsync(stream.fileno())
            require(len(cases) == 48 and not rows and all(counts[x] == 1152 for x in counts if x != 'scientific_encoder_forwards'),
                    'Complete unselected1152 control population required')
            result = {'schema':'model_v3_attention_av_centering_diagnostic_result_v1','status':'LOCAL_DIAGNOSTIC_COMPLETE',
                'scope':'ACTUAL1492_FP32_COUPLED_ATTENTION_FIXED_INPUTS_ONLY','case_count':48,'cases':cases,
                'counts':counts,'tiny_controls':tiny,'CPU_cache_peak_payload_bytes':cache_bytes,
                'cache_layout_restored_but_pointer_relocated':True,'capture_complete':protocol['capture_complete'],
                'capture_accounting':accounting_validation,'protocol':pins['analysis_protocol'],
                'production_centered_model_executed':False,'F64_encoder_recomputed':False,
                'NativeRuntimeDense_bf16_training_dropout_covered':False,'physics_acceptance':False}
            save(args.output_root/'ANALYSIS_RESULT.json',result)
    except BaseException as error:
        failure = {'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()}
    finally:
        cache.clear()
        after = {path:ref(path) for path in before}; save(args.output_root/'sources_after.json',after)
        stable = after == before
        summary = {'schema':'model_v3_attention_av_diagnostic_closure_v1',
            'status':'LOCAL_DIAGNOSTIC_COMPLETE' if result is not None and failure is None and stable else 'FAILED',
            'counts':counts,'failure':failure,'sources_before_after_equal':stable,'physics_acceptance':False,
            'result':ref(args.output_root/'ANALYSIS_RESULT.json') if result is not None else None}
        save(args.output_root/('COMPLETE.json' if summary['status'] == 'LOCAL_DIAGNOSTIC_COMPLETE' else 'FAILED.json'),summary)
    return 0 if result is not None and failure is None and stable else 1

if __name__ == '__main__':
    raise SystemExit(main())
