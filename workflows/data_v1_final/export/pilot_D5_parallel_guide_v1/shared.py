"""Consume only early closed D3 configuration components on an admitted CPU."""
import pathlib
import time
from . import contract as C
from workflows.data_v1_final.export.pilot_family_D3_census_resume_v3 import domain as D, io as I


def load(plan, accepted, roots, budget, root):
    directory = pathlib.Path(plan['shared_D3_configuration_locator'])
    locator = directory / 'closed_for_parallel_D5.json'
    d3plan = C.meta(plan['shared_D3_plan_reference'])
    # The locator is reviewed before execution; its first hash is computed here,
    # only after D3 writes its actual closed-component marker.
    while not locator.is_file():
        budget.check(force=True)
        C.need(not (pathlib.Path(d3plan['output_directory']) / 'failure.DATA.json').is_file(),
               'SHARED_D3_CONFIGURATION_FAILED_NO_DIAGNOSTIC_FAMILY_IMPUTATION')
        time.sleep(10)
    before = I.identity(locator)
    rr = I.pin(locator)
    D.register(rr, [*roots, d3plan['output_directory']])
    marker = I.load_data(rr, 8 << 20)
    C.need(I.identity(locator) == before and
           marker['schema'] == 'ACTUAL_RUNNING_D3_CONFIGURATION_COMPONENTS_CLOSED_V1' and
           marker['status'] == 'COMPONENTS_CLOSED_PARENT_RUNNING_NOT_C0_OR_D3_PAYLOAD_ACCEPTANCE' and
           marker['actual_D3_plan_reference'] == plan['shared_D3_plan_reference'] and
           marker['actual_D4_acceptance_reference'] == plan['pilot_acceptance_reference'] and
           marker['pilot_counts'] == C.O.COUNTS and marker['all_configuration_files_closed_and_hashed'] is True and
           marker['parent_terminal_or_D3_payload_or_Model_ACK_claimed'] is False,
           'REAL_SAME_D4_D3_CLOSED_COMPONENT_MARKER_NOT_FUTURE_C0')
    proof = C.meta(marker['actual_D3_startup_proof_reference'])
    C.need(str(proof['job_id']) == str(marker['actual_D3_job_id']) and proof['uid'] == 1278 and
           proof['request']['scope_key'] == C.O.KEY and proof['request']['cpus'] == 16 and
           proof['request']['execution_argv'] == [C.PY, '-B', '-m', C.O.MODULE, '--plan',
               plan['shared_D3_plan_reference']['path'], '--startup-proof', marker['actual_D3_startup_proof_reference']['path']],
           'ACTUAL_D3_PRODUCER_PROOF_NOT_PARENT_TERMINAL_CLAIM')
    gate = C.meta(marker['source3_reference'])
    C.need(gate['tests_run'] == 3 and gate['failures'] == gate['errors'] == gate['skips'] == 0,
           'ACTUAL_SHARED_D3_SOURCE3_PASS')
    configurations = marker['actual_configuration_references']
    expected = {'registry_reference', 'mapping_reference', 'projection_recipe_reference',
                'target_policy_reference', 'configuration_header_reference'}
    C.need(set(configurations) == expected and all(pathlib.Path(ref['path']).parent == directory
           for ref in configurations.values()), 'ALL_FIVE_CLOSED_CONFIGURATION_COMPONENTS')
    values = {k: D.read(ref, [*roots, d3plan['output_directory']]) for k, ref in configurations.items()}
    header = values['configuration_header_reference']
    C.need(header['schema'] == 'ACTUAL_CPU_BOUNDED_D2_D3_CONFIGURATIONS_V1' and
           header['actual_D4_acceptance_reference'] == plan['pilot_acceptance_reference'] and
           header['configuration_build_review_reference'] == C.meta(plan['bounded_export_review_reference'])['configuration_build_review_reference'] and
           all(header[k] == configurations[k] for k in expected - {'configuration_header_reference'}),
           'EXACT_CLOSED_D3_CONFIGURATION_HEADER_CURRENT_CPU_HASHES')
    rho_ref = marker['actual_original_series_size_rho_reference']
    C.need(rho_ref is not None, 'REAL_REQUIRED_SIZE_RHO_NO_DUPLICATE_REFIT_OR_GUESSED_FAMILY')
    rho = D.read(rho_ref, [*roots, d3plan['output_directory']], 64 << 20)
    C.need(rho['fit_population_reference'] == accepted['component_references']['population_reference'] and
           rho['statistics_reference'] == accepted['component_references']['numeric_repetitions'][0] and
           rho['threshold_abs_rho'] == .95 and rho['required_scalar_fields'] == 69 and
           str(rho['actual_D3_job_id']) == str(marker['actual_D3_job_id']),
           'EXACT_ORIGINAL_69_SCALAR_RHO_FROM_SHARED_ACTUAL_D3_CPU')
    bound = I.save(root / 'shared_configuration_component_acceptance.json', dict(
        schema='D5_ACTUAL_EARLY_CLOSED_D3_CONFIGURATION_ACCEPTANCE_V1',
        status='CPU_CURRENT_HASHED_COMPONENTS_ONLY_NOT_D3_PAYLOAD_OR_C0',
        actual_closed_configuration_marker_reference=rr, actual_D3_plan_reference=plan['shared_D3_plan_reference'],
        actual_D3_job_id=str(marker['actual_D3_job_id']), actual_configuration_references=configurations,
        actual_original_series_size_rho_reference=rho_ref, all_current_CPU_file_hashes_verified=True,
        D3_payload_C0_required=False, new_rho_fit=False, Model_ACK=False))
    return configurations, values, bound
