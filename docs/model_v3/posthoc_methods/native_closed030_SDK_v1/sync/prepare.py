"""Root explicit proof triples -> immutable metadata manifest; no SDK open."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from long_common import HERE,verify,proof_rows,request_gate,root_only,ref,read,write,require
from prepare_sync import capture_C0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--entry',nargs=3,type=Path,action='append',required=True,
        metavar=('VERIFICATION','AUDIT_BATCH','AUDIT_SUPERVISOR'))
    p.add_argument('--default-entity',default='mint_leaf258')
    p.add_argument('--output',type=Path,required=True);p.add_argument('--job-output',type=Path,required=True)
    p.add_argument('--pins-sha256',required=True);a=p.parse_args();root_only();source=verify(a.pins_sha256)
    require(1<=len(a.entry)<=3 and not a.output.exists() and not a.job_output.exists(),
        'Explicit one-to-three entries and fresh plan/output required')
    a.output.mkdir(mode=0o700,parents=True)
    terminals={};entries=[]
    for verification,batch_path,sup in a.entry:
        batch_ref=ref(batch_path);batch=read(batch_ref);job=str(batch['actual_job_id'])
        require(job.isdigit(),'Actual audit job ID missing')
        if job not in terminals:terminals[job]=capture_C0(job,a.output/('audit_C0_'+job))
        entries.append(dict(verification=ref(verification),audit_batch=batch_ref,
            audit_supervisor=ref(sup),actual_audit_C0=terminals[job]))
    rows=proof_rows(entries)
    manifest=write(a.output/'explicit_manifest.json',dict(schema='native_closed_long_sync_manifest_v1',
        entries=entries,runs=rows,default_entity=a.default_entity,
        routing_deferred_to_CPU_header_only=True,SDK_payload_opened_by_prepare=False,
        fixed50_or_first3_modified=False,scientific_acceptance=False))
    os.environ['MODEL_V3_LONGSYNC_MANIFEST']=manifest['path'];os.environ['MODEL_V3_LONGSYNC_MANIFEST_SHA']=manifest['sha256']
    root=HERE.parent
    gate=dict(result=ref(root/'WandB_sync50_pilot_actual_v3/RESULT.json'),
        supervisor=ref(root/'WandB_sync50_pilot_actual_v3.supervisor.json'),
        actual_terminal=capture_C0('4521412',a.output/'method_C0_4521412'),native_exit_code=1,actual_replay_verified=True)
    request=dict(schema='native_closed_long_sync_request_v1',mode='batch',selected_run_ids=[r['run_id'] for r in rows],
        source_manifest=source,eligible_manifest=manifest,pilot_gate=gate,job_output=str(a.job_output.absolute()),
        child_seconds=3000,CLI_timeout_seconds=600,API_verification_seconds=180,maximum_batch_runs=3,
        scientific_acceptance=False,original_model_statuses_unchanged=True)
    request_gate(request);raw=write(a.output/'request.json',request)
    bindings=dict(MODEL_V3_LONGSYNC_MANIFEST=manifest['path'],MODEL_V3_LONGSYNC_MANIFEST_SHA=manifest['sha256'],
        MODEL_V3_LONGSYNC_REQUEST=raw['path'],MODEL_V3_LONGSYNC_REQUEST_SHA=raw['sha256'],
        MODEL_V3_LONGSYNC_SOURCE_SHA=source['sha256'],MODEL_V3_LONGSYNC_OUTPUT=str(a.job_output.absolute()))
    result=write(a.output/'bindings.json',bindings)
    print(json.dumps(dict(request=raw,bindings=result,run_ids=request['selected_run_ids'],SDK_opened=False,online_sync=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())
