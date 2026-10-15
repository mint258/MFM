#!/usr/bin/env python3
"""WP0 inventory and WP1 first-step analysis of closed Stage61 core records.

This program reads derived Parquet and small receipts only. It never opens or
writes an LMDB. TRAIN and FULL retain their existing memberships; routine is an
additional membership of FULL. Native records outside those existing views are
reported as an unassigned source gap, rather than silently called screened.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

PROJECT = Path('/share/home/zixiao/descriptor_analysis')
AUDIT = PROJECT / 'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2'
DEFAULT_OUTPUT = PROJECT / 'runs/phase1_dataset_rebuild_20261010'
sys.path[:0] = [str(AUDIT / 'deps'), str(AUDIT / 'scripts/deps')]

WHITELIST = (1, 5, 6, 7, 8, 9, 14, 15, 16, 17, 34, 35, 53)
X_CODES = ('X01', 'X02', 'X03', 'X04', 'X05')
G_CODES = ('G01', 'G02', 'G03')
KEY_PATTERN = r'^(.*)_([0-9]{8})_([0-9]{2})$'
HEAVY_BINS = ('01_0_10', '02_11_20', '03_21_30', '04_31_50',
              '05_51_75', '06_76_100', '07_gt100')


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def ref(path: Path, with_sha: bool = True) -> dict:
    result = {'path': str(path), 'bytes': path.stat().st_size}
    if with_sha:
        result['sha256'] = sha256(path)
    return result


def dump(path: Path, value: object) -> None:
    pending = path.with_name(path.name + '.pending')
    pending.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                  allow_nan=False) + '\n', encoding='utf-8')
    pending.replace(path)


def sql_string(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def sql_paths(paths: list[str]) -> str:
    return '[' + ','.join(map(sql_string, paths)) + ']'


def fetch(db, sql: str) -> list[dict]:
    cursor = db.execute(sql)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def heavy_bin(column: str) -> str:
    return (f"CASE WHEN {column}<=10 THEN '01_0_10' "
            f"WHEN {column}<=20 THEN '02_11_20' "
            f"WHEN {column}<=30 THEN '03_21_30' "
            f"WHEN {column}<=50 THEN '04_31_50' "
            f"WHEN {column}<=75 THEN '05_51_75' "
            f"WHEN {column}<=100 THEN '06_76_100' "
            f"WHEN {column}>100 THEN '07_gt100' ELSE 'UNKNOWN' END")


def collect_closed_core(audit: Path) -> tuple[dict, dict, list[dict]]:
    plan_path = audit / 'plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    files = {role: [] for role in ('train', 'full', 'routine')}
    coverage = {role: 0 for role in files}
    receipts = []
    for expected in plan['chunks']:
        chunk_path = audit / 'chunks' / f"{expected['id']:03d}.json"
        chunk = json.loads(chunk_path.read_text(encoding='utf-8'))
        if chunk['chunk'] != expected:
            raise RuntimeError(f'Closed chunk scope differs: {chunk_path}')
        if chunk['plan_sha256'] != plan['content_sha256']:
            raise RuntimeError(f'Closed chunk plan differs: {chunk_path}')
        pieces = []
        for piece_ref in chunk['pieces']:
            piece_path = Path(piece_ref['path'])
            if not piece_path.is_relative_to(audit / 'pieces'):
                raise RuntimeError(f'Unexpected closed piece path: {piece_path}')
            if sha256(piece_path) != piece_ref['sha256']:
                raise RuntimeError(f'Closed receipt changed: {piece_path}')
            piece = json.loads(piece_path.read_text(encoding='utf-8'))
            pieces.append((piece_path, piece))
        cursor = expected['start']
        for piece_path, piece in sorted(pieces, key=lambda item: item[1]['start']):
            if (piece['role'] != expected['role'] or piece['start'] != cursor or
                    piece['records'] != piece['stop'] - piece['start'] or
                    piece['plan_sha256'] != plan['content_sha256']):
                raise RuntimeError(f'Non-contiguous closed piece: {piece_path}')
            references = [item for item in piece['files']
                          if item['path'] == 'records.parquet']
            if len(references) != 1:
                raise RuntimeError(f'Non-unique core record file: {piece_path}')
            core = dict(references[0], path=str(piece_path.parent / 'records.parquet'))
            if Path(core['path']).stat().st_size != core['bytes']:
                raise RuntimeError(f'Closed Parquet size differs: {core["path"]}')
            files[piece['role']].append(core['path'])
            receipts.append({'role': piece['role'], 'start': piece['start'],
                             'stop': piece['stop'], 'core': core,
                             'receipt': ref(piece_path)})
            coverage[piece['role']] += piece['records']
            cursor = piece['stop']
        if cursor != expected['stop']:
            raise RuntimeError(f'Incomplete closed chunk: {chunk_path}')
    expected_counts = {role: plan['manifests'][role]['view']['rows'] for role in files}
    if coverage != expected_counts:
        raise RuntimeError(f'Closed three-role coverage differs: {coverage}')
    return plan, files, receipts


def role_summary(db, role: str) -> dict:
    member = 'member_' + role
    population = fetch(db, f'''SELECT count(*) AS records,
        count(DISTINCT molecule_id) AS molecules,
        count(*) FILTER (WHERE NOT sample_key_parse_valid) AS unparsed_sample_keys,
        count(*) FILTER (WHERE pre_geometry_keep) AS early_keep_records,
        count(DISTINCT molecule_id) FILTER (WHERE pre_geometry_keep) AS early_keep_molecules,
        count(*) FILTER (WHERE X_keep) AS after_X_records,
        count(DISTINCT molecule_id) FILTER (WHERE X_keep) AS after_X_molecules
        FROM idx WHERE {member}''')[0]
    groups = f'''SELECT molecule_id, count(*) AS records,
        count(DISTINCT conformer_id) AS distinct_conformer_ids
        FROM idx WHERE {member} GROUP BY molecule_id'''
    hist = fetch(db, f'''SELECT records AS conformers, count(*) AS molecules
        FROM ({groups}) GROUP BY records ORDER BY records''')
    population['conformers_1_to_10'] = {
        str(value): next((row['molecules'] for row in hist if row['conformers'] == value), 0)
        for value in range(1, 11)}
    population['conformer_count_distribution'] = hist
    population['molecules_with_more_than_10_records'] = sum(
        row['molecules'] for row in hist if row['conformers'] > 10)
    population['molecules_with_duplicate_conformer_ids'] = db.execute(
        f'SELECT count(*) FROM ({groups}) WHERE records<>distinct_conformer_ids').fetchone()[0]
    population['prefixes'] = fetch(db, f'''SELECT sample_prefix, source_family,
        count(*) AS records, count(DISTINCT molecule_id) AS molecules
        FROM idx WHERE {member} GROUP BY ALL ORDER BY sample_prefix,source_family''')
    hits = {}
    for code in X_CODES + G_CODES + ('B01',):
        condition = member if code in X_CODES else f'{member} AND X_keep'
        hits[code] = fetch(db, f'''SELECT count(*) AS assessed_population,
            count(*) FILTER (WHERE {code} IS TRUE) AS hit_records,
            count(*) FILTER (WHERE {code} IS NULL) AS unknown_records,
            count(DISTINCT molecule_id) FILTER (WHERE {code} IS TRUE) AS hit_molecules
            FROM idx WHERE {condition}''')[0]
    population['code_counts'] = hits
    overlaps = []
    expressions = []
    for left in X_CODES:
        for right in X_CODES:
            expressions.append(f'count(*) FILTER (WHERE {left} IS TRUE AND {right} IS TRUE) AS {left}_{right}')
    values = fetch(db, 'SELECT ' + ','.join(expressions) + f' FROM idx WHERE {member}')[0]
    for left in X_CODES:
        for right in X_CODES:
            overlaps.append({'left': left, 'right': right, 'records': values[left + '_' + right]})
    population['X_overlap_matrix'] = overlaps
    stages = []
    keep = member
    for code in X_CODES:
        keep += f' AND {code} IS FALSE'
        count = fetch(db, f'''SELECT count(*) AS records,count(DISTINCT molecule_id) AS molecules
            FROM idx WHERE {keep}''')[0]
        stages.append({'after': code, **count})
    for code in G_CODES:
        keep += f' AND {code} IS FALSE'
        count = fetch(db, f'''SELECT count(*) AS records,count(DISTINCT molecule_id) AS molecules
            FROM idx WHERE {keep}''')[0]
        stages.append({'after': code, **count})
    population['sequential_early_remaining'] = stages
    population['after_X_H01'] = fetch(db, f'''SELECT count(*) AS records,
        min(H01_abs_energy_per_atom) AS minimum,
        median(H01_abs_energy_per_atom) AS median,
        quantile_cont(H01_abs_energy_per_atom,.90) AS p90,
        quantile_cont(H01_abs_energy_per_atom,.99) AS p99,
        max(H01_abs_energy_per_atom) AS maximum,
        count(*) FILTER (WHERE H01_abs_energy_per_atom>20) AS above_20,
        count(*) FILTER (WHERE H01_abs_energy_per_atom>30) AS above_30,
        count(*) FILTER (WHERE H01_abs_energy_per_atom>50) AS above_50,
        count(*) FILTER (WHERE H01_abs_energy_per_atom>200) AS above_200
        FROM idx WHERE {member} AND X_keep''')[0]
    population['early_keep_size_bins'] = fetch(db, f'''SELECT {heavy_bin('heavy_atoms')} AS size_bin,
        count(*) AS records, count(DISTINCT molecule_id) AS molecules
        FROM idx WHERE {member} AND pre_geometry_keep GROUP BY ALL ORDER BY size_bin''')
    population['early_keep_element_composition'] = fetch(db, f'''SELECT entry.key AS atomic_number,
        sum(entry.value) AS atoms,count(*) AS records
        FROM (SELECT unnest(map_entries(element_counts)) AS entry FROM idx
              WHERE {member} AND pre_geometry_keep)
        GROUP BY entry.key ORDER BY atomic_number''')
    return population


def make_pilot_panel(db, out: Path, target: int, seed: int) -> dict:
    db.execute(f'''CREATE TABLE molecule_panel_pool AS
        SELECT molecule_id,min(sample_prefix) AS sample_prefix,min(heavy_atoms) AS heavy_atoms,
            max(heavy_atoms) AS maximum_heavy_atoms,count(*) AS conformers,
            {heavy_bin('min(heavy_atoms)')} AS size_bin
        FROM idx GROUP BY molecule_id
        HAVING bool_and(pre_geometry_keep) AND bool_and(sample_key_parse_valid)
            AND min(heavy_atoms)=max(heavy_atoms)''')
    available = fetch(db, '''SELECT size_bin,sum(conformers)::BIGINT AS records,
        count(*) AS molecules FROM molecule_panel_pool GROUP BY size_bin ORDER BY size_bin''')
    capacities = {row['size_bin']: row['records'] for row in available}
    remaining = min(target, sum(capacities.values()))
    budgets = dict.fromkeys(capacities, 0)
    active = list(capacities)
    while remaining > 0 and active:
        share = max(1, math.ceil(remaining / len(active)))
        for bin_name in list(active):
            amount = min(share, remaining, capacities[bin_name] - budgets[bin_name])
            budgets[bin_name] += amount
            remaining -= amount
            if budgets[bin_name] == capacities[bin_name]:
                active.remove(bin_name)
            if remaining <= 0:
                break
    db.execute('CREATE TABLE panel_budgets(size_bin VARCHAR,record_budget BIGINT)')
    db.executemany('INSERT INTO panel_budgets VALUES (?,?)', list(budgets.items()))
    db.execute(f'''CREATE TABLE selected_molecules AS SELECT * EXCLUDE(cumulative_records)
        FROM (SELECT p.*,sum(conformers) OVER(PARTITION BY p.size_bin
            ORDER BY sha256(molecule_id||'|{seed}'),molecule_id
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_records
            FROM molecule_panel_pool p)
        JOIN panel_budgets USING(size_bin) WHERE cumulative_records<=record_budget''')
    panel = out / 'pilot_candidates_pre_geometry.parquet'
    pending = panel.with_name(panel.name + '.pending')
    db.execute(f'''COPY (SELECT i.*,'PRE_GEOMETRY_C02_C03_I01_PENDING' AS candidate_scope
        FROM idx i JOIN selected_molecules s USING(molecule_id)
        ORDER BY s.size_bin,i.molecule_id,i.conformer_id,i.record_id)
        TO {sql_string(pending)} (FORMAT PARQUET,COMPRESSION ZSTD)''')
    pending.replace(panel)
    counts = fetch(db, '''SELECT size_bin,count(*) AS molecules,sum(conformers)::BIGINT AS records,
        min(heavy_atoms) AS smallest,max(heavy_atoms) AS largest
        FROM selected_molecules GROUP BY size_bin ORDER BY size_bin''')
    return {'path': str(panel), 'target_records': target,
            'actual_records': sum(row['records'] for row in counts),
            'actual_molecules': sum(row['molecules'] for row in counts),
            'seed': seed, 'stratum_record_budgets': budgets,
            'available_whole_molecules': available, 'selected_by_stratum': counts,
            'whole_molecule_rule': 'Every current physical TRAIN/FULL conformer of each selected molecule is included and passes X and early G checks.',
            'scope': 'Candidate panel only: charge=0 geometric bond assignment, closed-shell and InChIKey tests remain pending.',
            'final_WP4_panel_ready': False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-root', type=Path, default=AUDIT)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--workers', type=int, default=16)
    parser.add_argument('--memory-gb', type=int, default=24)
    parser.add_argument('--temp-gb', type=int, default=32)
    parser.add_argument('--seed', type=int, default=20261010)
    parser.add_argument('--target-pilot-records', type=int, default=10000)
    args = parser.parse_args()
    allocated = int(os.environ.get('SLURM_CPUS_PER_TASK', '0'))
    if not os.environ.get('SLURM_JOB_ID') or not 16 <= args.workers <= allocated:
        raise RuntimeError('Run in a CPU Slurm allocation with >=16 effectively parallel CPUs.')
    if args.memory_gb < 1 or args.temp_gb < 1 or args.target_pilot_records < 1:
        raise ValueError('Positive memory, temporary storage and panel target required.')
    args.out.mkdir(parents=True, exist_ok=True)
    outputs = ('record_index.parquet', 'inventory.json', 'pilot_candidates_pre_geometry.parquet',
               'wp1_first_step_examples.json', 'wp0_inputs.json')
    if any((args.out / name).exists() for name in outputs):
        raise RuntimeError('WP0 outputs already exist; use a fresh output directory.')
    started = time.monotonic()
    begin = dt.datetime.now(dt.timezone.utc).isoformat()
    plan, files, receipts = collect_closed_core(args.audit_root)
    dump(args.out / 'wp0_inputs.json', {'plan': ref(args.audit_root / 'plan.json'),
        'closed_record_files': receipts,
        'core_SHA256_verification': 'Receipt SHA and closed file size checked; full Parquet SHA is inherited from successful Stage61 receipts to avoid another whole-cache read.'})
    progress_path = args.out / 'wp0_progress.json'

    def progress(stage: str, **extra) -> None:
        dump(progress_path, {'stage': stage, 'elapsed_seconds': time.monotonic() - started,
                            'job_id': os.environ['SLURM_JOB_ID'], **extra})

    import duckdb
    temporary = args.out / 'tmp_wp0_inventory'
    temporary.mkdir(exist_ok=False)
    db = duckdb.connect()
    db.execute(f'SET threads={args.workers}')
    db.execute(f"SET memory_limit='{args.memory_gb}GB'")
    db.execute(f"SET max_temp_directory_size='{args.temp_gb}GB'")
    db.execute('SET temp_directory=' + sql_string(temporary))
    db.execute('SET preserve_insertion_order=false')
    progress('create_index', closed_files=sum(map(len, files.values())))
    try:
        db.execute('CREATE TABLE source_shards(shard_id INTEGER,shard_name VARCHAR,source_path VARCHAR)')
        db.executemany('INSERT INTO source_shards VALUES (?,?,?)', [
            (index, item['name'], item['path']) for index, item in enumerate(plan['sources'])])
        for role in files:
            db.execute(f'''CREATE VIEW core_{role} AS SELECT *
                FROM read_parquet({sql_paths(files[role])},union_by_name=true)''')
        db.execute('''CREATE TABLE routine_members AS
            SELECT record_id,logical_index AS routine_logical_index FROM core_routine''')
        db.execute('''CREATE VIEW physical_core AS SELECT 'train' AS split,* FROM core_train
            UNION ALL BY NAME SELECT 'full' AS split,* FROM core_full''')
        electron_sum = '+'.join(f'{number}*c.element_count_Z{number}' for number in range(1, 119))
        counts = ','.join(f'struct_pack(z := {number},n := c.element_count_Z{number})'
                          for number in range(1, 119))
        whitelist = '[' + ','.join(map(str, WHITELIST)) + ']'
        db.execute(f'''CREATE VIEW index_base AS WITH parsed AS (
            SELECT c.*,s.shard_name,s.source_path,r.routine_logical_index,
                regexp_full_match(c.sample_key,{sql_string(KEY_PATTERN)}) AS sample_key_parse_valid,
                regexp_extract(c.sample_key,{sql_string(KEY_PATTERN)},1) AS sample_prefix,
                regexp_extract(c.sample_key,{sql_string(KEY_PATTERN)},2) AS molecule_number,
                try_cast(regexp_extract(c.sample_key,{sql_string(KEY_PATTERN)},3) AS INTEGER) AS conformer_id,
                CASE WHEN c.native_x_encoding_or_shape_invalid IS FALSE THEN ({electron_sum})::BIGINT ELSE NULL END AS electron_count,
                CASE WHEN c.native_x_encoding_or_shape_invalid IS FALSE THEN map_from_entries(
                    list_filter([{counts}],item -> item.n>0)) ELSE NULL END AS element_counts
            FROM physical_core c JOIN source_shards s USING(shard_id)
            LEFT JOIN routine_members r USING(record_id))
            SELECT record_id,shard_id,real_index,record_payload_sha256,shard_name,source_path,
                split,split='train' AS member_train,split='full' AS member_full,
                routine_logical_index IS NOT NULL AS member_routine,
                list_filter([CASE WHEN split='train' THEN 'train' END,
                    CASE WHEN split='full' THEN 'full' END,
                    CASE WHEN routine_logical_index IS NOT NULL THEN 'routine' END],
                    value -> value IS NOT NULL) AS membership,
                CASE WHEN split='train' THEN logical_index ELSE NULL END AS train_logical_index,
                CASE WHEN split='full' THEN logical_index ELSE NULL END AS full_logical_index,
                routine_logical_index,logical_index,sample_key,sample_prefix,sample_key_parse_valid,
                CASE WHEN sample_key_parse_valid THEN sample_prefix||'_'||molecule_number
                    ELSE 'UNPARSED:'||record_id END AS molecule_id,conformer_id,
                CASE WHEN starts_with(shard_name,'principal_') THEN 'principal'
                    WHEN starts_with(shard_name,'unimol_') THEN 'unimol' ELSE 'other' END AS source_family,
                smiles,canonical_smiles,isomeric_smiles,inchikey AS stored_inchikey,
                total_atoms,heavy_atoms,elements,element_counts,electron_count,
                energy_raw,energy_unit,fragments AS stored_graph_fragments,
                formal_charge,charged_atoms,radical_electrons,parse_failed,sanitize_failed,
                native_x_encoding_or_shape_invalid,atom_sequence_mismatch,H_count_mismatch,
                atomic_array_shape_mismatch,geometry_nonfinite,geometry_all_zero,
                minimum_distance_A,minimum_nonbond_distance_A,bond_count,
                bond_length_outlier_count,bond_length_outlier_fraction,
                order_suspected_from_bond_lengths,geometry_missing_bonds,geometry_extra_bonds,
                (strpos(smiles,'.')>0 OR fragments>1) AS X01,
                FALSE AS X01_geometry_checked,
                CASE WHEN native_x_encoding_or_shape_invalid IS FALSE THEN
                    length(list_filter(elements,z -> NOT list_contains({whitelist},z)))>0
                    ELSE NULL END AS X02,
                formal_charge<>0 AS X03,radical_electrons>0 AS X04,
                electron_count%2=1 AS X05,
                CASE WHEN total_atoms<=1 THEN FALSE ELSE minimum_distance_A<.5 END AS G01,
                CASE WHEN total_atoms<=1 OR bond_count=total_atoms*(total_atoms-1)/2 THEN FALSE
                    ELSE minimum_nonbond_distance_A<.9 END AS G02,
                order_suspected_from_bond_lengths AS G03,
                bond_length_outlier_count>0 AS B01,
                CASE WHEN total_atoms>0 THEN abs(energy_raw)/total_atoms ELSE NULL END AS H01_abs_energy_per_atom,
                CASE WHEN total_atoms>0 THEN energy_raw/total_atoms ELSE NULL END AS energy_per_atom_signed
            FROM parsed''')
        x_keep = ' AND '.join(f'{code} IS FALSE' for code in X_CODES)
        early_keep = x_keep + ' AND ' + ' AND '.join(f'{code} IS FALSE' for code in G_CODES)
        index_path = args.out / 'record_index.parquet'
        pending_index = index_path.with_name(index_path.name + '.pending')
        db.execute(f'''COPY (SELECT *,({x_keep}) AS X_keep,
            ({early_keep}) AS pre_geometry_keep FROM index_base)
            TO {sql_string(pending_index)} (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 100000)''')
        pending_index.replace(index_path)
        db.execute('CREATE VIEW idx AS SELECT * FROM read_parquet(' + sql_string(index_path) + ')')
        observed = fetch(db, '''SELECT count(*) AS physical_records,count(DISTINCT record_id) AS distinct_records,
            count(*) FILTER (WHERE member_train) AS train,count(*) FILTER (WHERE member_full) AS "full",
            count(*) FILTER (WHERE member_routine) AS routine,
            count(*) FILTER (WHERE member_routine AND NOT member_full) AS routine_outside_full,
            count(DISTINCT molecule_id) AS physical_molecules FROM idx''')[0]
        expected = {role: plan['manifests'][role]['view']['rows'] for role in files}
        if (observed['physical_records'] != expected['train'] + expected['full'] or
                observed['distinct_records'] != observed['physical_records'] or
                any(observed[role] != expected[role] for role in expected) or
                observed['routine_outside_full']):
            raise RuntimeError(f'Physical record/membership reconciliation failed: {observed}')
        inventory = {'schema': 'phase1_dataset_rebuild_WP0_WP1_first_step_v1',
            'status': 'WP0_AND_EARLY_SCREEN_COMPLETE_GEOMETRIC_CHEMISTRY_PENDING',
            'started_UTC': begin, 'created_UTC': dt.datetime.now(dt.timezone.utc).isoformat(),
            'seed': args.seed, 'job_id': os.environ['SLURM_JOB_ID'],
            'script': ref(Path(__file__)),
            'software': {'python': sys.version, 'duckdb': duckdb.__version__},
            'resources': {'effective_DuckDB_threads': args.workers,
                          'memory_limit_GB': args.memory_gb, 'temporary_limit_GB': args.temp_gb},
            'sample_key_parser': {'regex': KEY_PATTERN,
                'molecule_id': 'Complete prefix plus the eight-digit molecule number; final two digits are conformer_id.',
                'prefix_meaning': {'principal': 'Principal source raw/stable XYZ family.',
                    'molecule': 'Original Uni-Mol family key found in retained upstream XYZ and preserved by build_lmdb.',
                    'unimol': 'An observed sample prefix, if present; never inferred from a shard filename.'},
                'source_evidence': str(args.audit_root / 'source_snapshot/external/dataset/dataset_without_charge.py'),
                'unparsed_policy': 'Keep a unique UNPARSED:record_id molecule_id, flag invalid, and exclude from the provisional pilot only.'},
            'population': observed,
            'sources': plan['sources'],
            'source_gap': {'original_LMDB_records': sum(item['length'] for item in plan['sources']),
                'existing_membership_records': observed['physical_records'],
                'unassigned_original_records': sum(item['length'] for item in plan['sources']) - observed['physical_records'],
                'policy': 'Existing WP2 train/full views are retained. Original source records absent from those views remain unassigned and are not claimed to have passed or failed the new screening.',
                'legacy_QA_record_counts': {'identity_order_quarantine': 3149,
                    'known_fullkey_embargo': 4120, 'unknown_non_H_composition_embargo': 990},
                'legacy_QA_evidence': str(PROJECT / 'docs/phase1/evidence/stage48_full_corpus_qa/run_v2_4511985/summary.json')},
            'nonadditive_roles': 'routine is a membership subset of FULL; physical output contains TRAIN + FULL once.',
            'code_definitions': {'X01': 'Stored SMILES contains a dot or its parsed stored graph has more than one fragment. Geometry fragment check remains pending.',
                'X02': 'Any Native element outside H B C N O F Si P S Cl Se Br I; recomputed from actual element list.',
                'X03': 'Stored SMILES graph net formal charge is nonzero.',
                'X04': 'Stored SMILES graph radical electron count is positive.',
                'X05': 'Sum of Native atomic numbers is odd; Native atoms include H.',
                'G01': 'Minimum pair distance strictly less than 0.5 Angstrom.',
                'G02': 'Minimum distance of nonbonded pairs in the aligned stored graph is strictly less than 0.9 Angstrom.',
                'G03': 'Existing explicit suspicion rule: at least five bonds, with >25% having d/(sum covalent radii) outside [0.75,1.30].',
                'B01': 'Any stored-graph bond outside the existing covalent-radius ratio range [0.75,1.30]; annotation only.',
                'H01': 'abs(energy_raw)/Native total_atoms in kcal/mol/atom; annotation only. Prior published candidate counts used signed positive energy, so new absolute counts are recomputed.',
                'C02_C03_I01_T01_S01_S02': 'Await the new charge=0 geometry recognition and full molecule/conformer join.'},
            'unknown_policy': 'NULL means unavailable or not assessed; a provisional candidate requires all assessed X/G exclusions explicitly FALSE.',
            'outputs': {'record_index': str(index_path), 'inputs': str(args.out / 'wp0_inputs.json')},
            'roles': {}}
        for role in ('train', 'full', 'routine'):
            progress('role_statistics', role=role)
            inventory['roles'][role] = role_summary(db, role)
        inventory['molecules_crossing_train_full'] = db.execute('''SELECT count(*) FROM
            (SELECT molecule_id FROM idx GROUP BY molecule_id HAVING count(DISTINCT split)>1)''').fetchone()[0]
        inventory['unparsed_examples'] = fetch(db, '''SELECT record_id,sample_key,source_family
            FROM idx WHERE NOT sample_key_parse_valid ORDER BY record_id LIMIT 50''')
        progress('early_code_examples')
        examples = {}
        for code in X_CODES + G_CODES + ('B01',):
            qualifier = f'{code} IS TRUE' if code in X_CODES else f'X_keep AND {code} IS TRUE'
            examples[code] = fetch(db, f'''SELECT record_id,molecule_id,conformer_id,split,
                member_routine,sample_key,smiles,total_atoms,heavy_atoms,formal_charge,
                radical_electrons,electron_count,minimum_distance_A,minimum_nonbond_distance_A,
                H01_abs_energy_per_atom FROM idx WHERE {qualifier}
                ORDER BY sha256(record_id||'|{args.seed}'),record_id LIMIT 50''')
        dump(args.out / 'wp1_first_step_examples.json', {'seed': args.seed,
            'scope': 'X whole-category flags and G/B within after-X population; geometry-derived X01/C/I/T/S remain pending.',
            'examples': examples})
        progress('whole_molecule_pilot_candidates')
        inventory['pilot_candidates'] = make_pilot_panel(db, args.out, args.target_pilot_records, args.seed)
        inventory['record_index_schema'] = fetch(db, 'DESCRIBE idx')
        inventory['elapsed_seconds'] = time.monotonic() - started
        inventory['record_index_bytes'] = index_path.stat().st_size
        inventory['pending_WP1'] = ['Geometry-based fragments for X01',
            'C02 charge=0 RDKit bond determination and legitimate closed shell',
            'C03 timeout/error outcomes', 'I01 reconstructed versus stored SMILES InChIKey',
            'T01 specified stereochemistry versus 3D geometry', 'S01 molecule identity vote',
            'S02 conformer energy minus same molecule minimum',
            'Final code overlaps, retained population, and final WP4 whole-molecule panel']
        dump(args.out / 'inventory.json', inventory)
        progress('complete', records=observed['physical_records'],
                 pilot_records=inventory['pilot_candidates']['actual_records'])
        print(json.dumps({'inventory': str(args.out / 'inventory.json'),
                          'record_index': str(index_path), 'population': observed,
                          'elapsed_seconds': time.monotonic() - started}, ensure_ascii=False), flush=True)
    finally:
        db.close()
        # DuckDB removes its own spill files on close. Only this newly created
        # temporary namespace is eligible for cleanup, never a broad output root.
        if temporary.exists() and not any(temporary.iterdir()):
            temporary.rmdir()


if __name__ == '__main__':
    main()
