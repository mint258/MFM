"""Append operational-only source adoption; keep existing validated science unchanged."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from long_common import *


def main():
    root_identity();parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',type=Path,required=True);parser.add_argument('--pins-sha256',required=True)
    args=parser.parse_args();manifest,_=verify(args.pins_sha256)
    from long_operations import lock,closed_attempts,next_member
    with lock(args.phase):
        original=binding(args.phase/'control/VALIDATED.json');validated=read_ref(original)
        require(validated['package_manifest']==binding(N/'native_s_precision_long_run_v3/source_pins.json'),
            'Only the previously verified v3 operational package may be adopted')
        for name in ('configuration','profile','initial_roots','runtime_contract'):read_ref(validated[name])
        principal=binding(args.phase/'control/principal.json');read_ref(principal)
        attempts=closed_attempts(args.phase)
        require(len(attempts)==1 and attempts[0][0]['actual_sbatch_job_id']=='4521411'
            and attempts[0][1]['status']=='FAILED_OR_STORAGE_HOLD','Only reconciled failed1411 lineage is allowed')
        next_step=next_member(args.phase,allow_failed=True)
        require(next_step['slot']==2 and next_step['start_update']==0 and next_step['resume_checkpoint'] is None,
            'Failed partial updates cannot become a resume prefix')
        result=write(args.phase/'control/OPERATIONAL_ADOPTION_v4.json',dict(
            schema='native_S_long_operational_adoption_v4',authority='ROOT_ACTUAL',original_validation=original,
            original_package=validated['package_manifest'],package_manifest=manifest,
            configuration=validated['configuration'],profile=validated['profile'],initial_roots=validated['initial_roots'],
            runtime_contract=validated['runtime_contract'],principal=principal,registry=validated['registry'],
            original_failed_closure=attempts[0][2],science_code_sha=CODE,science_prereg_sha=PUBLIC,
            numerical_science_config_data_seed_precision_unchanged=True,counters_reset=False,
            operational_changes=['bounded30s_original_quota_revalidation_with_exact_rejection_snapshots',
                'original_compute_host_device_inode_census','four_additional_inline_metadata_QA'],
            no_new_reservation_or_model_started=True,scientific_acceptance=False))
        print(json.dumps(dict(status='OPERATIONAL_SOURCE_ADOPTED_NO_NEW_SCIENCE',adoption=result,next=next_step)))
    return 0


if __name__=='__main__':raise SystemExit(main())
