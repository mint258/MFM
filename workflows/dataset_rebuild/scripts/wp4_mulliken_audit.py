#!/usr/bin/env python3
"""Read-only numerical Mulliken audit of existing WP4 synthetic output files.

No MOPAC, xTB, LMDB, optimization, or new SCF is invoked. Dense working arrays
remain in worker memory; only charge checks and diagnostic atom-pair overlap
populations are written. Frozen wp4_parsers.py is imported without bytecode.
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import datetime as dt
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
DEFAULT_INPUT = ROOT / 'wp4_capability/job_4512796'
for thread_variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[thread_variable] = '1'

# Exact six-element parameters used by the sixteen existing synthetic cases.
# Source: official v23.0.3 src/models/parameters_for_PM7_C.F90 data beta{s,p,d}7.
# These values reconstruct the MULLIK overlap from exported AUX overlap. They
# never create or save a Hamiltonian or density label.
PM7_BETA = {
    'H': (-8.389745, None, None),
    'C': (-14.414930, -7.893717, None),
    'N': (-22.110958, -15.464433, None),
    'O': (-67.776339, -20.267981, None),
    'Si': (-10.755885, -3.922152, -4.736877),
    'S': (-11.422550, -7.191896, -10.695329),
}
SOURCE_URLS = {
    'mullik': 'https://raw.githubusercontent.com/openmopac/mopac/v23.0.3/src/properties/mullik.F90',
    'aux_export': 'https://raw.githubusercontent.com/openmopac/mopac/v23.0.3/src/output/to_screen.F90',
    'mo_transform': 'https://raw.githubusercontent.com/openmopac/mopac/v23.0.3/src/matrix/mult.F90',
    'printed_population': 'https://raw.githubusercontent.com/openmopac/mopac/v23.0.3/src/properties/mpcsyb.F90',
    'parameters': 'https://raw.githubusercontent.com/openmopac/mopac/v23.0.3/src/models/parameters_for_PM7_C.F90',
    'graph_output_manual': 'https://openmopac.net/Manual/graph.html',
    'aux_precision_manual': 'https://openmopac.net/Manual/auxiliary.html',
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path: Path) -> dict:
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha256(path)}


def dump(path: Path, value: object) -> None:
    pending = path.with_name(path.name + '.pending')
    pending.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
                       + '\n', encoding='utf-8')
    pending.replace(path)


def beta_arrays(symbols, mapping, types):
    import numpy as np
    actual = []
    legacy = []
    d_orbitals = []
    for ao, (atom_index, orbital_type) in enumerate(zip(mapping, types)):
        atom_index = int(atom_index) - 1
        symbol = symbols[atom_index]
        if symbol not in PM7_BETA:
            raise ValueError('No bound official PM7 beta parameters for ' + symbol)
        bs, bp, bd = PM7_BETA[symbol]
        typ = str(orbital_type).strip().upper()
        if typ == 'S':
            actual.append(bs)
            legacy.append(bs)
        elif typ in ('PX', 'PY', 'PZ'):
            actual.append(bp)
            legacy.append(bp)
        else:
            if bd is None:
                raise ValueError('Unexpected d AO without an official beta_d: ' + symbol + '/' + typ)
            actual.append(bd)
            legacy.append(bp)
            d_orbitals.append({'AO_index_0based': ao, 'atom_index_0based': atom_index,
                               'element': symbol, 'AO_type': typ, 'beta_d_eV': bd,
                               'legacy_MULLIK_beta_p_eV': bp})
    return np.asarray(actual), np.asarray(legacy), d_orbitals


def inverse_root(matrix):
    import numpy as np
    values, vectors = np.linalg.eigh(matrix)
    if np.min(np.abs(values)) < 1e-10:
        raise ValueError('Near-zero overlap eigenvalue; no stable diagnostic reconstruction.')
    # v23.0.3 mullik.F90 intentionally uses sqrt(abs(eig)), not sqrt(eig).
    work = (vectors / np.sqrt(np.abs(values))) @ vectors.T
    return work, {'minimum_eigenvalue': float(values.min()),
                  'minimum_absolute_eigenvalue': float(np.abs(values).min()),
                  'negative_eigenvalues': int((values < 0).sum()),
                  'condition_absolute_eigenvalues': float(np.abs(values).max() / np.abs(values).min())}


def population_checks(density, overlap, mapping, core, reference):
    import numpy as np
    work, spectrum = inverse_root(overlap)
    back_density = work @ density @ work.T
    population = back_density * overlap
    atom_population = np.asarray([population[mapping == atom + 1, :].sum()
                                  for atom in range(len(core))])
    charges = core - atom_population
    pairs = [{'i': i, 'j': j,
              'overlap_population_e': float(2 * population[np.ix_(mapping == i + 1, mapping == j + 1)].sum())}
             for i in range(len(core)) for j in range(i)]
    return {'spectrum': spectrum, 'charges_e': charges.tolist(),
            'charge_sum_e': float(charges.sum()),
            'maximum_charge_error_vs_printed_e': float(np.max(np.abs(charges - reference))) if reference is not None else None,
            'atom_pair_overlap_population_e': pairs}


def audit_case(task):
    import numpy as np
    # Import only read-only numerical helpers; no CLI/function invokes QM.
    from wp4_parsers import read_aux, triangle, indexed_table
    directory = Path(task['path'])
    before = [ref(directory / 'input.aux'), ref(directory / 'input.out')]
    aux, aux_errors = read_aux(directory / 'input.aux')
    text = (directory / 'input.out').read_text(errors='replace')
    symbols = aux.get('ATOM_EL', [])
    mapping = np.asarray(aux.get('AO_ATOMINDEX', []), dtype=int)
    types = aux.get('ATOM_SYMTYPE', [])
    n = len(mapping)
    core = np.asarray(aux.get('ATOM_CORE', []), dtype=float)
    result = {'molecule': task['molecule'], 'task': task['task'], 'input_path': str(directory),
              'PID': os.getpid(), 'input_files': before, 'parse_errors': aux_errors,
              'AO_count': n, 'atom_count': len(symbols), 'MOPAC_VERSION': aux.get('MOPAC_VERSION'),
              'METHOD': aux.get('METHOD'), 'keywords': aux.get('KEYWORDS'),
              'new_QM_calls': 0, 'Hamiltonian_or_density_labels_saved': False}
    if str(aux.get('METHOD')).upper() != 'PM7' or str(aux.get('MOPAC_VERSION')) != '23.0.3':
        raise ValueError('This diagnostic binds the existing PM7/v23.0.3 output model only.')
    if not n or len(types) != n or len(core) != len(symbols):
        raise ValueError('AO/atom mapping dimensions differ.')
    overlap = triangle(aux.get('OVERLAP_MATRIX'), n)
    density = triangle(aux.get('TOTAL_DENSITY_MATRIX'), n)
    if overlap is None or density is None:
        raise ValueError('Full AUX overlap and Coulson density are required for this read-only diagnostic.')
    printed = indexed_table(text, r'MULLIKEN POPULATIONS AND CHARGES', symbols, 2)
    reference = np.asarray([row[1] for row in printed]) if printed else None
    aux_charges = aux.get('MULLIKEN_ATOM_CHARGES')
    result['printed_mulliken_charges_e'] = reference.tolist() if reference is not None else None
    result['AUX_MULLIKEN_ATOM_CHARGES_e'] = aux_charges
    result['AUX_vs_printed_Mulliken_max_error_e'] = float(np.max(np.abs(np.asarray(aux_charges) - reference))) if aux_charges and reference is not None else None
    result['AUX_density_trace_e'] = float(np.trace(density))
    result['declared_total_electrons'] = aux.get('NUM_ELECTRONS')
    ao_population = aux.get('AO_CHARGES')
    result['density_diagonal_vs_AO_population_max_error_e'] = float(np.max(np.abs(np.diag(density) - ao_population))) if ao_population else None
    actual_beta, old_beta, d_orbitals = beta_arrays(symbols, mapping, types)
    native_sum = actual_beta[:, None] + actual_beta[None, :]
    legacy_sum = old_beta[:, None] + old_beta[None, :]
    ratio = native_sum / legacy_sum
    legacy_overlap = overlap.copy()
    inter_atom = mapping[:, None] != mapping[None, :]
    legacy_overlap[inter_atom] = overlap[inter_atom] * ratio[inter_atom] + 1e-14
    # Within-atom blocks are zero off-diagonal and one diagonal in both sources.
    np.fill_diagonal(legacy_overlap, 1.0)
    result['d_orbitals'] = d_orbitals
    result['AUX_to_v23_MULLIK_overlap_max_change'] = float(np.max(np.abs(overlap - legacy_overlap)))
    result['from_AUX_full_density'] = {
        'AUX_overlap': population_checks(density, overlap, mapping, core, reference),
        'v23_MULLIK_beta_p_for_d_overlap': population_checks(density, legacy_overlap, mapping, core, reference),
    }
    occupancies = np.asarray(aux.get('MOLECULAR_ORBITAL_OCCUPANCIES', []), dtype=float)
    coefficients = aux.get('EIGENVECTORS', [])
    mo_set = aux.get('SET_OF_MOS')
    result['MO_count_exported'] = int(len(occupancies))
    result['SET_OF_MOS'] = mo_set
    result['exported_occupancy_sum_e'] = float(occupancies.sum())
    result['all_occupied_MOs_exported'] = abs(occupancies.sum() - float(aux['NUM_ELECTRONS'])) < 1e-5
    result['frozen_parser_nao_equals_len_occupancies'] = n == len(occupancies)
    if len(coefficients) == n * len(occupancies):
        c = np.asarray(coefficients).reshape((n, len(occupancies)), order='F')
        eigen_density = (c * occupancies) @ c.T
        result['MO_coefficient_layout'] = 'Fortran columns: c(AO,MO); flat AUX coefficients reshape(nAO,nMO,order=F).'
        result['MO_orthonormality_max_error'] = float(np.max(np.abs(c.T @ c - np.eye(len(occupancies)))))
        result['density_from_MOs_vs_AUX_density_max_error'] = float(np.max(np.abs(eigen_density - density)))
        result['from_exported_MOs'] = {
            'AUX_overlap': population_checks(eigen_density, overlap, mapping, core, reference),
            'v23_MULLIK_beta_p_for_d_overlap': population_checks(eigen_density, legacy_overlap, mapping, core, reference),
        }
        if len(occupancies) == n:
            wrong_c = np.asarray(coefficients).reshape((n, n), order='C')
            result['wrong_MO_orientation_charge_error_e'] = population_checks(
                (wrong_c * occupancies) @ wrong_c.T, legacy_overlap, mapping, core, reference
            )['maximum_charge_error_vs_printed_e']
    result['source_unchanged'] = [ref(directory / 'input.aux'), ref(directory / 'input.out')] == before
    if not result['source_unchanged']:
        raise RuntimeError('An existing output changed during its read-only audit.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--workers', type=int, default=16)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not 16 <= args.workers <= int(os.environ.get('SLURM_CPUS_PER_TASK', 0)):
        raise RuntimeError('A Slurm allocation with >=16 effectively parallel workers is required.')
    destination = args.out or ROOT / 'reports' / ('mulliken_audit_job_' + os.environ['SLURM_JOB_ID'])
    destination.mkdir(parents=True, exist_ok=False)
    bound_parser = Path(__file__).parent / 'wp4_parsers.py'
    frozen_parser = ref(bound_parser)
    tasks = [{'molecule': molecule.name, 'task': task, 'path': str(molecule / task)}
             for molecule in sorted(args.input_root.iterdir()) if molecule.is_dir()
             for task in ('pm7_B', 'pm7_B_large')
             if (molecule / task / 'input.aux').exists() and (molecule / task / 'input.out').exists()]
    if len(tasks) < args.workers:
        raise RuntimeError('Not enough existing read-only cases to use the requested workers.')
    started = time.monotonic()
    results, errors = [], []
    with futures.ProcessPoolExecutor(max_workers=args.workers, mp_context=mp.get_context('spawn')) as pool:
        running = {pool.submit(audit_case, task): task for task in tasks}
        for future in futures.as_completed(running):
            task = running[future]
            try:
                results.append(future.result())
            except Exception as exc:
                errors.append({'task': task, 'error': type(exc).__name__ + ': ' + str(exc)})
    results.sort(key=lambda row: (row['molecule'], row['task']))
    if ref(bound_parser) != frozen_parser:
        raise RuntimeError('Frozen numerical parser changed during the audit.')
    report = {'scope': 'READ_ONLY_EXISTING_16_SYNTHETIC_CASES_NOT_WP4_RETAINED_SAMPLE',
              'created_UTC': dt.datetime.now(dt.timezone.utc).isoformat(),
              'job_id': os.environ['SLURM_JOB_ID'], 'workers': args.workers,
              'actual_worker_PIDs': sorted({row['PID'] for row in results}),
              'elapsed_seconds': time.monotonic() - started,
              'tasks': len(tasks), 'completed': len(results), 'errors': errors,
              'script': ref(Path(__file__)), 'frozen_parser': frozen_parser,
              'official_source_URLs': SOURCE_URLS,
              'existing_local_reference_sources': [ref(path) for path in sorted((ROOT / 'software/mopac_reference').glob('v23.0.3_*.F90'))],
              'source_findings': {
                  's_p_overlap': 'AUX fill_overlap_matrix divides H by half the beta sum, while MULLIK divides 2H by the beta sum: equivalent for s/p AOs apart from 1e-14.',
                  'd_AO_difference': 'v23.0.3 MULLIK uses beta_p for every non-first AO including d; AUX uses beta_d for d. The diagnostic rescales only inter-atom blocks with the exact PM7 beta ratio.',
                  'MO_mapping': 'nAO is len(AO_ATOMINDEX), not len(exported occupancies). Ordinary AUX may omit deeply occupied MOs; full AUX density still exists in these outputs.',
                  'charges_direct': 'AUX MULLIKEN_ATOM_CHARGES is the actual internal result with fixed 5 decimals; the .out atomic table has 6 decimals. Neither contains a unique atom-pair allocation.',
                  'direct_pairs_keyword': 'v23.0.3 mpcpop prints atomic populations and charges only; no direct pair table was found in this execution path.',
                  'future_same_SCF_option': 'GRAPHF ALLVEC exports the exact internal MULLIK inverse-overlap root and sufficient MOs in the same B single point; GRAPH exports double-precision binary data. Parse compact pairs, then discard dense working matrices. This audit does not launch either option.',
                  'precision_status': 'All reconstructions use existing rounded AUX. Numerical residual after model/layout correction can be reported; precision is not presumed to be the original cause.'},
              'new_QM_calls': 0, 'Hamiltonian_or_density_labels_saved': False,
              'frozen_parser_modified': False, 'cases': results}
    dump(destination / 'mulliken_audit.json', report)
    print(json.dumps({'report': str(destination / 'mulliken_audit.json'), 'completed': len(results),
                      'errors': errors, 'elapsed_seconds': report['elapsed_seconds']}), flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
