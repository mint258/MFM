"""Call the shared versioned library; preserve every unsuccessful diagnostic."""
import hashlib
import json
import os
from pathlib import Path
import traceback
from ..alpha_runtime_v1 import common as Q
from . import probe

STATE=None


def initialize(plan,barrier,directory,original_refs):
    global STATE
    try:
        for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
        path=Path(directory)/('worker_%s.log'%os.getpid());fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        os.dup2(fd,1);os.dup2(fd,2);os.close(fd)
        from ..generic_representation_repair_v1 import library as L
        from .. import common,screen,features_legacy_compatible_v2 as old,features_generic_candidate_v1 as generic
        from ..common_molecular_fp_candidate_v1 import worker as W
        state=L.initialize();nongeneric,proof=probe.initialize(screen,generic)
        declared={r['path']:r for r in plan['code_references']+plan.get('scientific_source_references',[])}
        modules=[L,L.N,W,common,screen,old,generic]
        for module in modules:
            Q.need(declared.get(module.__file__)==Q.reference(module.__file__),'Exact actual dependency source pin: '+module.__file__)
        official=state['official']['installed_source']
        Q.need(declared.get(official['path'])==Q.reference(official['path']),'Exact official RDKit Murcko source')
        for module in (common,screen,old,generic):
            origin=original_refs[Path(module.__file__).name];actual=Q.reference(module.__file__)
            Q.need((actual['bytes'],actual['sha256'])==(origin['bytes'],origin['sha256']),
                   'Actual native original science must equal old Alpha frozen bytes')
        STATE=dict(library=L,state=state,screen=screen,probe=nongeneric,proof=proof)
        Q.write(Path(directory)/('worker_%s.json'%os.getpid()),dict(uid=os.getuid(),job_id=os.environ['SLURM_JOB_ID'],
            pid=os.getpid(),library_source_proof=state['source_proof'],non_generic_probe_proof=proof,
            original_Alpha_frozen_science_body_bytes_equal=True,official_source=official))
        barrier.wait()
    except BaseException:
        barrier.abort();raise


def error(exc):
    return dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())


def diagnose(task):
    row=task['observation']['original_typed_fields'];cid=int(row['cid_source_ascii']);smiles=row['source_smiles'];ordinal=row['ordinal']
    result=dict(schema='PUBCHEM_GENERIC_UNKNOWN_NATIVE_DIAGNOSTIC_ROW_V1',source=task,
        worker_pid=os.getpid(),original_technical_UNKNOWN_retained=True,scientific_acceptance=False,
        pool_or_baseline_modified=False,original_InChI_or_raw_graph_repair_attempted=False)
    L=STATE['library'];N=L.N
    try:
        mol,flags=STATE['screen'].chemical_flags(smiles)
        Q.need(mol is not None and flags==json.loads(row['audit_flags_json'])
               and set(flags)=={'X01','X02','X03','X04','X05'} and all(v is False for v in flags.values()),
               'Actual original X audit must equal recorded allFalse X flags')
        original_snapshot=N.snapshot(mol);expected=STATE['probe'](cid,smiles,ordinal)
        # evaluate owns whole-function compatibility fallback routing. No ring
        # fragments or expected generic keys are spliced together in this audit.
        evaluation=L.evaluate(cid,smiles,ordinal)
        result['native_evaluation_JSON_text']=json.dumps(evaluation,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=True)
        actual={k:v for k,v in evaluation['features'].items() if k not in probe.GENERIC}
        differences={k:dict(expected_canonical_JSON=Q.canonical(expected.get(k)).decode(),
                            actual_canonical_JSON=Q.canonical(actual.get(k)).decode())
                     for k in set(actual)|set(expected) if Q.canonical(actual.get(k))!=Q.canonical(expected.get(k))}
        check_mol,check_flags=STATE['screen'].chemical_flags(smiles)
        template_equal=(check_mol is not None and Q.canonical(N.snapshot(check_mol))==Q.canonical(original_snapshot))
        recorded=task['observation']['recorded_exception_observation']['errors'][0]
        current_error=evaluation.get('original_error',{})
        failure_equal=(current_error.get('message')==recorded['message']
                       and current_error.get('type')==recorded['exception_type'])
        Q.need(hashlib.sha256(smiles.encode('utf-8')).hexdigest()==row['source_smiles_sha256'],'Original whole source SMILES SHA')
        result.update(non_generic_expected=expected,non_generic_fields=sorted(expected),
            non_generic_field_set_equal=set(actual)==set(expected),exact_non_generic_differences=differences,
            original_X_flags=flags,after_original_X_flags=check_flags,original_template_snapshot=original_snapshot,
            original_template_snapshot_equal_after=template_equal,whole_source_SMILES_SHA_equal=True,
            representation_version=L.VERSION,representation_repair_applied=evaluation['representation_repair_applied'],
            original_kernel_passed=evaluation['original_kernel_passed'],
            original_failure=evaluation.get('original_error'),original_failure_type_message_equal_recorded=failure_equal,
            generic_events=evaluation['events'])
        passed=(set(actual)==set(expected) and not differences and template_equal and check_flags==flags
                and evaluation['representation_repair_applied'] is True and evaluation['original_kernel_passed'] is False
                and failure_equal and evaluation.get('original_error',{}).get('type')=='AtomValenceException'
                and any(e.get('heavy_adjacency_allC_SINGLE_verified') is True for e in evaluation['events'])
                and all(e.get('heavy_adjacency_allC_SINGLE_verified',True) for e in evaluation['events']))
        result['diagnostic_status']='REPAIRED_CANDIDATE_NON_GENERIC_EXACT' if passed else 'DIAGNOSTIC_UNRESOLVED_OR_COMPARISON_DIFFERENT'
    except Exception as exc:
        result.update(diagnostic_status='DIAGNOSTIC_EXCEPTION_PRESERVED',native_exception=error(exc))
    return result
