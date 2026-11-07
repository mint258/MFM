"""Allocated exact-primary3 diagnosis, with separate ontology and metadata bounds."""
import argparse
import concurrent.futures as cf
import io
import json
import multiprocessing as mp
import os
import sys
import traceback
import unittest
from pathlib import Path
from workflows.expansion.coconut_alpha_cached735_v1 import support as S
from workflows.expansion.coconut_alpha_cached735_v1.run import parent
from . import evidence as F, kernel as K, bounds
from .transport import Evidence


def admit(plan, proof, plan_path, proof_path):
    from workflows.expansion.alpha_runtime_v1 import profile
    result = profile.admit(plan, minimum_workers=16); req = proof['request']
    S.need(plan['schema'] == 'COCONUT_ALPHA_PRIMARY3_PLAN_V1'
           and plan['scope_key'] == req['scope_key'] == 'coconut_alpha_primary3_v1'
           and req['producer_plan_reference'] == S.pin(plan_path), 'ACTUAL_PRIMARY3_ROOT_PLAN')
    argv = req['execution_argv']
    S.need(argv == plan['execution_argv'] and argv[argv.index('--plan')+1] == str(plan_path)
           and argv[argv.index('--startup-proof')+1] == str(proof_path)
           and sys.argv[-4:] == ['--plan',str(plan_path),'--startup-proof',str(proof_path)],
           'EXACT_CURRENT_PRIMARY3_ROOT_CLI')
    S.need(proof['endpoint'] == plan['endpoint'] == '218.192.171.238:22'
           and proof['uid'] == plan['uid'] == os.getuid() == 1264
           and str(proof['job_id']) == os.environ.get('SLURM_JOB_ID')
           and proof['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
           'ACTUAL_PRIMARY3_ALPHA_JOB_UID_BOOT')
    refs = {r['path']:r for r in req['source_references']}
    import workflows.expansion.coconut_alpha_cached735_v1 as cached
    expected_files = [*Path(__file__).parent.glob('*.py'), *Path(cached.__file__).parent.glob('*.py')]
    for file in expected_files:
        S.need(refs.get(str(file.absolute())) == S.pin(file), 'EXACT_NEW_AND_BORROWED_CACHED735_SOURCE_BODY')
    for ref in req['source_references']: S.read(ref, 2 << 20)
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[key] = '1'
    return result


def fixtures(out):
    from .test_source import Source
    stream=io.StringIO(); suite=unittest.defaultTestLoader.loadTestsFromTestCase(Source)
    tested=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    ref=S.save(out/'source_tests.json',dict(tests=tested.testsRun,errors=len(tested.errors),
        failures=len(tested.failures),skips=len(tested.skipped),transcript=stream.getvalue(),before_primary_DATA=True))
    S.need(tested.wasSuccessful() and tested.testsRun == 6 and not tested.skipped,
           'SIX_SOURCE_ASSOCIATION_EXTRACTION_AND_NATIVE_FORMULA_FIXTURES')
    return ref


def execute(plan, out, guard):
    records, source_ref, receipt = parent(plan)  # Actual complete original735 chain, never name-only rows.
    selected={}
    for expected in F.IDS:
        matches=[r for r in records if json.loads(r['source']['identity_fields_json'])['id']==expected]
        S.need(len(matches)==1,'ONE_AND_ONLY_ONE_ORIGINAL_PHYSICAL_ENTRY_FOR_PRIMARY_ID')
        selected[expected]=matches[0]
    E=Evidence(plan);E.native735_original_plan=S.load(receipt['plan'])
    requests=[(selected['707929'],F.cyano(selected['707929'],E)),
                              (selected['174911'],F.inpac(selected['174911'],E)),
                              (selected['174178'],F.indofine(selected['174178'],E))]
    guard.check(); target=out/'primary3_source_bound_observations.DATA.jsonl'
    with target.open('xb') as stream, cf.ProcessPoolExecutor(max_workers=plan['workers'],
            mp_context=mp.get_context('spawn'),initializer=K.initialize,initargs=(plan,)) as pool:
        for result in pool.map(K.work, requests):
            guard.check(); stream.write(S.canonical(result))
        stream.flush(); os.fsync(stream.fileno())
    ontology=[]
    for row in E.manifest['rows']:
        if row['original_reference_id'] in ('CHEBI:10545','CHEBI:18140','CHEBI:17792'):
            rid=row['original_reference_id'].split(':')[1]
            html='CHEBI_'+rid+'.html';mol='CHEBI_'+rid+'.mol'
            E.read(html); E.read(mol)
            ontology.append(dict(research_classification=row, official_HTML_reference=E.ref(html),
                official_MOL_reference=E.ref(mol), no_representative_finite_molecule_substituted=True,
                ontology_semantics_not_converted_to_exclusion_rule=True, chemical_parse_called=False))
    S.need(len(ontology)==3, 'THREE_ONTOLOGY_WITNESSES_SEPARATE_FROM_PRIMARY3_MOLECULES')
    ont_ref=S.save(out/'CHEBI3_ontology_classification_witnesses.json',dict(rows=ontology,
        classification_only=True,scientific_domain_exception_or_exclusion_accepted=False))
    lower=bounds.from_receipt(plan)
    bounds_ref=S.save(out/'cached729_lower_bound_metadata_antichain.json',lower)
    guard.check()
    return dict(schema='COCONUT_ALPHA_PRIMARY3_DIAGNOSTIC_V1',
        status='COMPLETE_EXACT_PRIMARY_SOURCE_OBSERVATIONS_NOT_EXCLUSION_ACCEPTANCE',
        DATA=dict(S.pin(target),rows=3), native735_DATA_reference=source_ref,
        selected_original_entry_ids=list(F.IDS), primary_evidence_manifest_reference=E.manifest_ref,
        explicit_origin_windows_transport_reference=E.map_ref, consumed_primary_replicas=E.selected,
        ontology_classification_witnesses=ont_ref, lower_bound_metadata_antichain=bounds_ref,
        original_UNKNOWN735_retained=True, upstream_source_or_formula_composition_accepted=False,
        original_SQL_prefix_or_bracket_repaired=False, no_new_SDF_tautomers_or_stereoisomers_generated=True,
        strict5_rows_written=0, all11_ready=False, global_pool_release=False,
        new_UFF_QM_network_calls=0, native735_receipt_reference=plan['native735_receipt_reference'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True)
    args=p.parse_args();plan=json.loads(args.plan.read_text());proof=json.loads(args.startup_proof.read_text())
    authority=admit(plan,proof,args.plan,args.startup_proof)
    from workflows.expansion.alpha_runtime_v1.guard import Guard
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        guard.check();out.mkdir(parents=True,exist_ok=False);kernel_proof=K.initialize(plan)
        tests=fixtures(out);kernel_ref=S.save(out/'actual_frozen_kernel_proof.json',kernel_proof)
        result=execute(plan,out,guard)
        S.save(out/'receipt.json',dict(schema='COCONUT_ALPHA_PRIMARY3_PRODUCER_V1',
            plan=S.pin(args.plan),startup_proof=S.pin(args.startup_proof),source_tests=tests,
            kernel_proof=kernel_ref,profile_admission=authority,result=result,runtime=guard.receipt(),
            actual_parent_C0_pending_root_readback=True,all11_ready=False,global_pool_release=False))
    except BaseException as exc:
        if out.is_dir():S.save(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),
            original_UNKNOWN735_retained=True,partials_retained=True,no_scientific_acceptance=True))
        raise
    finally:guard.close()


if __name__=='__main__':main()
