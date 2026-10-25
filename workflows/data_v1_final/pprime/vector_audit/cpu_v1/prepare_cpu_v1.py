"""Prepare isolated coordinate-frame controls; never invoke a QM program."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).absolute().parents[2]))
sys.path.insert(0, str(Path(__file__).absolute().parents[1]))
from common import (canonical, digest, load_config, load_engine, new_output, output_guard,
                    reference, require_pin, write_json)
import threading
from workflows.data_v1_final.execution.cpu_analysis_v1 import runtime as cpu_runtime
from runtime_control import (checkpoint_iter, cpu_observed, load_runconfig,
                             prepared_authority, source_lineage)
from geometry import adapt_native
from math_v1 import ROTATION, checked_rotation, rotation_case


def load_audit(path):
    c = json.loads(Path(path).read_text())
    if c['schema'] != 'PPRIME_VECTOR_FRAME_AUDIT_V1' or c['maximum_molecules'] != 4 or c['minimum_molecules'] != 2:
        raise ValueError('FROZEN_TWO_TO_FOUR_MOLECULE_AUDIT_REQUIRED')
    if c['rotation_matrix'] != ROTATION or c['production_membership'] is not False:
        raise ValueError('AUDIT_ROTATION_OR_ISOLATION_CHANGED')
    checked_rotation(c['rotation_matrix'])
    for pin in c['parent_source_pins']:
        require_pin(pin)
    return c


def choose_pairs(pairs, maximum_atoms):
    """Use only already-validated pairs; missing chemistry strata stay explicit."""
    from rdkit import Chem
    first = {}
    for pair in pairs:
        if pair['random_order_rank'] == 0:
            first[pair['molecule_id']] = pair
    buckets = {'hydrocarbon': [], 'CNO': [], 'P_S_Si': [], 'Se': [], 'other_supported': []}
    for mid, pair in checkpoint_iter(sorted(first.items())):
        source = pair['source']
        if not 6 <= int(source['total_atoms']) <= maximum_atoms:
            continue
        mol = Chem.MolFromSmiles(source['smiles'])
        if mol is None or Chem.GetFormalCharge(mol) != 0:
            continue
        z = {atom.GetAtomicNum() for atom in mol.GetAtoms()}
        if z <= {1, 6}:
            bucket = 'hydrocarbon'
        elif 34 in z:
            bucket = 'Se'
        elif z & {14, 15, 16}:
            bucket = 'P_S_Si'
        elif z <= {1, 6, 7, 8}:
            bucket = 'CNO'
        else:
            bucket = 'other_supported'
        buckets[bucket].append(pair)
    chosen = [values[0] for values in buckets.values() if values]
    used = {p['molecule_id'] for p in chosen}
    for pair in sorted((p for values in buckets.values() for p in values), key=lambda p: p['molecule_id']):
        if len(chosen) >= 4:
            break
        if pair['molecule_id'] not in used:
            chosen.append(pair)
            used.add(pair['molecule_id'])
    if len(chosen) < 2:
        raise ValueError('FEWER_THAN_TWO_SMALL_VALIDATED_SOURCE_MOLECULES')
    return chosen[:4], {key: len(value) for key, value in buckets.items()}


def make_cases(native, source, molecule_id, geometry_source, protocol, starting_id=0,
               translation_A=(0.317, -0.419, 0.233)):
    """Four task conditions: B, SP(clean), gradient(noisy), SP(same noisy geometry)."""
    tasks = {t['name']: t for t in protocol['tasks']}
    rid = f'vector-audit:{molecule_id}:{geometry_source}'
    conditions = [('pm7_B', 'pm7_B', False), ('xtb_singlepoint', 'xtb_singlepoint', False),
                  ('xtb_perturbed_gradient', 'xtb_perturbed_gradient', False),
                  ('xtb_singlepoint_noisy_companion', 'xtb_singlepoint', True)]
    cases = []
    for condition, task_name, companion in checkpoint_iter(conditions):
        for arm in checkpoint_iter(('base', 'rotated')):
            transform = rotation_case(native['coords'], rid, tasks[task_name], protocol,
                                      arm, noisy_companion=companion)
            row = dict(source, record_id=rid + (':noisy-companion' if companion else ''))
            cases.append({'case_id': f'case-{starting_id+len(cases):03d}', 'molecule_id': molecule_id,
                          'geometry_source': geometry_source, 'condition': condition,
                          'calc_type': task_name, 'arm': arm, 'row': row,
                          'source_record': source, 'symbols': list(native['symbols']),
                          'atomic_numbers': native['z'].tolist(), 'pairs': [list(p) for p in native['pairs']],
                          'native_atom_order_sha256': native['native_atom_order_sha256'],
                          'source_clean_coordinates_A': native['coords'].tolist(),
                          **transform})
    cpu_runtime.checkpoint()
    import numpy as np
    coordinates = np.asarray(native['coords'])+np.asarray(translation_A)
    cases.append({'case_id': f'case-{starting_id+len(cases):03d}', 'molecule_id': molecule_id,
                  'geometry_source': geometry_source, 'condition': 'xtb_singlepoint_origin_translation',
                  'calc_type': 'xtb_singlepoint', 'arm': 'translated', 'row': dict(source, record_id=rid),
                  'source_record': source, 'symbols': list(native['symbols']),
                  'atomic_numbers': native['z'].tolist(), 'pairs': [list(p) for p in native['pairs']],
                  'native_atom_order_sha256': native['native_atom_order_sha256'],
                  'source_clean_coordinates_A': native['coords'].tolist(),
                  'native_coordinates_A': coordinates.tolist(),
                  'expected_actual_coordinates_A': coordinates.tolist(),
                  'translation_A': list(translation_A), 'production_membership': False})
    return cases


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--cpu-runconfig', type=Path, required=True)
    p.add_argument('--pilot-config', type=Path, required=True)
    p.add_argument('--prepared-pprime', type=Path, required=True)
    p.add_argument('--prepared-pprime-sha256', required=True)
    p.add_argument('--root-preflight', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    c, pilot = load_audit(args.config), load_config(args.pilot_config)
    cpu = load_runconfig(args.cpu_runconfig, args.config, args.pilot_config, args.prepared_pprime)
    observed, preflight = cpu_observed(args.root_preflight, args.cpu_runconfig, args.config, c, cpu)
    require_pin(c['pilot_config'])
    if reference(args.pilot_config) != c['pilot_config']:
        raise ValueError('REGISTERED_PILOT_CONFIG_REQUIRED')
    source_manifest = args.prepared_pprime / 'prepared.json'
    if digest(source_manifest) != args.prepared_pprime_sha256:
        raise ValueError('PREPARED_PPRIME_MANIFEST_SHA_CHANGED')
    saved = json.loads(source_manifest.read_text())
    if saved['status'] != 'PPRIME_PAIRS_READY_NOT_QM_EXECUTED':
        raise ValueError('CLOSED_PREPARED_PPRIME_INPUTS_REQUIRED')
    prepared_authority(saved, source_manifest, args.prepared_pprime_sha256, cpu, args.root_preflight)
    for pin in checkpoint_iter(saved['outputs']):
        require_pin(pin)
    cpu_runtime.checkpoint()
    pairs = [json.loads(line) for line in (args.prepared_pprime / 'pairs.jsonl').read_text().splitlines()]
    chosen, strata = choose_pairs(pairs, c['maximum_atoms'])
    out = new_output(args.output, c)
    import pyarrow as pa
    import pyarrow.parquet as pq
    import numpy as np
    e, contract, protocol = load_engine(pilot)
    audit_rows = []
    for pair in checkpoint_iter(chosen):
        for geom in ('pm7', 'uff_sprime'):
            rid = f'vector-audit:{pair["molecule_id"]}:{geom}'
            for record_id in (rid, rid+':noisy-companion'):
                audit_rows.append({'record_id': record_id, 'file_group': int(pair['source']['file_group']),
                                   'size_stratum': pair['source']['size_stratum']})
    pq.write_table(pa.Table.from_pylist(audit_rows), out / 'audit_selected.parquet', compression='zstd')
    audit_ref = dict(reference(out / 'audit_selected.parquet'), rows=len(audit_rows))
    write_json(out / 'audit_membership.json', {'schema': 'WP5_STRATIFIED_RECORD_AUDIT_V1',
               'status': 'AUDIT_MEMBERSHIP_CLOSED', 'selected_records': audit_ref,
               'audit_fraction': 1.0, 'scope': 'isolated vector-frame controls only; not formal P-prime membership'})
    cases = []
    scratch = Path(tempfile.mkdtemp(prefix='pva_prepare_', dir='/tmp'))
    try:
        e.initialize_worker(pilot['source_plan']['path'], protocol=contract['protocol']['path'],
                            node_scratch_root=str(scratch), audit_membership=str(out/'audit_membership.json'),
                            reproduction_package=contract['reproduction_package']['path'])
        for pair in checkpoint_iter(chosen):
            source = dict(pair['source'])
            original = e.NATIVE.read_native(source)
            graph = e.source_bond_graph(original['_source_raw'], original)
            uff, _ = adapt_native(original, dict(pair, bond_pairs=graph['bond_pairs_zero_based']))
            for geometry, native in checkpoint_iter((('pm7', original), ('uff_sprime', uff))):
                cases.extend(make_cases(native, source, pair['molecule_id'], geometry, protocol,
                                        len(cases), c['origin_translation_A']))
        (out / 'inputs').mkdir()
        render_barrier = threading.Barrier(16)
        render_state = threading.local()
        def render(case):
            cpu_runtime.checkpoint()
            if not getattr(render_state, 'seen', False):
                render_state.seen = True
                render_barrier.wait(timeout=180)
            native = {'symbols': case['symbols'], 'coords': np.asarray(case['native_coordinates_A'])}
            task = next(t for t in protocol['tasks'] if t['name'] == case['calc_type'])
            rendered = e.render_inputs(task, native, case['row'], protocol)
            actual = np.asarray([[float(v) for v in line.split()[1:]]
                                 for line in rendered['input.xyz'].decode().splitlines()[2:]])
            error = float(np.max(np.abs(actual-np.asarray(case['expected_actual_coordinates_A']))))
            if error > c['rendered_coordinate_atol_A']:
                raise ValueError('AUDIT_RENDERED_INPUT_NOT_REQUESTED_ROTATION')
            folder = out / 'inputs' / case['case_id']
            folder.mkdir()
            refs = []
            for name, body in checkpoint_iter(rendered.items()):
                with (folder / name).open('xb') as stream:
                    stream.write(body); stream.flush(); os.fsync(stream.fileno())
                refs.append(reference(folder/name))
            return dict(case, input_files=refs, actual_rendered_coordinates_A=actual.tolist(),
                        serialization_max_error_A=error, render_worker_pid=os.getpid(),
                        render_worker_tid=threading.get_native_id())
        with ThreadPoolExecutor(max_workers=16) as workers:
            cases = list(checkpoint_iter(workers.map(render, cases)))
        case_ref = write_json(out / 'cases.json', cases)
        write_json(out / 'prepared.json', {'status': 'VECTOR_AUDIT_INPUTS_PREPARED_QM_NOT_STARTED',
                   'runtime': observed, 'config': reference(args.config), 'pilot_config': reference(args.pilot_config),
                   'cpu_runconfig': reference(args.cpu_runconfig),
                   'execution_variant': 'CPU_PARTITION_READONLY_VECTOR_PREPARATION_V1',
                   'actual_render_worker_tids': sorted({row['render_worker_tid'] for row in cases}),
                   'pprime_prepared': reference(source_manifest), 'root_preflight': preflight,
                   'molecules': len(chosen), 'geometry_instances': 2*len(chosen), 'QM_calls_prepared': len(cases),
                   'chemistry_candidate_strata': strata, 'cases': case_ref,
                   'audit_membership': reference(out/'audit_membership.json'),
                   'selected_source_pairs': [{'molecule_id': p['molecule_id'], 'source_record': p['source'],
                                              'sprime_conf_idx': p['conformer']['sprime_conf_idx'],
                                              **source_lineage(p['source'])} for p in chosen],
                   'official_source_references': c['official_source_references'],
                   'production_membership': False, 'QM_started': False,
                   'output_bytes_before_manifest': output_guard(out, c, reserve=1 << 20)})
    finally:
        closed = e.close_worker()
        write_json(out / 'prepare_reader_closed.json', closed)
        if scratch.exists() and not any(scratch.iterdir()):
            scratch.rmdir()
    print(json.dumps({'status': 'VECTOR_AUDIT_INPUTS_PREPARED_QM_NOT_STARTED', 'cases': len(cases)}))


if __name__ == '__main__':
    main()
