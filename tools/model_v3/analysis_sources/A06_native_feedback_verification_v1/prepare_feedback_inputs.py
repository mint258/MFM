"""Build a fresh raw-byte manifest from existing diagnostic metadata and Root C0 receipt."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

import feedback_schema as schema
from report_feedback import verify_source_pins


def build_manifest(root, root_closure_ref):
    root=Path(root)
    config_ref=schema.file_ref(root/'configuration.json'); config=schema.read(config_ref)
    roles={entry['role']:entry for entry in config['original_evidence_and_sources']}
    refs={key:schema.file_ref(root/(key+'.'+('jsonl' if key in ('history','reference_history',
        'candidate_history','consumption') else 'json'))) for key in schema.SOURCE_KEYS if key not in
        ('sdk','producer','source_pins','original_reference_history','original_candidate_history','root_closure')}
    refs.update(producer=schema.file_ref(schema.PRODUCER),source_pins=config['source_pins'],root_closure=root_closure_ref)
    for role in ('reference','candidate'):
        refs['original_'+role+'_history']={key:roles['457_'+role+'_history'][key] for key in ('path','bytes','sha256')}
    sdks=list((root/'wandb').glob('offline-run-*/run-'+schema.RUN_ID+'.wandb'))
    schema.require(len(sdks)==1,'Exactly one physical declared offline SDK required')
    refs['sdk']=schema.file_ref(sdks[0],schema.LIMITS['max_source_bytes'])
    manifest={'schema':'model_v3_A06_feedback_verification_inputs_v1','expected_job_id':schema.JOB,
        'expected_run_id':schema.RUN_ID,'files':refs,
        'update_files':[schema.file_ref(root/f'update_{update:02d}.json') for update in range(1,16)]}
    schema.prepare(manifest)  # Metadata/counters/source bytes only; no DataStore or model initialization.
    return manifest


def main(argv=None):
    started=time.monotonic(); parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnostic-root',type=Path,required=True)
    parser.add_argument('--root-closure',type=Path,required=True); parser.add_argument('--root-closure-sha256',required=True)
    parser.add_argument('--source-pins',type=Path,required=True); parser.add_argument('--source-pins-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True); args=parser.parse_args(argv)
    sys.dont_write_bytecode=True
    pins_ref,source_refs=verify_source_pins(args.source_pins,args.source_pins_sha256)
    ref=schema.file_ref(args.root_closure)
    schema.require(ref['sha256']==args.root_closure_sha256,'Root actual closure raw SHA differs')
    manifest=build_manifest(args.diagnostic_root,ref)
    for source in source_refs: schema.bind(source)
    schema.bind(pins_ref)
    output=args.output
    schema.require(output.is_absolute() and '..' not in output.parts and not output.exists()
        and not output.is_relative_to(args.diagnostic_root) and not args.diagnostic_root.is_relative_to(output.parent),
        'Fresh external input manifest required')
    raw=schema.encoded(manifest); schema.require(len(raw)<=schema.FILE_CAP,'Input manifest exceeds metadata budget')
    schema.require(time.monotonic()-started<=schema.LIMITS['max_wall_seconds'],'Preparation wall budget exhausted')
    with output.open('xb') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    result=schema.file_ref(output)
    print(json.dumps({'status':'PREPARED_METADATA_ONLY_NATIVE_SDK_SCAN_PENDING','manifest':result,
        'expected_history_rows':17,'native_records_observed':None,'scientific_acceptance':False})); return 0


if __name__=='__main__': raise SystemExit(main())
