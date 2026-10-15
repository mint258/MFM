#!/usr/bin/env python3
"""Read only the small completed audit metadata; no QM or matrix work."""
import json
from pathlib import Path

root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
report=json.loads((root/'reports/mulliken_audit_v2_job_4512806/mulliken_audit.json').read_text())
cases=report['cases']
summary={'job_id':report['job_id'],'tasks':report['tasks'],'completed':report['completed'],'errors':report['errors'],
         'actual_worker_count':len(report['actual_worker_PIDs']),
         'corrected_charge_errors_e':{r['molecule']+'/'+r['task']:r['from_AUX_full_density']['v23_MULLIK_beta_p_for_d_overlap']['maximum_charge_error_vs_printed_e'] for r in cases},
         'uncorrected_max_error_e':max(r['from_AUX_full_density']['AUX_overlap']['maximum_charge_error_vs_printed_e'] for r in cases),
         'corrected_max_error_e':max(r['from_AUX_full_density']['v23_MULLIK_beta_p_for_d_overlap']['maximum_charge_error_vs_printed_e'] for r in cases),
         'all_existing_files_unchanged':all(r['source_unchanged'] for r in cases),
         'maximum_negative_eigenvalues':max(r['from_AUX_full_density']['v23_MULLIK_beta_p_for_d_overlap']['spectrum']['negative_eigenvalues'] for r in cases)}
print(json.dumps(summary,indent=2))
