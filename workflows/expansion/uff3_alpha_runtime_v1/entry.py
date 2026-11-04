"""Launcher-bound Alpha UFF metadata entry; original scientific kernels unchanged."""
import argparse
import fcntl
import os
from pathlib import Path
import sys
import stat
import uuid
from ..alpha_runtime_v1 import common as Q,profile
from ..uff3_candidate_v1 import run as generation,core as C
from .quality_authority import accepted,read
from .terminal import parent as terminal_parent

MODULE='workflows.expansion.uff3_alpha_runtime_v1.entry'


def admit(plan_path,proof_path,module=MODULE):
    plan=Q.load(plan_path);proof=Q.load(proof_path);request=proof['request'];argv=plan['execution_argv']
    actual=profile.admit(plan,minimum_workers=16)
    Q.need(proof['uid']==os.getuid()==actual['uid']==Q.UID
        and proof['endpoint']==plan['endpoint']==Q.ENDPOINT
        and str(proof['job_id'])==actual['job_id']==os.environ.get('SLURM_JOB_ID')
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        and request['producer_plan_reference']==Q.reference(plan_path)
        and request['execution_argv']==argv and request['scope_key']==plan['scope_key']
        and len(argv)==9 and argv[0]==sys.executable and argv[1:3]==['-I','-B']and argv[4]==module
        and argv[5:]==sys.argv[1:]==['--plan',str(plan_path),'--startup-proof',str(proof_path)],
        'Exact actual Alpha isolated launcher plan/proof/job/boot/argv required')
    folder=Path(generation.__file__).parent
    paths=list(Path(__file__).parent.glob('*.py'))+[folder/name for name in
        ('run.py','resources.py','credit.py','ledger_resume.py','core.py','native.py','store.py','families.py','quality.py')]+[Path(argv[3])]
    refs=[Q.reference(p)for p in paths]
    Q.need(all(ref in plan['code_references']and ref in request['source_references']for ref in refs),
        'Every Alpha adapter and actual UFF runtime/scientific source must be pinned in native startup')
    return plan,actual,refs


def partition(plan):
    review=plan['storage_partition']
    if 'future_budget'in review:
        from .budget import validate
        budget=validate(review['future_budget'],plan)
    else:budget=read(review['future_budget_review_reference'])
    Q.need(review['endpoint']==budget['endpoint']==Q.ENDPOINT and review['uid']==budget['uid']==Q.UID
        and ('future_budget'in review or(budget['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2'and budget['reviewer']=='root'))
        and review['routing_scope_root']==plan['output_scope_root']
        and review['inner_stage_is_only_child']is True
        and review['routing_budget_includes_all_ancestors']is True,'Actual private UFF partition within Root full-future budget required')
    names=('closed_legacy_allocated_bytes','routing_overhead_reserved_bytes','inner_output_cap_bytes',
           'peer_stage_caps_bytes','peer_remaining_reserved_bytes','other_future_reserved_bytes')
    Q.need(all(type(review[k])is int and review[k]>=0 for k in names),'Exact nonnegative partition accounting integers')
    Q.need(review['closed_legacy_allocated_bytes']+review['routing_overhead_reserved_bytes']
        +review['inner_output_cap_bytes']+review['peer_stage_caps_bytes']<=budget['scope_total_caps_bytes']['UFF']
        and review['peer_remaining_reserved_bytes']<=review['peer_stage_caps_bytes']
        and review['other_future_reserved_bytes']>=budget['other_future_reserved_bytes_for_each_scope']['UFF']
            +review['peer_remaining_reserved_bytes']+review['routing_overhead_reserved_bytes']
        and plan['output_cap_bytes']==review['inner_output_cap_bytes']
        and plan['other_future_reserved_bytes']==review['other_future_reserved_bytes']
        and plan['minimum_free_bytes']==budget['minimum_free_after_all_future_bytes'],
        'B+routing+all stage caps must fit global UFF; all peer/nonUFF future and floor retained')
    # Root's exact closed census pin is evidence for B, never a fabricated B=0.
    Q.verify(review['closed_legacy_census_reference'])
    return review


def routing_overhead(review,routing):
    """Actual few-ancestor blocks only; never enumerate legacy output bodies."""
    routing=Path(routing);global_root=Path(review['global_UFF_scope_root'])
    Q.need(global_root.is_absolute()and routing.is_relative_to(global_root),'Actual declared global UFF/routing relationship')
    paths=[routing]
    while paths[-1]!=global_root:paths.append(paths[-1].parent)
    Q.need(review['routing_ancestor_paths']==[str(p)for p in paths],
           'Exact complete routing-to-global-UFF ancestor list')
    total=0
    for path in paths:
        s=path.lstat()
        Q.need(stat.S_ISDIR(s.st_mode)and s.st_uid==os.getuid(),'Own literal routing/ancestor directory')
        total+=s.st_blocks*512
    lock=routing/'uff_alpha_routing.lock'
    if lock.exists():
        s=lock.lstat();Q.need(stat.S_ISREG(s.st_mode)and s.st_uid==os.getuid(),'Own literal routing lock')
        total+=s.st_blocks*512
    Q.need(total<=review['routing_overhead_reserved_bytes'],'Actual routing/ancestor blocks exceed reserved partition overhead')
    return total

def same_pilot_stage(plan,review):
    Q.need(Path(review['pilot_generation_receipt_reference']['path']).parent==Path(plan['output_directory'])
        and bool(plan.get('resume_binding'))
        and plan.get('shard_count',1)==1 and plan.get('shard_index',0)==0,
        'Full allocation must resume the actual pilot stage; no fresh scope or implicit cross-shard cache adoption')

def pilot(plan):
    b=plan['pilot_completed'];receipt=read(b['generation_receipt_reference']);qa=read(b['quality_report_reference'])
    terminal_parent(receipt['runtime'],b['generation_accounting_reference'])
    terminal_parent(qa['runtime'],b['quality_accounting_reference'])
    same_pilot_stage(plan,{'pilot_generation_receipt_reference':b['generation_receipt_reference']})
    Q.need(receipt['schema']=='PUBCHEM_UFF3_ALLOCATION_RECEIPT_V1'
        and receipt['status']=='COMPLETE_CANDIDATE_PILOT_NOT_TRAINING_RELEASE'
        and receipt['mode']=='pilot'and receipt['expected_molecules']==receipt['closed_family_export_molecules']==10000
        and sum(receipt['state_counts'].values())==10000
        and receipt['source_manifest']==plan['source_manifest']
        and receipt['quality_reference_review']==plan['quality_reference_review']
        and receipt['recipe_sha256']==C.recipe_sha()
        and receipt['wall_seconds']>=0 and bool(receipt['last_resource_observation'])
        and qa['schema']=='PUBCHEM_UFF3_VALIDITY_REVIEW_V1'and qa['mode']=='pilot'
        and qa['status']=='COMPLETE_ORIGINAL_MASK_AND_ROBUST_REVIEW_REPORT'
        and qa['source_molecules_by_stream']=={'R':5000,'N':5000}
        and qa['source_state_counts']==receipt['state_counts']
        and b['generation_receipt_reference']in qa['generation_receipts']
        and qa['quality_reference_review']==plan['quality_reference_review']
        and qa['new_R_N_TRAIN_fit']is False
        and qa['technical_unknown_sources_preserved_not_fabricated_as_valid']is True,
        'Actual same-source10k producer/QA/observed resources; no manual Root approval or success/cost threshold')

def derive(plan,actual,plan_ref,proof_ref):
    Q.need('_metadata_entry_files'not in plan,'Entry-owned derived metadata field cannot be supplied by caller')
    action=plan.get('runtime_action','generation')
    Q.need(action in ('generation','quality'),'Explicit UFF generation or closed-output QA action')
    expected='PUBCHEM_UFF3_ALLOCATION_PLAN_V1'if action=='generation'else'PUBCHEM_UFF3_QUALITY_PLAN_V1'
    Q.need(plan['schema']==expected,'Exact owned UFF runtime action plan schema')
    review=partition(plan);accepted(plan['quality_reference_review'])
    bindings=read(plan['quality_bindings_reference'])
    Q.need(bindings['schema']=='PUBCHEM_ALPHA_UFF_FULLTRAIN_QUALITY_BINDINGS_V1'
        and all(plan[k]==bindings[k]for k in('source_capsule_reference','parent_transport_manifest','quality_reference_review')),
        'Same actual original UFF sources plus fullTRAIN189 transport metadata')
    if action=='quality':
        Q.need(bool(plan['generation_actual_accounting_references'])and bool(plan['generation_receipts']),
               'Closed generation scope and real terminal accounting cannot be empty')
        accounts=[read(ref)for ref in plan['generation_actual_accounting_references']]
        parents=[]
        for account in accounts:
            Q.need(account['endpoint']==Q.ENDPOINT and account['uid']==Q.UID,'Actual Alpha generation accounting endpoint/UID')
            Q.verify(account['raw_sacct_reference']);parents.extend(account['actual_parents'])
        for ref in plan['generation_receipts']:
            receipt=read(ref)
            matches=[p for p in parents if str(p['JobIDRaw'])==str(receipt['runtime']['job_id'])]
            Q.need(len(matches)==1 and matches[0]['State']=='COMPLETED'and matches[0]['ExitCode']=='0:0'
                and int(matches[0]['UID'])==Q.UID and receipt['runtime']['endpoint']==Q.ENDPOINT,
                'Only terminal actual generation output may be opened by QA; never an active writer SQLite')
            refs=[ref for ref,a in zip(plan['generation_actual_accounting_references'],accounts)if any(str(p['JobIDRaw'])==str(receipt['runtime']['job_id'])for p in a['actual_parents'])]
            Q.need(len(refs)==1,'One actual generation accounting source')
            terminal_parent(receipt['runtime'],refs[0])
    if action=='generation':
        from .ordered_contract import completed_source
        completed_source(plan,read(plan['source_manifest']))
        Q.need(plan['maximum_conformers']==3 and plan['no_fill']is True and plan['no_retry']is True
            and plan['recipe_sha256']==C.recipe_sha(),'Frozen max3 recipe, no fill or scientific retry')
        if plan.get('mode','full')=='full':pilot(plan)
    routing=Path(plan['output_scope_root']);out=Path(plan['output_directory'])
    Q.need(out.parent==routing and out!=routing and not any(p.is_symlink()for p in(out,*out.parents)),
           'Only direct actual inner stage in exclusive routing scope')
    routing_bytes=routing_overhead(review,routing)
    permitted={out.name,'uff_alpha_routing.lock'}
    Q.need(all(p.name in permitted for p in routing.iterdir()),'Routing scope contains another stage or unexpected writer output')
    reserve=plan['metadata_wrapper_reserved_bytes']
    Q.need(type(reserve)is int and 1<<20<=reserve<plan['output_cap_bytes'],'Finite wrapper reservation within inner cap')
    runtime={**plan,'output_scope_root':str(out),'output_cap_bytes':plan['output_cap_bytes']-reserve,
        'other_future_reserved_bytes':plan['other_future_reserved_bytes']+reserve,
        'original_launcher_plan_reference':plan_ref,'original_startup_proof_reference':proof_ref,
        'derived_stage_scope_accounting':True,'wrapper_reserved_bytes':reserve,
        'actual_routing_ancestor_allocated_bytes':routing_bytes}
    return runtime,review


def execute(plan_path,proof_path):
    plan,actual,refs=admit(plan_path,proof_path)
    routing=Path(plan['output_scope_root'])
    fd=os.open(routing/'uff_alpha_routing.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    lock=os.fdopen(fd,'a+b');fact=os.fstat(lock.fileno())
    Q.need(stat.S_ISREG(fact.st_mode)and fact.st_uid==Q.UID and fact.st_nlink==1,'Own literal exclusive routing lock')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        runtime,review=derive(plan,actual,Q.reference(plan_path),Q.reference(proof_path))
        out=Path(runtime['output_directory']);out.mkdir(parents=False,exist_ok=True)
        token=actual['job_id']+'_'+uuid.uuid4().hex
        derived_ref=Q.write(out/('derived_runtime_plan_'+token+'.json'),runtime)
        runtime['_derived_runtime_plan_reference']=derived_ref
        if plan.get('runtime_action','generation')=='generation':
            result=generation.run(runtime)
            receipt_paths=list(out.glob('receipt_job'+actual['job_id']+'_*.json'))
            matches=[p for p in receipt_paths if Q.load(p)==result]
            Q.need(len(matches)==1,'Exactly one actual original generation receipt; never rewrite scientific output')
            original=Q.reference(matches[0])
        else:
            from ..uff3_candidate_v1 import quality
            result=quality.run({**runtime,'_metadata_entry_files':[derived_ref]});original=Q.reference(out/'result.json')
        return result,original
    finally:lock.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();result,_=execute(a.plan,a.startup_proof)
    if result.get('status')=='PARTIAL_RETAINED_NO_SCIENTIFIC_RETRY':raise SystemExit(3)


if __name__=='__main__':main()