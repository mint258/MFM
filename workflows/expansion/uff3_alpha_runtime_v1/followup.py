"""QA and same-stage full templates from actual completed pilot machine data."""
import argparse
import copy
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from ..uff3_candidate_v1 import core as C
from ..uff3_candidate_v1.ledger_resume import resume_authority,assert_registered_writers_gone
from .quality_authority import read
from .terminal import parent
from . import prepare,budget,entry


def pilot_inputs(receipt_ref,account_ref):
    r=read(receipt_ref);parent(r['runtime'],account_ref)
    Q.need(r['schema']=='PUBCHEM_UFF3_ALLOCATION_RECEIPT_V1'
        and r['status']=='COMPLETE_CANDIDATE_PILOT_NOT_TRAINING_RELEASE'and r['mode']=='pilot'
        and r['expected_molecules']==r['closed_family_export_molecules']==10000
        and r['recipe_sha256']==C.recipe_sha()and sum(r['state_counts'].values())==10000,
        'Real complete balanced10k pilot machine result, never a replacement sample')
    meta=r['execution_metadata'];plan_ref=meta['original_launcher_plan_reference'];startup_ref=meta['original_startup_proof_reference']
    p=read(plan_ref);proof=read(startup_ref)
    Q.need(proof['request']['producer_plan_reference']==plan_ref
        and str(proof['job_id'])==str(r['runtime']['job_id'])
        and p['output_directory']==str(Path(receipt_ref['path']).parent)
        and p['source_manifest']==r['source_manifest'], 'Pilot actual output/plan/startup/source pin')
    binding=dict(scope='UFF',runtime=r['runtime'],plan_reference=plan_ref,
        startup_proof_reference=startup_ref,accounting_reference=account_ref,generation_receipt_reference=receipt_ref)
    return r,p,binding


def refresh(config,output,extra,inherited=None):
    allocations=list(config['closed_allocations'])
    inherited_bindings=budget.read_census(inherited)['closed_allocations']if inherited else[]
    for b in [*inherited_bindings,*extra]:
        if not any(a['plan_reference']==b['plan_reference']for a in allocations):allocations.append(b)
    ref=budget.census(config['baseline_budget_reference'],allocations,config['excluded_active_allocations'],
                      Path(output)/'native_closed_blocks.json',config['global_UFF_scope_root'])
    return budget.inline(config['baseline_budget_reference'],ref),budget.read_census(ref)


def qa(config,pilot_ref,pilot_account_ref,output,bindings_ref=None):
    root=Path(output);root.mkdir(parents=True,exist_ok=False);config=copy.deepcopy(config)
    config['quality_bindings_reference']=bindings_ref or Q.reference(prepare.BINDINGS)
    bindings=read(config['quality_bindings_reference']);r,old,binding=pilot_inputs(pilot_ref,pilot_account_ref)
    Q.need(all(r[k]==bindings[k]for k in('source_capsule_reference','parent_transport_manifest','quality_reference_review')),
           'Same actual original science/189 bindings for pilot QA')
    inline,c=refresh(config,root,[binding],old['storage_partition']['future_budget']['closed_census_reference']);gen=Path(pilot_ref['path']).parent
    routing=Path(config['global_UFF_scope_root'])/('quality_pilot_'+pilot_ref['sha256'][:12])
    output=routing/'uff3_qa_LAUNCHER_ASSIGN_REAL_JOB_ID'
    part=prepare.partition_for(config,inline,c,'quality',routing,output,gen)
    p=prepare.resources(config,bindings,inline,part,'quality',routing,output)
    p.update(schema='PUBCHEM_UFF3_QUALITY_PLAN_V1',runtime_action='quality',mode='pilot',
        scope_key='uff3_qa_'+pilot_ref['sha256'][:16],source_manifest=r['source_manifest'],
        generation_receipts=[pilot_ref],generation_actual_accounting_references=[pilot_account_ref],
        sql_memory_bytes=config['qa_sql_memory_bytes'],spill_cap_bytes=config['qa_spill_cap_bytes'],
        build_metadata={'template_only':True,'Slurm_submitted':False,'actual_pilot_job_id':r['runtime']['job_id']})
    return Q.write(root/'qa_plan_template.json',p)


def previous(root,source,account_refs):
    """Inventory actual immutable attempt markers, not per-job approval files."""
    unique={Q.canonical(ref):ref for ref in account_refs}
    accounts=[(ref,read(ref))for ref in unique.values()];out=[];seen=set()
    for path in sorted(Path(root).glob('derived_runtime_plan_*.json')):
        marker=Q.load(path);ref=marker['original_launcher_plan_reference']
        token=Q.canonical(ref)
        if token in seen:continue
        seen.add(token);plan=read(ref);startup_ref=marker['original_startup_proof_reference'];proof=read(startup_ref)
        Q.need(plan['source_manifest']==source and plan['output_directory']==str(root),
               'All previous real scope attempts have same source and literal output')
        job=str(proof['job_id']);matches=[r for r,a in accounts if any(str(p['JobIDRaw'])==job for p in a['actual_parents'])]
        Q.need(len(matches)==1,'Actual terminal accounting for every old attempt, including failed prefixes')
        item=dict(plan_reference=ref,startup_proof_reference=startup_ref,accounting_reference=matches[0])
        receipts=[]
        for candidate in Path(root).glob('receipt_job'+job+'_*.json'):
            value=Q.load(candidate)
            if str(value['runtime']['job_id'])==job:receipts.append(candidate)
        Q.need(len(receipts)<=1,'Ambiguous old producer result for one immutable native job')
        if receipts:item['runtime_receipt_reference']=Q.reference(receipts[0])
        out.append(item)
    Q.need(bool(out),'Pilot stage must retain its actual attempt/source metadata')
    return dict(output_scope_root=str(root),source_manifest=source,recipe_sha256=C.recipe_sha(),previous_allocations=out)


def full(config,pilot_ref,pilot_account_ref,qa_ref,qa_account_ref,output,bindings_ref=None):
    root=Path(output);root.mkdir(parents=True,exist_ok=False);config=copy.deepcopy(config)
    config['quality_bindings_reference']=bindings_ref or Q.reference(prepare.BINDINGS)
    bindings=read(config['quality_bindings_reference']);r,old,binding=pilot_inputs(pilot_ref,pilot_account_ref)
    Q.need(all(r[k]==bindings[k]for k in('source_capsule_reference','parent_transport_manifest','quality_reference_review')),
           'Full keeps the actual pilot scientific source/189 bindings')
    report=read(qa_ref);parent(report['runtime'],qa_account_ref)
    Q.need(report['mode']=='pilot'and report['source_molecules_by_stream']=={'R':5000,'N':5000}
        and pilot_ref in report['generation_receipts']and report['quality_reference_review']==bindings['quality_reference_review'],
        'Actual same-pilot original mask/robust report, not full or historical unrelated QA')
    qa_plan_ref=report['execution_metadata']['original_launcher_plan_reference']
    qa_binding=dict(scope='UFF',runtime=report['runtime'],plan_reference=qa_plan_ref,
        startup_proof_reference=report['execution_metadata']['original_startup_proof_reference'],accounting_reference=qa_account_ref)
    inline,c=refresh(config,root,[binding,qa_binding],old['storage_partition']['future_budget']['closed_census_reference']);gen=Path(pilot_ref['path']).parent;routing=Path(old['output_scope_root'])
    part=prepare.partition_for(config,inline,c,'generation',routing,gen,gen)
    p=prepare.resources(config,bindings,inline,part,'generation',routing,gen)
    # Freeze original scientific/runtime shape while rebinding only real current
    # resources/code/quota. Future full has no invented job ID or startup pin.
    for k in ('source_manifest','source_completed','recipe_sha256','user_policy','maximum_conformers','no_fill','no_retry',
              'family_batch_molecules'):
        p[k]=old[k]
    p.update(worker_rss_soft_cap_bytes=config['worker_rss_soft_cap_bytes'],maximum_molecule_output_bytes=config['maximum_molecule_output_bytes'],
        parent_family_reserved_bytes=config['parent_family_reserved_bytes'],ledger_rebuild_reserved_bytes=config['ledger_rebuild_reserved_bytes'])
    p.update(schema='PUBCHEM_UFF3_ALLOCATION_PLAN_V1',runtime_action='generation',mode='full',scope_key=old['scope_key'],
        resume_output_directory=str(gen),shard_index=0,shard_count=1,selected_molecules=2500000,selected_molecules_by_stream={'R':1250000,'N':1250000},
        pilot_completed=dict(generation_receipt_reference=pilot_ref,generation_accounting_reference=pilot_account_ref,
                             quality_report_reference=qa_ref,quality_accounting_reference=qa_account_ref),
        resume_binding=previous(gen,r['source_manifest'],[pilot_account_ref,*config.get('previous_accounting_references',[])]),
        build_metadata={'template_only':True,'Slurm_submitted':False,'resume_exact_actual_pilot_output':str(gen)})
    # These are the same direct producer/terminal gates used by the runtime;
    # no human approval or native scientific replay occurs in plan preparation.
    entry.pilot(p)
    assert_registered_writers_gone(resume_authority(p,gen))
    return Q.write(root/'full_plan_template.json',p)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=('qa','full'))
    p.add_argument('--config',required=True,type=Path);p.add_argument('--pilot',required=True,type=Path)
    p.add_argument('--pilot-accounting',required=True,type=Path);p.add_argument('--qa',type=Path);p.add_argument('--qa-accounting',type=Path)
    p.add_argument('--bindings',type=Path,default=prepare.BINDINGS);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    config=Q.load(a.config);args=(config,Q.reference(a.pilot),Q.reference(a.pilot_accounting))
    if a.phase=='qa':result=qa(*args,a.output,Q.reference(a.bindings))
    else:
        Q.need(a.qa is not None and a.qa_accounting is not None,'Full needs actual completed QA, no future placeholder')
        result=full(*args,Q.reference(a.qa),Q.reference(a.qa_accounting),a.output,Q.reference(a.bindings))
    print(result)


if __name__=='__main__':main()