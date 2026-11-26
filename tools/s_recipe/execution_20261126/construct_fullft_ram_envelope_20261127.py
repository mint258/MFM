"""Only closed resource metadata, and the two new envelope checks; no refits."""
import unittest
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
from fullft_ram_envelope_20261127 import estimate,SCHEMA,PROOF,GiB,read
suite=unittest.defaultTestLoader.loadTestsFromName('test_fullft_ram_envelope_20261127')
count=suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise SystemExit(1)
progress=read(R/'results/s_recipe/execution_progress_20261127.json')
fits=[row for row in progress['completed_full_fits'] if row['point'] in ('S_B0_3M','S_G1_3M')]
identities={(row['point'],row['task']) for row in fits}
tasks=('qm9.U0_atom','qm9.homo','exp.LogD','exp.LogS')
if (len(fits)!=24 or identities!={(point,task) for point in ('S_B0_3M','S_G1_3M') for task in tasks}
        or any(sum((row['point'],row['task'])==identity for row in fits)!=3 for identity in identities)):
    raise ValueError('Both complete three-seed/all-four-task points required')
values=[]
ledger=read(C/'execution.json')['statistics']
for fit in fits:
    record=read(fit['closure_source'])
    if (record.get('status')!='COMPLETE' or record.get('exit_code')!=0
            or not record.get('owned_descendants_exited') or not record.get('observer_joined')):
        raise ValueError('Only actual complete process observations may estimate future demand')
    values.append(dict(source=fit['closure_source'],run=fit['run'],task=fit['task'],
        main=record['peak_RSS_bytes'],child=record['child_peak_RSS_bytes']))
    origin=ledger[fit['handle']].get('native_lifecycle_record')
    if origin and origin!=fit['closure_source']:
        native=read(origin)
        if (native.get('exit_code') not in (0,75) or not native.get('owned_descendants_exited')
                or not native.get('observer_joined')):
            raise ValueError('Original native resource observations must have genuinely exited')
        values.append(dict(source=origin,run=fit['run'],task=fit['task'],
            main=native['peak_RSS_bytes'],child=native['child_peak_RSS_bytes']))
bound=estimate(max(row['main'] for row in values),max(row['child'] for row in values))
if bound['estimated_concurrent_host_peak_bytes']>16*GiB:
    raise ValueError('Observed conservative resource envelope does not fit16GiB')
value=dict(schema=SCHEMA,status='RESOURCE_ESTIMATE_READY',new_tests=count,**execution_fields(),
    observed_complete_fits=len(fits),source_observations=values,estimate=bound,
    future_peak_ram_bytes=16*GiB,providers_sha256=read(C/'finetune_plan_20261124.json')['providers_sha256'],
    active_contracts_changed=False,pretraining_reservations_changed=False,
    policy_activated=False,new_scientific_work=False,
    topology_basis='Pinned P inline fitting with threads; one main metadata query plus one observer guard; no training reader worker pool',
    interpretation='Conservative estimate from completed full-fit process peaks and bounded topology; not measured whole-tree peak. Root must activate only after active fullFT exits.')
write(PROOF,value)
write(R/'results/s_recipe/fullft_ram_envelope_20261127.json',value)
