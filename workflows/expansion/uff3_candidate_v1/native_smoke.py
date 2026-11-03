"""Small actual-coordinate UFF3 parity and append fixture; never PubChem data.

Root runs this in its real RDKit2025.09.5 environment on a compute node. The
fourth-conformer extension is an explicit synthetic fixture, not production.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import socket
import time
from . import core as C, store as S
from .native import NativeKernel


def run(output):
    if socket.gethostname().split('.')[0]!='compute-0-20' and not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('NATIVE_FIXTURE_REQUIRES_COMPUTE20_OR_ACTUAL_SLURM_ALLOCATION')
    from rdkit import Chem, rdBase
    if rdBase.rdkitVersion != '2025.09.5':
        raise RuntimeError('EXACT_RDKit2025_09_5_REQUIRED')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    reports = []
    family_items = []
    began = time.monotonic()
    for i, smiles in enumerate(('CC', 'CCCCCCCCCC'), 1):
        mol = Chem.MolFromSmiles(smiles)
        source = {'pubchem_version': 'SYNTHETIC_SMOKE_NOT_PUBCHEM_RELEASE',
                  'cid': i, 'full_key': Chem.MolToInchiKey(mol),
                  'source_smiles': smiles,
                  'isomeric_smiles': Chem.MolToSmiles(mol, isomericSmiles=True),
                  'stream': 'R' if i == 1 else 'N', 'stream_rank': 1}
        kernel = NativeKernel()
        manifest = S.run_one(source, output / ('molecule' + str(i)), kernel=kernel)
        cache = S.read_json(manifest['candidate_cache']['path'])
        packet = S.read_json(manifest['selected_packet']['path'])
        if len(packet['conformers']) > 3:
            raise RuntimeError('MORE_THAN_THREE_INITIAL_EXPORTS')
        checks = [kernel.compare_original_wire(row, cache['D20']) for row in packet['conformers']]
        if not checks:
            raise RuntimeError('NO_REAL_COORDINATES_FOR_ORIGINAL_D3_PARITY')
        export_packet = dict(packet)
        export_packet['producer_job_id'] = os.environ.get('SLURM_JOB_ID', '0')
        export_packet['once_key'] = C.sha(C.canonical([C.recipe_sha(), C.source_identity(source)]))
        export_packet['error'] = cache.get('error')
        family_items.append((manifest['selected_packet'], export_packet))
        report = {'fixture_smiles': smiles, 'real_selected_conformers': len(packet['conformers']),
                  'internal_candidates_optimized_once': cache['optimizer_calls'],
                  'embedding_calls': cache['embedding_calls'],
                  'available_unique_in_cache': len(cache['canonical_candidates']),
                  'actual_original_wire_binary64_checks': checks,
                  'manifest': S.reference(output / ('molecule' + str(i)) / 'manifest.json')}
        if i == 2:
            if len(cache['canonical_candidates']) < 4:
                raise RuntimeError('EXTENSION_FIXTURE_HAS_FEWER_THAN_FOUR_REAL_SURVIVORS')
            old = C.canonical(packet['conformers'])
            # The fixture proves cache-only extension; fail immediately on an
            # accidental new embedding/optimizer or graph-D20 preparation call.
            def forbidden(*args, **kwargs):
                raise AssertionError('EXTENSION_REPEATED_NATIVE_OR_D20')
            kernel.prepare = kernel.embed = kernel.optimize = forbidden
            extended = S.run_one(source, output / 'explicit_fixture_extension4', kernel=kernel,
                prior_cache_path=manifest['candidate_cache']['path'],
                previous_packet_path=manifest['selected_packet']['path'],
                export_limit=4, allow_future_extension=True)
            extended_packet = S.read_json(extended['selected_packet']['path'])
            if len(extended_packet['conformers']) != 4 or C.canonical(extended_packet['conformers'][:3]) != old:
                raise RuntimeError('REAL_EXTENSION_PREFIX_NOT_PRESERVED')
            row = extended_packet['conformers'][3]
            kernel.compare_original_wire(row, cache['D20'])
            if any(kernel.distance(row, prior) < .5 for prior in extended_packet['conformers'][:3]):
                raise RuntimeError('EXTENSION_FAILED_DEDUP_VS_SAVED')
            report['real_three_to_four_fixture_prefix_preserved'] = True
            report['fourth_deduplicated_against_all_saved'] = True
            report['extension_performed_new_embedding_or_UFF'] = False
        reports.append(report)
    from . import families
    import pyarrow as pa
    import pyarrow.parquet as pq
    class FixtureBudget:
        def check(self, *args):
            return None
    family_directory = output / 'original_float64_family_writer_fixture'
    family_directory.mkdir()
    family_files = families.export_packets(family_items, family_directory,
        FixtureBudget(), os.environ.get('SLURM_JOB_ID', '0'))
    counts = {ref['family']: pq.ParquetFile(ref['path']).metadata.num_rows for ref in family_files}
    selected = sum(report['real_selected_conformers'] for report in reports)
    if counts != {'D20': 2, 'D3': selected, 'geometry': selected, 'source_status': 2}:
        raise RuntimeError('FAMILY_COUNTS_MUST_EXPORT_REAL_UP_TO_THREE_NOT_THIRTY_CANDIDATES')
    schema = pq.read_schema(family_directory / 'D3.parquet')
    for field in ('PMI1', 'PMI2', 'PMI3', 'PBF_A', 'volume_A3', 'SASA_total_A2'):
        if schema.field(field).type != pa.float64():
            raise RuntimeError('ORIGINAL_D3_FLOAT64_FAMILY_SCHEMA_CHANGED:' + field)
    result = {'schema': 'PUBCHEM_UFF3_REAL_NATIVE_SMOKE_V1', 'status': 'PASS',
              'fixtures_only_no_candidate_release': True, 'production_export_limit': 3,
              'elapsed_seconds': time.monotonic() - began, 'fixtures': reports,
              'actual_family_rows': counts, 'actual_original_float64_family_files': family_files,
              'job_zero_if_present_means_unallocated_synthetic_fixture_not_Slurm': True,
              'new_PM7_xTB_Pprime_calls': 0}
    S.write_new(output / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
