"""Window-two population and frozen D5 producer; one pass, no content hashes."""
from __future__ import annotations
import argparse
import ast
import collections
import json
import os
from pathlib import Path
import socket

REPO = Path(__file__).absolute().parents[4]


def read(reference):
    path = Path(reference['path'] if isinstance(reference, dict) else reference)
    return json.loads(path.read_text(encoding='utf-8-sig'))


def info(path, records=None):
    value = {'path': str(Path(path).absolute()), 'bytes': Path(path).stat().st_size}
    if records is not None:
        value['records'] = records
    return value


def save(path, value):
    path = Path(path)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    return info(path)


def original_membership_functions():
    """Load unchanged pure functions without the old resource/import framework."""
    path = REPO / 'workflows/data_v1_final/conformers/formal_cpu_auto_finalize_mapping_v2/finalize.py'
    module = ast.parse(path.read_text(encoding='utf-8'))
    names = {'membership', 'exclusion_gates'}
    nodes = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in nodes} != names:
        raise ValueError('ORIGINAL_MEMBERSHIP_FUNCTIONS_MISSING')
    namespace = {'Counter': collections.Counter}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['membership'], namespace['exclusion_gates']


def update_member(row, membership, extras, states):
    value = dict(row)
    predicted = membership(value)
    if predicted['common_population'] != value['common_population']:
        raise ValueError('SOURCE_MEMBERSHIP_AND_ORIGINAL_PREDICATE_DISAGREE:' + value['molecule_id'])
    value.update(predicted)
    value['ordinary_pprime_two_conformers_pending'] = value['pprime_two_conformers_pending']
    mid = value['molecule_id']
    count = int(mid in extras)
    available = value['merged_uff_count'] + count
    value['registered_pprime_extra_conformers'] = count
    value['available_real_Pprime_bases'] = available
    value['n1_current_state'] = ('REGISTERED_REAL_SECOND_GEOMETRY' if count else
        states.get(mid, 'NOT_IN_REGISTERED_N1_SCOPE'))
    value['pprime_two_conformers_pending'] = value['common_population'] and available < 2
    return value


def build_common(source, n1, out):
    import pyarrow as pa
    import pyarrow.parquet as pq
    original = read(source)
    config = read(n1)
    membership, exclusion_gates = original_membership_functions()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'membership').mkdir()
    extras, states = {}, {}
    for component in config['components']:
        accepted = read(component['accepted_extra_index_reference'])
        for position, row in enumerate(accepted['records']):
            mid = row['molecule_id']
            if mid in extras:
                raise ValueError('DUPLICATE_REGISTERED_N1_MOLECULE:' + mid)
            extras[mid] = dict(row, source_path=accepted['geometry_table']['path'],
                source_bytes=accepted['geometry_table']['bytes'], source_row_index=position,
                source_format='parquet', source_member=None)
    for key in ('original_Alpha_all4407_states_reference', 'prior_Main_all224_states_reference'):
        with Path(config[key]['path']).open(encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                if row['molecule_id'] in states:
                    raise ValueError('DUPLICATE_N1_STATE_MOLECULE')
                states[row['molecule_id']] = row.get('status', 'UNKNOWN')
    members, gate_rows, n1_rows, extra_rows = [], [], [], []
    seen, counts = set(), collections.Counter()
    for reference in original['membership_tables']:
        rows = []
        file = pq.ParquetFile(reference['path'])
        for batch in file.iter_batches(batch_size=8192):
            for row in batch.to_pylist():
                mid = row['molecule_id']
                if mid in seen:
                    raise ValueError('DUPLICATE_POPULATION_MOLECULE:' + mid)
                seen.add(mid)
                value = update_member(row, membership, extras, states)
                rows.append(value)
                gate_rows.append({key: value[key] for key in
                    ('effective_role', 'common_population', 'elements_atomic_numbers')})
                if value['common_population']:
                    counts[(value['effective_role'], 'molecules')] += 1
                    counts[(value['effective_role'], 'pm7')] += value['S_conformers']
                    counts[(value['effective_role'], 'uff')] += value['merged_uff_count']
                    if mid in extras:
                        extra = extras[mid]
                        extra_rows.append(dict(extra, effective_role=value['effective_role'],
                            ordinary_sprime_member=False, usage_domain='pprime_extra'))
                if value['common_population'] and value['S_conformers'] == 1:
                    n1_rows.append({key: value[key] for key in ('molecule_id', 'effective_role',
                        'n1_current_state', 'registered_pprime_extra_conformers',
                        'available_real_Pprime_bases', 'pprime_two_conformers_pending')})
        path = out / 'membership' / Path(reference['path']).name
        pq.write_table(pa.Table.from_pylist(rows), path, compression='zstd', row_group_size=8192)
        members.append(info(path, len(rows)))
        print(json.dumps({'stage':'common','molecules':len(seen)}), flush=True)
    gates = exclusion_gates(gate_rows)
    if len(seen) != 1220466 or gates['mother_molecules'] != original['denominator_molecules']:
        raise ValueError('ORIGINAL_FULL_POPULATION_OR_ROLE_DENOMINATOR_CHANGED')
    if not gates['passed']:
        raise ValueError('UNCHANGED_COMMON_SCIENTIFIC_EXCLUSION_RULE_FAILED')
    # Membership and alignment are checked while producing, with no reread.
    n1path = out / 'n1_state.parquet'
    pq.write_table(pa.Table.from_pylist(n1_rows), n1path, compression='zstd')
    extrarefs = []
    if extra_rows:
        # JSON preserves source metadata without Arrow inferring mixed legacy fields.
        path = out / 'registered_pprime_extra.jsonl'
        with path.open('x', encoding='utf-8') as stream:
            for row in extra_rows:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
        extrarefs.append(info(path, len(extra_rows)))
    result = dict(original)
    result.update(status='COMMON_POPULATION_V1_FROZEN', version='v1-final',
        membership_tables=members, roles=[{'effective_role':role,
            'molecules':counts[(role,'molecules')], 'pm7_records':counts[(role,'pm7')],
            'uff_records':counts[(role,'uff')]} for role in ('TRAIN','VAL')],
        runtime={'job_id':os.environ.get('SLURM_JOB_ID'), 'node':socket.gethostname(),
            'uid':os.getuid()}, source_common_component=source,
        original_source_parent_state='FAILED_AFTER_COMMON_CLOSED',
        registered_extra_geometry_map_tables=extrarefs,
        registered_extra_geometry_tables=[component['registered_identity_table_reference']
            for component in config['components']],
        n1_current_state_reference=info(n1path, len(n1_rows)),
        pprime_n1_molecules=sum(row['pprime_two_conformers_pending'] for row in n1_rows),
        ordinary_N_and_D5_unchanged=True, n1_component_config=n1,
        exclusion_summary=gates, orders_frozen=False, order_manifest=None,
        original_5659_state='FAILED', original_5659_promoted_to_C0=False,
        checks={'producer_membership_alignment_once':True, 'source_molecules':len(seen),
            'scientific_membership_unchanged':True},
        Sprime_exhaustion_complete=False,
        source_fill_execution_unresolved_molecules=original.get('execution_unresolved_molecules'),
        content_hashes_computed=False, new_UFF_calls=0, new_QM_calls=0)
    save(out / 'manifest.json', result)
    paths = [*members, info(n1path, len(n1_rows)), *extrarefs]
    save(out / 'delivery_manifest.json', {'files': paths})
    return result


def check_nested(subsets):
    expected = (('train_120000',120000), ('train_240000',240000), ('train_600000',600000))
    previous = set()
    for name, count in expected:
        values = subsets[name]
        if len(values) != count or len(set(values)) != count or not previous <= set(values):
            raise ValueError('NESTED_D5_COUNTS_OR_MEMBERSHIP:' + name)
        previous = set(values)
    if not previous <= set(subsets['train_all']):
        raise ValueError('D5_600K_NOT_IN_ALL')


def build_d5(common, original_d5, out):
    import pyarrow as pa
    import pyarrow.parquet as pq
    population = read(common)
    prior = read(original_d5)
    components = prior['components']
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    train = set()
    for reference in population['membership_tables']:
        table = pq.read_table(reference['path'], columns=['molecule_id','effective_role','common_population'])
        train.update(row['molecule_id'] for row in table.to_pylist()
            if row['common_population'] and row['effective_role'] == 'TRAIN')
    # Preserve the already frozen complete-Sprime selection exactly. This keeps
    # all scale comparisons stable when extra molecules are completed later.
    lists, references = {}, {}
    for name in ('train_120000','train_240000','train_600000','train_all'):
        reference = components['subsets'][name]
        table = pq.read_table(reference['path'])
        mids = table.column('molecule_id').to_pylist()
        if not set(mids) <= train:
            raise ValueError('FROZEN_D5_MEMBER_OUTSIDE_FINAL_COMMON_TRAIN:' + name)
        lists[name] = mids
        references[name] = {**reference, 'records':len(mids)}
    old_all = lists['train_all']
    lists['train_all'] = old_all + sorted(train - set(old_all))
    full_path = out / 'train_all.parquet'
    pq.write_table(pa.table({'molecule_id': lists['train_all'], 'subset_rank': range(len(lists['train_all']))}),
        full_path, compression='zstd', row_group_size=8192)
    references['train_all'] = info(full_path, len(lists['train_all']))
    check_nested(lists)
    diagnostic = components['diagnostic_base_reference']
    table = pq.read_table(diagnostic['path'])
    mids = set(table.column('molecule_id').to_pylist())
    if len(mids) != 20000 or not mids <= train:
        raise ValueError('FROZEN_DIAGNOSTIC20K_NOT_COMPLETE_FINAL_TRAIN')
    # Existing 20k PM7 and 20k UFF bases and every direct child target are
    # already excluded before selecting first-k training conformers.
    result = {'schema':'FINAL_COMMON_D5_V1','status':'FROZEN','version':'v1-final',
        'source_common':common,'subsets':references,'all_subset_molecules':len(lists['train_all']),
        'all_scope':'ALL_FINAL_COMMON_TRAIN_COMPLETE_SPRIME_AT_FREEZE',
        'diagnostic_molecules':20000,'diagnostic_base_reference':diagnostic,
        'diagnostic_targets_reference':components['diagnostic_targets_reference'],
        'actual_heldout_geometry_reference':components['actual_heldout_geometry_reference'],
        'actual_input_views_reference':components['actual_input_views_reference'],
        'all_fixed_random_base_index_reference':components['all_fixed_random_base_index_reference'],
        'training_fixed_random_base_index_reference':components['training_fixed_random_base_index_reference'],
        'heldout_PM7_bases':components['heldout_PM7_bases'],
        'heldout_ordinary_Sprime_bases':components['heldout_ordinary_Sprime_bases'],
        'all_training_lists_anti_join_global_base_child_inputview_targets_before_first_k':True,
        'original_D5_delivery':original_d5,'selection_changed':False,
        'checks':{'producer_nested_role_and_holdout_alignment_once':True},
        'new_geometry_or_labels_computed':False,'content_hashes_computed':False}
    save(out / 'manifest.json', result)
    save(out / 'delivery_manifest.json', {'files':[
        *references.values(), diagnostic, components['diagnostic_targets_reference'],
        components['actual_heldout_geometry_reference'], components['training_fixed_random_base_index_reference']]})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    common = sub.add_parser('common')
    common.add_argument('--source', required=True)
    common.add_argument('--n1', required=True)
    common.add_argument('--output', required=True)
    d5 = sub.add_parser('d5')
    d5.add_argument('--common', required=True)
    d5.add_argument('--original-d5', required=True)
    d5.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'common':
        build_common(args.source, args.n1, args.output)
    else:
        build_d5(args.common, args.original_d5, args.output)


if __name__ == '__main__':
    main()