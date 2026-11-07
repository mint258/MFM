"""Compose all11 sources only from actual closed original evidence and adoption.

This is metadata composition, not physical all-source indexing or pool release.
Old READY9, MolNet21 and COCONUT735 artifacts remain unmodified.
"""
import argparse
import copy
import json
from pathlib import Path
from .run import file_reference
from .kernel import require
from ..decontamination import REQUIRED

MANIFEST = 'expansion_decontamination_sources_with_constraints_v3'


def read_ref(ref):
    require(isinstance(ref, dict) and {'path', 'bytes', 'sha256'} <= set(ref), 'Physical reference required')
    observed = file_reference(ref['path'])
    require(all(observed[k] == ref[k] for k in ('bytes', 'sha256')), 'Metadata source pin mismatch: ' + ref['path'])
    return json.loads(Path(ref['path']).read_text(encoding='utf-8'))


def compose(ready9, molnet_acceptance_ref, coconut_acceptance_ref):
    sources = copy.deepcopy(ready9['sources'])
    require(len(sources) == 11 and {s['dataset'] for s in sources} == REQUIRED, 'Exact original all11 source domains required')
    by_name = {s['dataset']: s for s in sources}
    require(all(s['status'] == 'READY' for s in sources if s['dataset'] not in ('moleculenet', 'coconut')),
            'All nine original ready sources required')
    mol_accept = read_ref(molnet_acceptance_ref)
    require(mol_accept['schema'] == 'ROOT_MOLNET21_ACTUAL_CONSERVATIVE_COVERAGE_ACCEPTANCE_V1' and
            mol_accept['status'] == 'APPROVED_FOR_CLOSED21_CONSERVATIVE_EXCLUSION_V2' and
            mol_accept['reviewer'] == 'root' and mol_accept['original_identity_unknowns_and_all_physical_rows_retained'] is True,
            'Existing actual MolNet Root adoption required')
    mol_receipt = read_ref(mol_accept['receipt_reference'])
    mol = mol_receipt['result']
    require(mol['remaining_exclusion_HOLD'] == 0 and mol['cases'] == 21 and
            mol['complete_exclusion_coverage_candidate'] is True and mol['original_graph_statuses_modified'] is False,
            'Original complete21 conservative evidence required')
    by_name['moleculenet'].update(status='READY_FOR_CONSERVATIVE_EXCLUSION_V3',
        version='original_MolNet17_all21_conservative_coverage_v3', required_roles=['all'],
        raw_artifacts=mol['raw_artifacts'], coverage_evidence=mol['report_reference'],
        identity_parts=[mol['base_strict5_reference'], mol['overlay_reference']],
        lower_bounds=mol['lower_bound_reference'], physical_dispositions=mol['physical_dispositions_reference'],
        acceptance=molnet_acceptance_ref)
    coconut_accept = read_ref(coconut_acceptance_ref)
    require(coconut_accept['schema'] == 'ROOT_COCONUT735_ACTUAL_CONSERVATIVE_COVERAGE_ACCEPTANCE_V1' and
            coconut_accept['status'] == 'APPROVED_FOR_CLOSED735_CONSERVATIVE_EXCLUSION_V3' and
            coconut_accept['reviewer'] == 'root' and
            all(coconut_accept[k] is True for k in ('original_unknowns_retained', 'all_original735_rows_exclusion_covered',
                'no_source_records_dropped', 'no_guessed_keys', 'veto_impact_measured_on_complete_candidate_pool')),
            'Complete actual735 adoption and full-pool veto-impact evidence required')
    closed = read_ref(coconut_accept['coverage_reference'])
    require(closed['schema'] == 'COCONUT735_ACCEPTED_EXCLUSION_COVERAGE_V1' and
            closed['physical_unknown_rows'] == 735 and closed['remaining_exclusion_HOLD'] == 0 and
            closed['all_physical_source_rows_retained'] is True and
            closed['original_graph_identities_repaired'] is False,
            'No manifest-only or partial735 source closure')
    impact = read_ref(coconut_accept['veto_impact_reference'])
    require(impact['complete_candidate_pool'] is True and impact['input_unique_molecules'] > 0 and
            impact['eligible_after_all_exclusions'] > 0 and impact['no_universal_or_empty_bound'] is True,
            'No degenerate whole-pool exclusion or unmeasured conservative veto')
    by_name['coconut'].update(status='READY_FOR_CONSERVATIVE_EXCLUSION_V3',
        version=closed['source_version'], required_roles=closed['required_roles'],
        required_subdatasets=closed['required_subdatasets'], raw_artifacts=closed['raw_artifacts'],
        coverage_evidence=coconut_accept['coverage_reference'], identity_parts=closed['identity_parts'],
        lower_bounds=closed['lower_bounds'], physical_dispositions=closed['physical_dispositions'],
        acceptance=coconut_acceptance_ref)
    return dict(schema=MANIFEST, version='0.3.0',
        status='ALL11_SOURCE_EVIDENCE_COMPOSED_PENDING_ACTUAL_INDEX_AND_FILTER', sources=sources,
        identity_policy=copy.deepcopy(ready9['identity_policy']),
        candidate_domain_authority=copy.deepcopy(mol['candidate_domain_authority']),
        root_molnet21_acceptance_reference=molnet_acceptance_ref,
        root_coconut735_acceptance_reference=coconut_acceptance_ref,
        original_graph_unknowns_retained=True, ranking_uses_downstream_features=False,
        all_sources_actually_indexed=False, filtered_candidate_pool_released=False,
        source_manifest_is_not_a_pool_release=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ready9', required=True)
    p.add_argument('--molnet-acceptance', required=True)
    p.add_argument('--coconut-acceptance', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    result = compose(json.loads(Path(a.ready9).read_text(encoding='utf-8')),
                     file_reference(a.molnet_acceptance), file_reference(a.coconut_acceptance))
    result['prior_manifest_reference'] = file_reference(a.ready9)
    with Path(a.output).open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps(file_reference(a.output), sort_keys=True))


if __name__ == '__main__':
    main()
