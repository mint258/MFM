"""Pure exact protocol derivation and login metadata; cannot submit or invoke QM."""
import argparse,copy,hashlib,json,re
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q
HERE=Q.REPO/'workflows/data_v1_final/pprime/strict_numerics_qa_proposal_v1'
FILES=('__init__.py','proposal.py','test_v1.py','README.md')
KEY='PPRIME_STRICT_NUMERICS15_QA_PROPOSAL_V1'
NAMES=('pm7_B','pm7_water','pm7_octanol','pm7_cation','pm7_anion','xtb_singlepoint','xtb_vipea','xtb_vfukui','xtb_ALPB_water','xtb_ALPB_octanol','xtb_fod','xtb_perturbed_gradient')
ORIGINAL_PROTOCOL=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/configs/protocol.json')
ORIGINAL_PROTOCOL_SHA='3e831aa57d4d90376c6107e309484e231038a3536ed0f28371d2f8554149a6bc'
BASE_PM7='PM7 1SCF XYZ GRADIENTS BONDS MULLIK PI SUPER ENPART DISP AUX(PRECISION=6) LARGE LET CHARGE=0'
XTB_SP=['--gfn','2','--chrg','0','--uhf','0']
XTB_GRAD=['--gfn','2','--grad','--chrg','0','--uhf','0']
SCFCRT='SCFCRT=1.D-9';ACC=['--acc','0.01']
SOURCES=[{'title':'MOPAC SCFCRT keyword','url':'https://openmopac.net/Manual/scfcrt.html'},
    {'title':'MOPAC SCF test qualification','url':'https://openmopac.net/Manual/scf_test.html'},
    {'title':'xTB accuracy/integral/SCC semantics','url':'https://xtb-docs.readthedocs.io/en/latest/sp.html'}]


def derive(original):
    Q.need(tuple(t['name'] for t in original['tasks'])==NAMES and original['timeout_seconds']==900
        and original['seed']==20261010 and original['perturb_sigma_A']==0.1,'EXACT_ORIGINAL_RECIPE_SEED_SIGMA_TIMEOUT')
    old={t['name']:t for t in original['tasks']}
    Q.need(old['pm7_B']['family']=='mopac' and old['pm7_B']['keywords']==BASE_PM7
        and old['xtb_singlepoint']['family']==old['xtb_perturbed_gradient']['family']=='xtb'
        and old['xtb_singlepoint']['args']==XTB_SP and old['xtb_perturbed_gradient']['args']==XTB_GRAD
        and old['xtb_perturbed_gradient']['perturbed'] is True,'EXACT_THREE_EXECUTED_TASK_ARGUMENT_BASELINES')
    Q.need(all('timeout_seconds' not in old[n] for n in ('pm7_B','xtb_singlepoint','xtb_perturbed_gradient')),'NO_CALL_TIMEOUT_OVERRIDE')
    candidate=copy.deepcopy(original);by={t['name']:t for t in candidate['tasks']}
    by['pm7_B']['keywords']+=' '+SCFCRT
    for name in ('xtb_singlepoint','xtb_perturbed_gradient'):by[name]['args']+=ACC
    restored=restore(candidate);Q.need(restored==original,'ONLY_DECLARED_THREE_FIELDS_CHANGED')
    return candidate,[{'task':'pm7_B','field':'keywords','before':BASE_PM7,'after':by['pm7_B']['keywords']},
        *({'task':n,'field':'args','before':old[n]['args'],'after':by[n]['args']} for n in ('xtb_singlepoint','xtb_perturbed_gradient'))]


def restore(candidate):
    value=copy.deepcopy(candidate);by={t['name']:t for t in value['tasks']}
    Q.need(by['pm7_B']['keywords']==BASE_PM7+' '+SCFCRT,'EXACT_FIXED_SCFCRT_ONLY')
    by['pm7_B']['keywords']=BASE_PM7
    for name,base in (('xtb_singlepoint',XTB_SP),('xtb_perturbed_gradient',XTB_GRAD)):
        Q.need(by[name]['args']==base+ACC,'EXACT_FIXED_ACC_ONLY');by[name]['args']=list(base)
    return value


def once_key(protocol_reference,original_prepared_reference,qa_id):
    Q.need(qa_id in {'qa-%02d'%i for i in range(15)} and re.fullmatch('[0-9a-f]{64}',protocol_reference['sha256']),'ONLY15_QA_AND_REAL_PROTOCOL_SHA')
    raw=json.dumps(['independent-strict-numerics15-QA-v1',protocol_reference,original_prepared_reference,qa_id],sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(raw).hexdigest()


def draft(protocol_path,out,candidate_path=None):
    Q.need(Path(protocol_path)==ORIGINAL_PROTOCOL,'EXACT_ORIGINAL_PROTOCOL_LOCATOR');pin=Q.pin(protocol_path)
    Q.need(pin['sha256']==ORIGINAL_PROTOCOL_SHA,'ORIGINAL_FROZEN_PROTOCOL_BYTES');original=Q.load(protocol_path);candidate,diff=derive(original)
    out=Path(out);Q.need(out.is_absolute() and '..' not in out.parts and Q.ROOT/'control' in out.parents and not out.exists(),'FRESH_PROPOSAL_METADATA_ONLY')
    if candidate_path is not None:Q.need(Q.load(candidate_path)==candidate,'EXACT_PREPARED_CANDIDATE_THREE_FIELDS_ONLY')
    out.mkdir(parents=True,exist_ok=False,mode=0o700)
    pr=Q.pin(candidate_path) if candidate_path is not None else Q.write_new(out/'candidate_protocol.proposed.json',candidate)
    engine=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts/wp5_engine_v3.py')
    result={'schema':KEY,'status':'PROPOSED_UNAPPROVED_NOT_EXECUTED','requested_by':'root_review_pending','user_approval_reference':None,
        'production_protocol_reference':pin,'new_QA_protocol_reference':pr,'protocol_diff':diff,'inverse_declared_edits_equals_original':restore(candidate)==original,
        'minimum_source_references':[*(Q.pin(HERE/n) for n in FILES),Q.pin(engine),Q.pin(original['frozen_dependencies']['native_lifecycle']['path'])],
        'numerical_settings':{'mopac_SCFCRT_kcal_mol':'1.D-9','xtb_accuracy_multiplier':'0.01'},'primary_sources':SOURCES,
        'scope':{'original_source_cases':['case-054','case-055','case-058','case-059','case-060','case-061'],
            'original_molecule_id':'molecule_01200493','conditions':['pm7_B','xtb_perturbed_gradient','xtb_singlepoint_noisy_companion'],
            'arms':['B1','B2','R1','P1','P2'],'maximum_new_QM_calls':15,'maximum_simultaneous_native_calls':15,
            'original_record_ID_seed_actual_coordinates_and_native_atom_order_preserved':True,'new_numeric_tolerances':False,
            'actual_executed_task_types':3,'other_nine_task_entries_unchanged_and_unexecuted':True,
            'new_once_domain':'independent-strict-numerics15-QA-v1 plus protocol triple/prepared triple/qa_id',
            'old_once_claims_modified_or_reused':False,'automatic_retry':False,'unknown_or_failed_call_replacement':False},
        'resources':{'kind':'qm','cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','exclusive':False,
            'node':'Root current approved QM CPU allowlist, actual freeCPU measured before submission','wall_seconds':7200,
            'per_call_timeout_seconds':900,'whole_output_cap_bytes':2<<30,'native_threads_per_call':1,'quota_reserve_bytes':200000000000,
            'output_basis':'same conservative2GiB cap as prior15 execution; original per-call raw16MiB/result8MiB caps retained; not a runtime prediction',
            'resource_pressure':'STOP_NEW_DISPATCH_NATURAL_DRAIN_NO_NEW_SIGNALS','cost_overrun_action':'REPORT_AND_CONTINUE'},
        'comparison':{'actual_controls':'retained original72,1766/1802,1845 and1891 facts; fresh strict B/P repeats retained',
            'checks':'original covariance/frame/input-byte/parser/native-print criteria unchanged; all native outputs retained',
            'SCF_or_property_improvement_not_promised':True,'pass_does_not_isolate_SCF_from_integral_screening_for_xTB':True,
            'any_FAIL_or_UNKNOWN':'REPORT_HOLD_NO_SCOPE_EXPANSION',
            'if_all15_pass':'Root separate gate before any20-molecule all12-task/rotation QA; no automatic promotion'},
        'unchanged':{'methods':'PM7/GFN2','versions':original['expected_versions'],'seed':original['seed'],'sigma_A':original['perturb_sigma_A'],
            'timeout_seconds':original['timeout_seconds'],'AUX_precision':6,'xTB_temperature_or_iterations_overrides_added':False,
            'SCFCRT_is_primary_criterion_not_promise_of_all_effective_tests':True,'production_recipe_or_original_return_state_modified':False},
        'original15FAIL_preserved':True,'scientific_PASS':False,'production_or_full_or2000_release':'HOLD',
        'execution_entrypoint_present':False,'native_call_or_submission_performed':False,'synthetic_tests_executed_by_helper':False,
        'interface_audit':'Frozen engine accepts independent protocol dict/path; original invoke directly consumes task keywords/args. New diagnostic protocol is an explicit authorized scientific configuration seam; frozen program implementations unchanged.'}
    return Q.write_new(out/'proposal_for_user_review.json',result)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['draft']);p.add_argument('--original-protocol',type=Path,required=True);p.add_argument('--candidate-protocol',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(draft(a.original_protocol,a.output,a.candidate_protocol))


if __name__=='__main__':main()
