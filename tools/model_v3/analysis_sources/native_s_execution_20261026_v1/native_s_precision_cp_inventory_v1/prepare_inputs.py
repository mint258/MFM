"""Prepare two tiny future-state manifests from actual closed profile metadata.

This metadata-only step neither opens nor hashes a checkpoint payload.
"""
from pathlib import Path
import argparse
import inventory as audit

BASE=Path('/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026')


def prepare(output):
    output=Path(output).absolute(); audit.require(not output.exists(),'Fresh manifest directory required')
    audit.require(not any(part.startswith('MFM_model_v3') for part in output.parts),'Manifest output is outside Git')
    values=[]
    for precision,job in (('fp32','4521331'),('bf16','4521332')):
        phase=BASE/('native_S_profile_'+precision+'_v8')
        child=phase/('job_'+job)/'child'; management=child.parent/'management'
        profile_ref=audit.bound(child/'profile_result.json'); profile=audit.read(profile_ref)
        checkpoint=profile['checkpoint_ref']
        value=dict(schema='native_S_evidence_inputs_v2',role='future_state',
            artifacts=dict(profile_result=profile_ref,checkpoint=checkpoint),
            context=dict(model=audit.MODEL,plan=audit.PLAN,checkpoint_cap_bytes=384<<20,
                max_complete_checkpoints=audit.MAX_CHECKPOINTS,
                Root_profile_closure=audit.bound(management/'ROOT_PROFILE_CLOSURE.json'),
                actual_terminal=audit.bound(management/'actual_terminal.json'),
                profile_configuration=audit.bound(child/'configuration.json'),
                checkpoint_complete=audit.bound(Path(checkpoint['path']).parent/'COMPLETE.json'),
                growth_source_refs={name:audit.bound(audit.RUNTIME/name) for name in audit.GROWTH_SOURCES}))
        audit.profile_context(value)
        values.append((precision,value))
    output.mkdir(mode=0o700)
    refs={precision:audit.write(output/(precision+'_future_inputs.json'),value) for precision,value in values}
    audit.write(output/'PREPARED.json',dict(schema='native_S_CP_future_inputs_prepared_v1',
        status='INPUTS_ONLY_NOT_AN_AUDIT',inputs=refs,checkpoint_payload_opened=False,
        source=audit.bound(Path(__file__).absolute()),B_acceptance=False))
    return refs


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); prepare(args.output)
