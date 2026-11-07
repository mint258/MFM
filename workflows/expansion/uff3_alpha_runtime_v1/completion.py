"""Full QA/finalizer metadata plans from actual C0 full same-pilot generation."""
import argparse
import copy
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from ..uff3_candidate_v1 import core as C
from .quality_authority import read
from .terminal import parent
from . import followup,prepare


def generation(receipt_ref,account_ref,bindings):
    r=read(receipt_ref);parent(r['runtime'],account_ref)
    Q.need(r['schema']=='PUBCHEM_UFF3_ALLOCATION_RECEIPT_V1'and r['mode']=='full'
        and r['status']=='COMPLETE_CANDIDATE_SHARD_NOT_TRAINING_RELEASE'
        and r['shard_count']==1 and r['shard_index']==0
        and r['expected_molecules']==r['closed_family_export_molecules']==r['source_total_molecules']==2500000
        and sum(r['state_counts'].values())==2500000 and r['maximum_conformers']==3
        and r['recipe_sha256']==C.recipe_sha() and r['new_QM_calls']==0,
        'Actual complete2.5M same-stage result; sparse/failed/unknown sources stay present')
    Q.need(all(r[k]==bindings[k]for k in ('quality_reference_review','source_capsule_reference','parent_transport_manifest')),
           'Full result uses actual same original science/189 reference, no R/N refit')
    meta=r['execution_metadata'];p=read(meta['original_launcher_plan_reference'])
    Q.need(Path(receipt_ref['path']).parent==Path(p['output_directory']) and p['source_manifest']==r['source_manifest']
        and p['resume_output_directory']==p['output_directory'] and 'pilot_completed'in p,
        'Full must extend actual completed pilot in the identical output stage')
    binding=dict(scope='UFF',runtime=r['runtime'],plan_reference=meta['original_launcher_plan_reference'],
        startup_proof_reference=meta['original_startup_proof_reference'],accounting_reference=account_ref,
        generation_receipt_reference=receipt_ref)
    return r,p,binding


def prepare_completion(config,generation_ref,generation_account_ref,output,*,qa_ref=None,qa_account_ref=None,bindings_ref=None):
    root=Path(output);root.mkdir(parents=True,exist_ok=False);config=copy.deepcopy(config)
    config['quality_bindings_reference']=bindings_ref or Q.reference(prepare.BINDINGS)
    bindings=read(config['quality_bindings_reference']);r,old,binding=generation(generation_ref,generation_account_ref,bindings)
    extras=[binding];report=None
    if qa_ref is not None:
        Q.need(qa_account_ref is not None,'Finalizer needs actual full QA accounting')
        report=read(qa_ref);parent(report['runtime'],qa_account_ref)
        Q.need(report['schema']=='PUBCHEM_UFF3_VALIDITY_REVIEW_V1'and report['mode']=='full'
            and report['status']=='COMPLETE_ORIGINAL_MASK_AND_ROBUST_REVIEW_REPORT'
            and report['source_molecules_by_stream']=={'R':1250000,'N':1250000}
            and report['generation_receipts']==[generation_ref]
            and all(report[k]==bindings[k]for k in ('quality_reference_review','source_capsule_reference','parent_transport_manifest'))
            and report['new_R_N_TRAIN_fit']is False and report['new_UFF_QM_calls']==0,
            'Finalizer consumes actual complete full QA from the same2.5M generation/source/reference')
        from .quality_gate import require_within_one_percent
        require_within_one_percent(report)
        m=report['execution_metadata']
        extras.append(dict(scope='UFF',runtime=report['runtime'],plan_reference=m['original_launcher_plan_reference'],
            startup_proof_reference=m['original_startup_proof_reference'],accounting_reference=qa_account_ref))
    inline,c=followup.refresh(config,root,extras,old['storage_partition']['future_budget']['closed_census_reference'])
    role='finalizer'if report is not None else'quality';gen=Path(generation_ref['path']).parent
    routing=Path(config['global_UFF_scope_root'])/(role+'_full_'+generation_ref['sha256'][:12])
    out=routing/(role+'_LAUNCHER_ASSIGN_REAL_JOB_ID')
    part=prepare.partition_for(config,inline,c,role,routing,out,gen)
    p=prepare.resources(config,bindings,inline,part,role,routing,out)
    p.update(scope_key='uff3_'+role+'_'+generation_ref['sha256'][:16],source_manifest=r['source_manifest'],
        generation_receipts=[generation_ref],generation_actual_accounting_references=[generation_account_ref],
        sql_memory_bytes=config['qa_sql_memory_bytes'],spill_cap_bytes=config['qa_spill_cap_bytes'],
        build_metadata={'template_only':True,'Slurm_submitted':False,'full_generation_actual_job_id':r['runtime']['job_id'],
                        'generation_tree_reenumerated_for_budget':False,'scientific_values_recomputed':False})
    if report is None:
        p.update(schema='PUBCHEM_UFF3_QUALITY_PLAN_V1',runtime_action='quality',mode='full')
    else:
        p.update(schema='PUBCHEM_UFF3_CANDIDATE_CLOSURE_PLAN_V1',expected_molecules=2500000,maximum_conformers=3,
            qa_report_reference=qa_ref,qa_actual_accounting_reference=qa_account_ref,
            maximum_metadata_input_bytes=config['maximum_metadata_input_bytes'],
            maximum_molecule_artifact_bytes=config['maximum_molecule_artifact_bytes'],
            shared_input_references=config['shared_input_references'])
    return Q.write(root/(role+'_full_plan_template.json'),p)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=('qa-full','finalize'))
    p.add_argument('--config',required=True,type=Path);p.add_argument('--generation',required=True,type=Path)
    p.add_argument('--generation-accounting',required=True,type=Path);p.add_argument('--qa',type=Path);p.add_argument('--qa-accounting',type=Path)
    p.add_argument('--bindings',type=Path,default=prepare.BINDINGS);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    Q.need(a.phase=='qa-full'and a.qa is None and a.qa_accounting is None
        or a.phase=='finalize'and a.qa is not None and a.qa_accounting is not None,'Explicit full QA or actual closed full QA for finalizer')
    print(prepare_completion(Q.load(a.config),Q.reference(a.generation),Q.reference(a.generation_accounting),a.output,
        qa_ref=Q.reference(a.qa)if a.qa else None,qa_account_ref=Q.reference(a.qa_accounting)if a.qa_accounting else None,
        bindings_ref=Q.reference(a.bindings)))


if __name__=='__main__':main()