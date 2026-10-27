"""A source-bound operational overlay; all underlying audit/transport refs stayv1."""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path
V1=Path(__file__).absolute().parent.parent/'native_S10000_panel_SDK_sync_v1_source'
sys.path.insert(0,str(V1))
from panel_common import *
OVERLAY=Path(__file__).absolute().parent


def verify_overlay(expected):
    own=ref(OVERLAY/'source_pins.json')
    require(own['sha256']==expected,'Explicit overlay source SHA differs')
    pins=read(own)
    require(pins['schema']=='native_S10000_panel_sync_operational_overlay_sources_v2','Explicit sync-only overlay schema required')
    for item in pins['files']:
        actual=ref(OVERLAY/item['relative_path'])
        require((actual['bytes'],actual['sha256'])==(item['bytes'],item['sha256']),'Overlay source changed')
    deps=read(OVERLAY/'dependencies.json');original=deps['baseline_source_pins']
    require(ref(V1/'source_pins.json')==original and verify(original['sha256'])==original,
        'Actual underlyingv1/e557 audit and transport source identity must remain separate and unchanged')
    for raw in deps['metadata_refs'].values():bind(raw)
    expected_body=(V1/'sync_panel.py').read_bytes()
    require(ref(V1/'sync_panel.py')==deps['baseline_driver'],'Frozen original driver differs')
    for edit in deps['driver_edits']:
        before,after=edit['before'].encode(),edit['after'].encode()
        require(expected_body.count(before)==1,'Declared exact driver adaptation point changed')
        expected_body=expected_body.replace(before,after)
    require((OVERLAY/'sync_retry.py').read_bytes()==expected_body,'Only declared sync-driver repairs permitted')
    return own


def main():
    parser=argparse.ArgumentParser(description='Root fresh sync plan using original verified4552 certificate; metadata only')
    parser.add_argument('--overlay-pins-sha256',required=True)
    parser.add_argument('--plan-output',type=Path,required=True);parser.add_argument('--job-output',type=Path,required=True)
    args=parser.parse_args();root_only();overlay=verify_overlay(args.overlay_pins_sha256)
    deps=read(OVERLAY/'dependencies.json');refs=deps['metadata_refs']
    require(args.plan_output.absolute().parent==OVERLAY.parent and args.job_output.absolute().parent==OVERLAY.parent
        and not args.plan_output.exists() and not args.job_output.exists(),'Explicit fresh retry plan/output required')
    argv=[str(PYTHON),'-B',str(V1/'prepare.py'),'sync','--pins-sha256',deps['baseline_source_pins']['sha256'],
        '--verification',refs['verified4552']['path'],'--audit-result',refs['audit4552_result']['path'],
        '--audit-supervisor',refs['audit4552_supervisor']['path'],'--plan-output',str(args.plan_output),
        '--job-output',str(args.job_output)]
    completed=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=90)
    require(completed.returncode==0,'Original verifiedv1 metadata prepare refused fresh retry; preserve anypartial and inspectRoot')
    require(len(completed.stdout.encode())+len(completed.stderr.encode())<=1<<20,'Bounded original metadata preparation output required')
    original_bindings=ref(args.plan_output/'bindings.json');bindings=read(original_bindings)
    require(bindings['MODEL_V3_PANEL_SOURCE_SHA']==deps['baseline_source_pins']['sha256'],'Do not relabel old audit as overlay')
    bindings={**bindings,'MODEL_V3_PANEL_SYNC_OVERLAY_SHA':overlay['sha256']}
    new=write(args.plan_output/'overlay_bindings.json',bindings)
    evidence=write(args.plan_output/'PREPARATION_OVERLAY.json',dict(schema='native_S10000_panel_sync_overlay_preparation_v2',
        source_overlay=overlay,underlying_audit_transport_source_pins=deps['baseline_source_pins'],
        original_bindings=original_bindings,overlay_bindings=new,actual_argv=argv,
        original_prepare_returncode=completed.returncode,stdout=completed.stdout,stderr=completed.stderr,
        actual_SDK4552_certificate=refs['verified4552'],new_SDK_scan=False,online_action=False,
        old_source_certificate_requests_and_failure_preserved=True))
    print(json.dumps(dict(overlay_bindings=new,preparation=evidence,source_overlay=overlay,
        underlying_source_pins=deps['baseline_source_pins'],new_SDK_scan=False,online_action=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())
