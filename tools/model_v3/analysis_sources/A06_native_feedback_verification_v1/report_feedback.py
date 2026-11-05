"""Emit a bounded diagnostic certificate/report only after native SDK + actual C0 verification."""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
import sys
import time

import feedback_schema as schema
from verify_feedback_sdk import verify


def csv_bytes(context):
    config, account, points = context['expected_config'],context['accounting'],context['summary']['points']
    row = {'run_id':schema.RUN_ID,'stage':'1','config_sha256':context['configuration_ref']['sha256'],
        'code_sha':schema.CODE_SHA,'data_version':context['data_version'],'seed':'0',
        'gpu_model':config['environment']['gpu_name'],'elapsed_seconds':str(account['elapsed_seconds']),
        'status':'NOT_ACCEPTED','preregistration_sha':schema.PREREG_SHA,
        'allocated_cpu_seconds':str(account['elapsed_seconds']*account['allocated_cpus']),
        'metric__diagnostic_only':'1','metric__native_history_rows':'17','metric__native_updates':'15',
        'metric__consumed_base_records':'5120','metric__all_replay_points_exact457':'1',
        'metric__first_original_threshold_failure':'14','metric__original_A06_gate_pass':'0',
        'metric__relative_loss_gap_update14':repr(points[13]['loss_relative_difference']),
        'metric__relative_loss_gap_update15':repr(points[14]['loss_relative_difference'])}
    stream = io.StringIO(newline=''); writer = csv.DictWriter(stream,fieldnames=list(row),lineterminator='\n')
    writer.writeheader(); writer.writerow(row); return stream.getvalue().encode()


def report_text(context, certificate):
    native, account = certificate['native'],context['accounting']
    out = ['# A06 native feedback diagnostic: independently verified evidence', '',
        'The original A06 acceptance gate remains **FAILED_UNCHANGED**. This is a single-seed, 15-update diagnostic, '
        'not a rerun of fixed20/full500 acceptance, architecture selection, convergence or a causal attribution result.', '',
        f"Actual parent {schema.JOB}: {account['state']}/{account['exit_code']}, {account['elapsed_seconds']} s. "
        f"Native offline run `{schema.RUN_ID}`: **{native['history_rows']} history rows**, "
        f"**{native['native_packets']} total native records**, clean EOF and exit0. "
        'All public configuration, metrics, explicit steps and final summary matched exactly. No online sync was performed.', '',
        'Replay of the saved457 reference/free scalar and input-receipt fields is exact at every one of the 15 points; '
        '5120 base records were consumed. The optimizer-only shadow has no model forward and borrows the same clipped '
        'reference gradients, with matching before/after/reference digests. Reading these saved receipts does not '
        'independently rerun a model or prove a causal decomposition.', '',
        'Relative loss gap uses abs(free-reference)/max(abs(reference),1e-12). The original 0.001 point threshold '
        'first fails at update14; no new threshold is applied. Loss and gradient norms have the original diagnostic '
        'normalization; no physical unit or confidence interval is invented.', '',
        '| Update | Base consumed | Reference loss | Free fused loss | Relative gap | Original point pass | Raw gradient max parameter relative L2 |',
        '|---:|---:|---:|---:|---:|:---:|---:|']
    for entry in context['expected_rows'][1:16]:
        row = entry['row']
        out.append('| '+ ' | '.join(str(value) for value in (entry['step'],row['consumed_base_records'],row['reference/loss'],
            row['free_fused/loss'],row['trajectory/relative_difference'],row['trajectory/original_point_pass'],
            row['gradient/free_vs_reference_max_parameter_relative_l2']))+' |')
    out += ['', 'All fixed logger comparison aggregates are below. These are aggregate tensor-difference diagnostics. '
        'A maximum relative error for a near-zero individual parameter is not an acceptance threshold. '
        'Global difference L2 has the native units of its parameter/moment/step tensor; no additive causal percentage is implied.', '']
    for role in schema.ROLES:
        out += [f'## {role}', '', '| Update | Parameters max relative / global L2 | exp_avg max relative / global L2 | '
            'exp_avg_sq max relative / global L2 | Step max relative / global L2 |', '|---:|---:|---:|---:|---:|']
        for entry in context['expected_rows'][1:16]:
            row = entry['row']; values = [str(entry['step'])]
            for component in schema.COMPONENTS:
                prefix = role+'/'+component+'/'
                values.append(str(row[prefix+'max_parameter_relative_l2'])+' / '+str(row[prefix+'global_difference_l2_diagnostic_only']))
            out.append('| '+' | '.join(values)+' |')
        out.append('')
    out += ['## Reference/free preclip gradient norms', '', '| Update | Reference | Free fused |', '|---:|---:|---:|']
    for entry in context['expected_rows'][1:16]:
        row=entry['row']; out.append(f"| {entry['step']} | {row['reference/preclip_gradient_norm']} | {row['free_fused/preclip_gradient_norm']} |")
    out += ['', 'The certificate includes raw-byte source/evidence references and installed decoder provenance. '
        'The complete fixed producer inventory was rehashed; metadata and the SDK were rechecked after scanning. '
        'Reports export only scalar aggregates/counts/hashes: no parameter arrays, selected parameter scalars, '
        'native molecule/member identities, geometries, labels or predictions. '
        'The original SDK and all original diagnostic artifacts remain unchanged.', '']
    return '\n'.join(out).encode()


def publish(output, context, certificate, inputs_ref, source_pins_ref):
    schema.require(certificate['status'] == 'VERIFIED_DIAGNOSTIC_ONLY'
        and certificate['all_public_metrics_config_summary_steps_exact'] is True
        and certificate['native']['native_closed'] is True, 'Only independently verified closed diagnostic may be reported')
    output = Path(output)
    schema.require(output.is_absolute() and '..' not in output.parts and not output.exists(), 'Fresh absolute output directory required')
    original_root=Path(context['sources']['summary']['path']).parent
    schema.require(not output.is_relative_to(original_root) and not original_root.is_relative_to(output),
        'New report must be separate from all original diagnostic artifacts')
    certificate = {**certificate,'report_inputs':inputs_ref,'report_source_pins':source_pins_ref}
    archive = {'schema':'model_v3_archive_pending_entry_v1','status':'DRAFT_FOR_ROOT_REVIEW',
        'source_job_id':schema.JOB,'run_id':schema.RUN_ID,'kind':'A06_native15_feedback_diagnostic',
        'native_sdk_verified':True,'source_SDK':context['SDK_file'],'history_rows':17,
        'native_records':certificate['native']['native_packets'],'outer_state':'COMPLETED','outer_exit_code':'0:0',
        'scientific_acceptance':False,'original_gate_status':'FAILED_UNCHANGED','online_sync_performed':False,
        'report_output':str(output),'note':'Draft entry only; no existing archive/index was modified.'}
    products = {'verification.json':schema.encoded(certificate),'summary.csv':csv_bytes(context),
        'REPORT.md':report_text(context,certificate),'archive_entry.draft.json':schema.encoded(archive)}
    schema.require(sum(map(len,products.values())) <= schema.LIMITS['max_export_bytes']-16384,
        'Whole report export budget exhausted')
    output.mkdir(parents=False)
    for name, raw in products.items():
        with (output/name).open('xb') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    result={'schema':'model_v3_A06_feedback_report_manifest_v1','status':'VERIFIED_DIAGNOSTIC_ONLY',
        'scientific_acceptance':False,'files':[schema.file_ref(output/name) for name in products],
        'original_artifacts_modified':False,'archive_automatically_modified':False}
    with (output/'report_manifest.json').open('xb') as stream: stream.write(schema.encoded(result)); stream.flush(); os.fsync(stream.fileno())
    return result


def verify_source_pins(path, digest):
    ref=schema.file_ref(path); schema.require(ref['sha256'] == digest,'New verifier source manifest SHA differs')
    pins=schema.read(ref)
    schema.require(pins['schema'] == 'model_v3_A06_feedback_verifier_sources_v1','Verifier source manifest schema differs')
    expected={'feedback_schema.py','verify_feedback_sdk.py','report_feedback.py','prepare_feedback_inputs.py',
        'test_feedback_verification.py','README.md'}
    schema.require({Path(row['path']).name for row in pins['files']} == expected and len(pins['files']) == len(expected),
        'Complete independent verifier source inventory required')
    for source in pins['files']:
        schema.require(Path(source['path']).parent == Path(__file__).parent,'Verifier inventory path differs'); schema.bind(source)
    return ref,pins['files']


def main(argv=None):
    started=time.monotonic(); deadline=started+schema.LIMITS['max_wall_seconds']
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True); parser.add_argument('--inputs-sha256',required=True)
    parser.add_argument('--source-pins',type=Path,required=True); parser.add_argument('--source-pins-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True); args=parser.parse_args(argv)
    sys.dont_write_bytecode=True
    pins_ref,source_refs=verify_source_pins(args.source_pins,args.source_pins_sha256)
    inputs_ref=schema.file_ref(args.inputs); schema.require(inputs_ref['sha256']==args.inputs_sha256,'Input manifest SHA differs')
    context=schema.prepare(schema.read(inputs_ref),inputs_ref); verdict=verify(context,deadline=deadline)
    for source in source_refs: schema.bind(source)
    schema.bind(pins_ref); schema.bind(inputs_ref)
    schema.require(time.monotonic() <= deadline,'Inclusive report wall budget exhausted')
    result=publish(args.output,context,verdict,inputs_ref,pins_ref)
    print(json.dumps({'status':result['status'],'report':str(args.output),'scientific_acceptance':False})); return 0


if __name__ == '__main__': raise SystemExit(main())
