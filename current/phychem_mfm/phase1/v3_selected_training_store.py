"""Two-phase, original-source materialization for the frozen TRAIN dev panel.

Preparation closes chemical membership without numeric/annotation decoding.
Materialization checks that immutable selection before invoking the unchanged
source decoder, and publishes a new selected-TRAIN store, not a historical
full-role store. No old partial payload or pretraining label line is consumed.
"""
from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

from .v3_dev_panel import ALLOWED_ROLES, canonical
from .v3_dev_membership import GroupedTrainingView
from .v3_dev_store import bound_json, TrainOnlyPackedStore


ROOT = Path(__file__).absolute().parents[3]
DATASETS = ('cyp_isoform', 'expansionrx', 'qm9')
FROZEN_IMPLEMENTATIONS = {
    'native_packing': '2d79d1e73f07c2e277b28724225d64b138c7050d3a54a29de474d462c4bf5766',
    'source_decoder': 'e844e765bef02e3e30bea10f9e6b91137211c4f9fae87e2306ecfeee76a7b634',
    'graph_join': 'd33acef71ff11e2565d178c91c3a30b4353948a95b93dae2735f949cadd3c52a'}


class SelectedTrainingStoreError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise SelectedTrainingStoreError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def binding(path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), 'Ordinary physical source required')
    before = path.stat(); digest = hashlib.sha256(); size = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block); size += len(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns) and size == after.st_size,
            'Source changed during opaque byte binding')
    return {'path': str(path), 'bytes': size, 'sha256': digest.hexdigest()}


def write_json(path, value):
    with Path(path).open('xb') as stream:
        stream.write(encoded(value)+b'\n'); stream.flush(); os.fsync(stream.fileno())
    return binding(path)


def resolved_reference(ref):
    path = Path(ref['path'])
    if not path.is_absolute():
        path = ROOT / path
    result = {**ref, 'path': str(path)}
    require(binding(path) == {k: result[k] for k in ('path', 'bytes', 'sha256')}, 'Pinned physical source differs')
    return result


def _module(ref, name):
    name += '_'+ref['sha256'][:16]+'_'+canonical(ref['path'])[:8]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ref['path'])
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def frozen_modules(sources):
    refs = {key: resolved_reference(sources[key]) for key in FROZEN_IMPLEMENTATIONS}
    require(all(refs[k]['sha256'] == digest for k, digest in FROZEN_IMPLEMENTATIONS.items()),
            'Only the pinned original decoder/packing/structural join implementations are supported')
    native = _module(refs['native_packing'], 'model_v3_source_native')
    # The original module uses this fixed sibling import. Temporarily supply
    # only the byte-verified known source, then restore the caller's namespace.
    previous = sys.modules.get('downstream_binding_data')
    sys.modules['downstream_binding_data'] = native
    try:
        decoder = _module(refs['source_decoder'], 'model_v3_source_decoder')
    finally:
        if previous is None:
            sys.modules.pop('downstream_binding_data', None)
        else:
            sys.modules['downstream_binding_data'] = previous
    graph = _module(refs['graph_join'], 'model_v3_source_graph_join')
    return native, decoder, graph, refs


def source_inventory():
    paths = list((ROOT / 'current/phychem_mfm').rglob('*.py'))
    paths += [ROOT / 'tools/model_v3' / name for name in (
        'prepare_selected_training_store.py', 'materialize_selected_training_store.py')]
    with ThreadPoolExecutor(max_workers=16) as pool:
        refs = list(pool.map(binding, sorted(paths)))
    return [{'path': str(Path(ref['path']).relative_to(ROOT)), 'sha256': ref['sha256'], 'bytes': ref['bytes']}
            for ref in refs]


def verify_inventory(refs):
    require(refs, 'Nonempty executed-source inventory required')
    for ref in refs:
        path = ROOT / ref['path']
        require(path.resolve().is_relative_to(ROOT.resolve()) and binding(path)['sha256'] == ref['sha256'],
                'Executed source differs from the label-free selection request')


def units_for(definition, protocol):
    if isinstance(definition['tasks'][0], dict):
        return [task['unit'] for task in definition['tasks']]
    return [protocol['downstream']['analysis_rules']['endpoints'][endpoint]['units']
            for endpoint in definition['endpoint_ids']]


class OriginalMetadataStore:
    """Expose only original TRAIN metadata, never a physical sample getter."""
    def __init__(self, membership, expansion, definitions, panel, native):
        self.members, self.groups, self.contracts, self.geometry = {}, {}, {}, {}
        require(expansion.get('complete') is True and expansion.get('target_fields_decoded') is False,
                'Closed target-opaque Expansion geometry required')
        native.check_seal(expansion)
        exp_rows = {}
        for row in expansion['records']:
            if row['declared_role'] == 'train':
                require(row['member_uid'] not in exp_rows, 'Duplicate native Expansion geometry')
                native.check_seal(row); exp_rows[row['member_uid']] = row
        for dataset in DATASETS:
            bucket = 'expansionrx_train' if dataset == 'expansionrx' else dataset
            originals = membership.rows[bucket]
            fold = 'official' if dataset == 'expansionrx' else panel['source_roles']['scaffold_datasets']['fold_id']
            ids = {role: list(membership.views[dataset, fold, role]) for role in ALLOWED_ROLES}
            require(not (set(ids[ALLOWED_ROLES[0]]) & set(ids[ALLOWED_ROLES[1]])), 'Original TRAIN roles overlap')
            self.contracts[dataset] = {'dataset_id': dataset, 'fold_id': fold,
                'tasks': [t['task_id'] if isinstance(t, dict) else t for t in definitions[dataset]['tasks']],
                'output_level': definitions[dataset]['output_level'], 'member_indices': ids,
                'ordered_members': {r: [originals[i]['member_uid'] for i in values] for r, values in ids.items()},
                'original_role_files': {r: membership.view_refs.get((dataset, fold, r)) for r in ALLOWED_ROLES}}
            for index in sorted({i for values in ids.values() for i in values}):
                member = originals[index]
                require(member['dataset'] == dataset and member['member_index'] == index
                        and member['label_masks'] == 'NOT_MATERIALIZED', 'Original native member metadata differs')
                key = (dataset, index); uid = member['member_uid']
                if dataset == 'expansionrx':
                    g = exp_rows.get(uid)
                    require(g is not None and g['member_row_sha256'] == native.canonical(member)
                            and g['source_member_index'] == index and g['raw_frame_sha256'] == member['source_frame']['raw_frame_sha256']
                            and g.get('target_fields_decoded') is False, 'Expansion identity/native source join differs')
                    group, n, ready = g['full_inchikey'], g['native_n_atoms'], g['status'] == 'GEOMETRY_READY'
                    self.geometry[key] = g
                else:
                    group = member['inchikey']
                    g = member['source_frame'] if dataset == 'qm9' else member['geometry_artifact_ref']
                    n = g['native_n_atoms']
                    ready = True if dataset == 'qm9' else g['status'] == 'GEOMETRY_READY'
                require(isinstance(group, str) and re.fullmatch(r'[A-Z]{14}-[A-Z]{10}-[A-Z]', group),
                        'Reliable full source chemical identity required; UID fallback is forbidden')
                require(type(n) is int and 0 < n <= 4096, 'Original native atom-count metadata required')
                self.members[key] = member
                self.groups[key] = {'member_uid': uid, 'full_inchikey': group}
                self.geometry.setdefault(key, {'native_n_atoms': n, 'geometry_ready': ready})

    def contract(self, dataset, fold):
        require(str(fold) == str(self.contracts[dataset]['fold_id']), 'Only the frozen development fold is available')
        return deepcopy(self.contracts[dataset])

    def view(self, dataset, fold, *, role):
        require(role in ALLOWED_ROLES, 'Outer roles are unavailable')
        return self.contract(dataset, fold)['member_indices'][role]

    def get(self, *args, **kwargs):
        raise SelectedTrainingStoreError('Label-free planning cannot get/decode a target sample')


def select_plan(store, panel, native):
    selection = panel['source_roles']['selection']; cohorts, records, contracts = {}, {}, {}
    for dataset in DATASETS:
        contract = store.contracts[dataset]; fold = contract['fold_id']
        view = GroupedTrainingView(store, dataset, fold, store.groups, seed=selection['seed'],
            max_train_groups=selection['max_train_molecule_groups'],
            max_validation_groups=selection['max_inner_validation_molecule_groups'])
        cohorts[dataset] = view.membership
        wanted = {i for role in ALLOWED_ROLES for i in view.view(role)}
        selected_roles = {i: role for role in ALLOWED_ROLES for i in view.view(role)}
        if dataset == 'expansionrx':
            require(wanted == set(contract['member_indices'][ALLOWED_ROLES[0]]),
                'This existing evaluator requires all official TRAIN metadata for the balanced Expansion split; '
                'the pinned 5326-record source fits the frozen caps, so no official TRAIN record should be removed')
        records[dataset] = [{'member_index': i, 'member_uid': store.members[dataset, i]['member_uid'],
            'original_member': deepcopy(store.members[dataset, i]),
            'original_member_row_sha256': native.canonical(store.members[dataset, i]),
            'full_inchikey': store.groups[dataset, i]['full_inchikey'],
            'selected_role': selected_roles[i],
            'native_n_atoms': store.geometry[dataset, i]['native_n_atoms']}
            for i in sorted(wanted)]
        contracts[dataset] = {**deepcopy(contract),
            'member_indices': {r: [i for i in contract['member_indices'][r] if i in wanted] for r in ALLOWED_ROLES},
            'ordered_members': {r: [store.members[dataset, i]['member_uid'] for i in contract['member_indices'][r] if i in wanted]
                                for r in ALLOWED_ROLES}}
        # An independently reconstructed view over the selected-store contract
        # must reproduce the exact frozen native cohort before labels exist.
        class Replay:
            def contract(self, *_): return deepcopy(contracts[dataset])
            def view(self, *_args, role): return contracts[dataset]['member_indices'][role]
        replay = GroupedTrainingView(Replay(), dataset, fold, store.groups, seed=selection['seed'],
            max_train_groups=selection['max_train_molecule_groups'],
            max_validation_groups=selection['max_inner_validation_molecule_groups'])
        require(all(replay.view(r) == view.view(r) for r in ALLOWED_ROLES), 'Selected-store replay changes chemical membership')
    return {'schema': 'model_v3_label_free_native_selection_v1', 'target_values_decoded': False,
            'cohorts': cohorts, 'records': records, 'contracts': contracts}


def load_context(sources, panel, check=lambda: None):
    require(sources.get('schema') == 'model_v3_existing_downstream_sources_v1'
        and all(sources.get(key) is False for key in ('target_decoding_during_preparation',
            'outer_target_decoding_permitted', 'failed_historical_partial_reuse_permitted',
            'geometry_generation_permitted', 'chemical_identity_recomputation_permitted')),
        'Explicit original-source TRAIN-only controls required')
    native, decoder, graph, implementation_refs = frozen_modules(sources)
    refs = {key: resolved_reference(sources[key]) for key in ('protocol', 'membership_summary', 'expansion_geometry')}
    protocol = native.json_input(refs['protocol'], check=check); native.check_seal(protocol)
    require(protocol.get('state') == 'frozen', 'Original frozen protocol required')
    require(panel.get('status') == 'FROZEN_TASKS_AND_RULES_AWAITING_PHYSICAL_BINDINGS' and len(panel['tasks']) == 9,
            'The frozen nine-task panel is required')
    membership = decoder.OriginalMembership(protocol, refs['membership_summary'], check)
    expansion = native.json_input(refs['expansion_geometry'], check=check)
    require(expansion['membership_summary_sha256'] == refs['membership_summary']['sha256'], 'Geometry/membership source binding differs')
    definitions = {d['dataset_id']: d for d in protocol['downstream']['dataset_definitions']}
    store = OriginalMetadataStore(membership, expansion, definitions, panel, native)
    for task in panel['tasks']:
        require(task['dataset_id'] in DATASETS and task['field'] in store.contracts[task['dataset_id']]['tasks']
                and task['output_level'] == store.contracts[task['dataset_id']]['output_level'], 'Frozen native field/output declaration differs')
    return {'native': native, 'decoder': decoder, 'graph': graph, 'protocol': protocol,
        'membership': membership, 'store': store, 'definitions': definitions,
        'source_refs': refs, 'implementation_refs': implementation_refs, 'sources': sources}


def make_selection_request(context, panel_ref, sources_ref, *, code_sha, preregistration_sha, inventory):
    require(all(re.fullmatch(r'[0-9a-f]{40}', value) for value in (code_sha, preregistration_sha)), 'Full code/preregistration commits required')
    panel = bound_json(panel_ref['path'], panel_ref['sha256'])
    plan = select_plan(context['store'], panel, context['native'])
    return {'schema': 'model_v3_selected_train_materialization_request_v1', 'status': 'FROZEN_LABEL_FREE_SELECTION',
        'panel': panel_ref, 'sources': sources_ref, 'code_sha': code_sha, 'preregistration_sha': preregistration_sha,
        'source_files': inventory, 'selection': plan, 'selection_sha256': canonical(plan),
        'budgets': deepcopy(context['sources']['budgets']), 'outer_target_decoding_permitted': False,
        'failed_partial_reuse_permitted': False, 'complete_for_selected_TRAIN_only': True}


class FrozenSelectedDecoder:
    """Only a frozen selected native (dataset,index,role) reaches source decoding."""
    def __init__(self, context, plan, check=lambda: None):
        self.context, self.plan, self.check = context, plan, check
        self.allowed = {(d, row['member_index']): row for d, rows in plan['records'].items() for row in rows}
        self.graph_frames, self.som_store, self.candidates = {}, None, None
        self.decoded, self._lock = set(), threading.Lock()

    def prepare_numeric_frames(self):
        from phychem_mfm.phase1 import downstream_source_records as records
        ctx = self.context; native, decoder, graph = ctx['native'], ctx['decoder'], ctx['graph']
        self.records = records; self.graph_refs = []
        # Frame bytes for original sources; no numeric conversion occurs here.
        for dataset in ('qm9', 'expansionrx'):
            rows = self.plan['records'][dataset]
            ref = rows[0]['original_member']['assignment_source'] if dataset == 'qm9' else rows[0]['original_member']['source_frame']['source_file']
            native.verify_binding(ref, self.check); content = Path(ref['path']).read_bytes()
            self.graph_refs.append(ref)
            frames = records._csv_rows(content, with_spans=True)
            _, _, header, _ = next(frames); names = tuple(graph._text(v) for v in header)
            require(len(names) == len(set(names)) and all(t in names for t in self.plan['contracts'][dataset]['tasks']),
                    'Original numeric source header/tasks differ')
            wanted = {row['member_index'] for row in rows}
            for index, frame in enumerate(frames):
                self.check()
                if index in wanted:
                    self.graph_frames[dataset, index] = (ref, content, names, frame)
            require(all((dataset, i) in self.graph_frames for i in wanted), 'Selected native numeric frame absent')

    def prepare(self):
        self.prepare_numeric_frames()
        ctx = self.context; native, decoder = ctx['native'], ctx['decoder']; records = self.records
        # These source/geometry constructors are target opaque. All annotation
        # functions are called later through the native allowlist guard.
        member = ctx['membership']
        som_ref = decoder.artifact_input(member.summary, 'full_som_structures_4511893/summary.json')
        som = native.json_input(som_ref, check=self.check)
        sources, folds = [], []
        for name in ('cyp_sources', 'cyp_folds'):
            legacy = som['ledgers'][name]
            ref = decoder.closed_som_ledger_binding(legacy, name=name, summary_ref=som_ref, check=self.check)
            values = decoder.jsonl(ref, maximum_rows=3000, check=self.check)
            require(len(values) == legacy['rows'], 'Original CYP ledger count differs')
            (sources if name.endswith('sources') else folds).extend(values)
        raw_sources = [ref for key, ref in som['sources'].items() if key.startswith('cyp_raw/')]
        require(len(raw_sources) == 9, 'Exact original nine CYP source files required')
        self.som_store = records.SourceRecordStore(ctx['sources']['benchmark_root'], source_files={Path(ref['path']).name:
            {k: ref[k] for k in ('bytes', 'sha256')} for ref in raw_sources}, source_rows=sources, member_rows=folds)
        candidate_ref = decoder.artifact_input(member.summary, 'missing_geometry_stage34_4511904/candidate_records.jsonl')
        self.candidates = records.ClosedCandidateLedger(candidate_ref['path'], expected_sha256=candidate_ref['sha256'])
        self.extra_refs = [som_ref, candidate_ref, *raw_sources, *self.graph_refs]
        from rdkit import Chem, rdBase
        from phychem_mfm.phase1.som_atom_mapping import build_cyp_author_atom_mapping
        from phychem_mfm.phase1.som_annotation import decode_cyp_primary_annotation
        from phychem_mfm.phase1.az_atom_mapping import build_az_author_atom_mapping
        from phychem_mfm.phase1.az_annotation import parse_az_exact_groups
        from .v3_source_sample_compat import CompatibleSourceRecords
        self.som_modules = (CompatibleSourceRecords(records), Chem, rdBase, build_cyp_author_atom_mapping, decode_cyp_primary_annotation,
                            build_az_author_atom_mapping, parse_az_exact_groups)

    def decode(self, dataset, index, *, role):
        key = dataset, index; row = self.allowed.get(key)
        require(role in ALLOWED_ROLES and row is not None and role == row['selected_role'],
                'Target decoding outside the sealed selected TRAIN/native role allowlist')
        with self._lock:
            require(key not in self.decoded, 'Each selected source target record may be decoded only once')
            self.decoded.add(key)
        self.check(); ctx = self.context; native, decoder, graph = ctx['native'], ctx['decoder'], ctx['graph']
        member = row['original_member']; tasks = self.plan['contracts'][dataset]['tasks']
        require(native.canonical(member) == row['original_member_row_sha256'], 'Selected member-row SHA differs before decode')
        if dataset == 'cyp_isoform':
            result = decoder.som_payload(member, self.som_store, self.candidates, tasks, self.som_modules)
            x, coords, targets, candidate, supervision, state, proof = result
            require(state != 'MALFORMED', 'Malformed original annotation cannot become unknown supervision')
            geometry_status = member['geometry_artifact_ref']['status']
            require(geometry_status in ('GEOMETRY_READY', 'NOT_READY')
                and (coords is not None) == (geometry_status == 'GEOMETRY_READY'),
                'CYP decoded coordinate availability differs from the original native geometry status')
        else:
            ref, content, names, (start, end, fields, spans) = self.graph_frames[key]
            bucket = 'expansionrx_train' if dataset == 'expansionrx' else dataset
            join = graph._joined_member(bucket, member, index+1, fields, names, spans, start, end, content, ref)
            if dataset == 'qm9':
                from phychem_mfm.phase1.downstream_structures import read_xyz_structure
                f = member['source_frame']; native.verify_binding(f, self.check)
                structure = read_xyz_structure(f['path'], units=ctx['definitions'][dataset]['source_coordinate_unit'])
                old = member['geometry_artifact_ref']
                require(structure.n_atoms == f['native_n_atoms']
                    and structure.provenance['source_atomic_number_order_hash'] == f['source_native_order_sha256']
                    and native.canonical(structure.source_atom_map) == old['source_atom_map_hash']
                    and native.canonical({'source_units': ctx['definitions'][dataset]['source_coordinate_unit'],
                        'coordinate_scale': structure.provenance['coordinate_scale'], 'atomic_numbers': structure.atomic_numbers,
                        'pos_angstrom': structure.pos_angstrom}) == old['coordinate_projection_hash'],
                    'Original native XYZ geometry/order binding differs before target decode')
                x, coords, geometry_proof = structure.x, structure.pos_angstrom, structure.provenance
            else:
                g = ctx['store'].geometry[key]; native.check_seal(g)
                require(g['member_row_sha256'] == native.canonical(member), 'Expansion geometry/member-row SHA differs before decode')
                x, coords, geometry_proof = g['native_x'], g['native_coordinates_float64'], g
            values = [decoder.observed_scalar(fields[names.index(task)], graph.NUMERIC) for task in tasks]
            targets = [[v for v, _ in values]]; candidate = [[True]*len(tasks)]; supervision = [[s for _, s in values]]
            state = 'OBSERVED_OR_UNKNOWN_NUMERIC'
            proof = {'source_join': join, 'source_file': ref, 'raw_frame_sha256': hashlib.sha256(content[start:end]).hexdigest(),
                'target_field_byte_hashes': {task: hashlib.sha256(fields[names.index(task)]).hexdigest() for task in tasks},
                'selected_target_numeric_recipe': decoder.NUMERIC_RECIPE, 'target_conversion': 'none',
                'native_geometry': deepcopy(geometry_proof), 'source_member_geometry_join_before_target_decode': True}
        require(len(x) == row['native_n_atoms'], 'Selected native atom cardinality changed')
        return {'x': tuple(x), 'coordinates': coords, 'targets': targets, 'candidate': candidate, 'supervision': supervision,
                'annotation_state': state, 'source_proof': proof}


def ordered_bounded_map(function, jobs, *, workers):
    require(type(workers) is int and 1 <= workers <= 16, 'At most 16 bounded materialization workers are supported')
    iterator = iter(jobs); pending = deque()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in range(2*workers):
            try: pending.append(pool.submit(function, next(iterator)))
            except StopIteration: break
        while pending:
            yield pending.popleft().result()
            try: pending.append(pool.submit(function, next(iterator)))
            except StopIteration: pass


def publish_selected_store(plan, native, decode, *, output, request_ref, source_contracts, definitions,
                           protocol, workers=16, check=lambda: None, close_source=lambda: None):
    """Write a new native store in fixed source order; no inherited partials."""
    output = Path(output); require(output.is_dir() and not any(output.iterdir()), 'Fresh empty selected-store output required')
    path = output / 'records.bin'; rows, groups, proofs = [], [], []
    jobs = [(dataset, row) for dataset in DATASETS for row in plan['records'][dataset]]
    def one(job):
        dataset, row = job
        return dataset, row, decode(dataset, row['member_index'], role=row['selected_role'])
    with path.open('xb') as stream:
        stream.write(native.RECORD_MAGIC)
        for dataset, source, actual in ordered_bounded_map(one, jobs, workers=workers):
            check()
            require(actual['annotation_state'] != 'MALFORMED', 'Malformed source cannot publish a successful selected store')
            raw = native.record_bytes(actual['x'], actual['coordinates'], actual['targets'], actual['candidate'], actual['supervision'])
            row = {'dataset_id': dataset, 'member_index': source['member_index'], 'member_uid': source['member_uid'],
                'native_n_atoms': len(actual['x']), 'target_rows': len(actual['targets']),
                'tasks': plan['contracts'][dataset]['tasks'], 'geometry_ready': actual['coordinates'] is not None,
                'offset': stream.tell(), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            require(row['native_n_atoms'] == source['native_n_atoms'], 'Packed source native atom count changed')
            stream.write(raw); rows.append(row)
            groups.append({k: source[k] for k in ('member_index', 'member_uid', 'full_inchikey')} | {'dataset_id': dataset})
            proofs.append({'dataset_id': dataset, 'member_index': source['member_index'], 'selected_role': source['selected_role'],
                'original_member_row_sha256': source['original_member_row_sha256'], 'source_proof': actual['source_proof']})
        stream.flush(); os.fsync(stream.fileno())
    payload_ref = binding(path)
    index_ref = write_json(output / 'record_index.json', {'schema': 'model_v3_selected_TRAIN_native_index_v1', 'records': rows})
    proof_ref = write_json(output / 'source_proofs.json', {'records': proofs, 'selected_numeric_or_annotation_values_written': False})
    contracts = []
    for dataset in DATASETS:
        contract = deepcopy(plan['contracts'][dataset]); contract['source_contract_sha256'] = source_contracts[dataset]['sha256']
        contracts.append(contract)
    contract_ref = write_json(output / 'contracts.json', {'contracts': contracts})
    manifest = {'schema': 'model_v3_selected_TRAIN_store_manifest_v1', 'complete': True,
        'closure_scope': 'complete_for_selected_TRAIN', 'historical_full_store_claimed': False,
        'selection_request': request_ref, 'selection_sha256': canonical(plan), 'records_file': payload_ref,
        'record_index': index_ref, 'contracts': contract_ref, 'source_proofs': proof_ref,
        'source_contracts': source_contracts, 'records': len(rows), 'outer_target_records_decoded': 0,
        'new_geometry_or_chemical_identity_generated': False,
        'native_units': {dataset: units_for(definitions[dataset], protocol) for dataset in DATASETS}}
    manifest_raw = encoded(manifest)+b'\n'
    manifest_ref = {'path': str(output / 'selected_store_manifest.json'), 'bytes': len(manifest_raw),
                    'sha256': hashlib.sha256(manifest_raw).hexdigest()}
    document = {'schema': 'model_v3_training_role_store_v1', 'source_complete': True,
        'closure_scope': 'complete_for_selected_TRAIN', 'source_kind': 'new_model_side_frozen_source_TRAIN_materialization',
        'historical_full_store_claimed': False, 'targets_in_metadata': False, 'native_record_hashes_preserved': True,
        'native_record_hash_origin': 'new closed selected-TRAIN index; no historical failed partial used',
        'source_store_manifest_sha256': manifest_ref['sha256'],
        'data_version': 'selectedTRAIN-v1-'+request_ref['sha256'][:16]+'-'+manifest_ref['sha256'][:16],
        'records_file': payload_ref, 'records': rows, 'contracts': contracts, 'molecule_groups': groups,
        'selected_store_manifest': manifest_ref}
    # Validate a deliberately named pending projection before publishing any
    # complete source manifest or final consumable sidecar. Preserve it later.
    sidecar_ref = write_json(output / 'training_store.PENDING.json', document)
    store = TrainOnlyPackedStore(sidecar_ref['path'], sidecar_ref['sha256'])
    for dataset in DATASETS:
        selection = plan['cohorts'][dataset]
        view = GroupedTrainingView(store, dataset, selection['source_fold_id'], store.group_map,
            seed=selection['seed'], max_train_groups=selection['caps'][ALLOWED_ROLES[0]],
            max_validation_groups=selection['caps'][ALLOWED_ROLES[1]])
        require(all(list(view.view(role)) == [r['member_index'] for r in selection['roles'][role]] for role in ALLOWED_ROLES),
                'Published selected-store replay changes the sealed cohort')
    check(); close_source(); check()
    require(write_json(output / 'selected_store_manifest.json', manifest) == manifest_ref,
            'Final selected-store manifest bytes differ')
    sidecar_ref = write_json(output / 'training_store.json', document)
    return {'status': 'COMPLETE_FOR_SELECTED_TRAIN', 'training_store': sidecar_ref, 'manifest': manifest_ref,
            'records': len(rows), 'outer_target_records_decoded': 0, 'cohort_replay_exact': True}


def validate_selection_request(context, request, panel):
    require(request.get('schema') == 'model_v3_selected_train_materialization_request_v1'
            and request.get('status') == 'FROZEN_LABEL_FREE_SELECTION'
            and request.get('outer_target_decoding_permitted') is False
            and request.get('failed_partial_reuse_permitted') is False
            and request.get('complete_for_selected_TRAIN_only') is True, 'Sealed label-free selection request required')
    require(request['budgets'] == context['sources']['budgets'], 'Materialization budget differs from its source request')
    require(canonical(request['selection']) == request['selection_sha256'], 'Selection content SHA differs')
    rebuilt = select_plan(context['store'], panel, context['native'])
    require(rebuilt == request['selection'], 'Source/member/chemical selection changed before target decode')
    return rebuilt


class MaterializationBudget:
    def __init__(self, budgets, output):
        require(type(budgets['workers']) is int and 1 <= budgets['workers'] <= 16
            and 60 <= budgets['maximum_wall_seconds'] <= 7200
            and 0 < budgets['maximum_rss_bytes'] <= 48*1024**3
            and 0 < budgets['maximum_output_bytes'] <= 2*1024**3, 'Explicit bounded CPU materialization budgets required')
        self.values, self.output, self.started = budgets, Path(output), time.monotonic()
        self.last_output_check, self.lock = 0., threading.Lock()

    def check(self, *, force=False):
        import resource
        elapsed = time.monotonic()-self.started
        require(elapsed < self.values['maximum_wall_seconds']-30, 'Materialization wall budget exhausted; preserve partial output')
        require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 <= self.values['maximum_rss_bytes'], 'Materialization RSS cap exceeded')
        if force or elapsed-self.last_output_check > 10:
            with self.lock:
                if force or elapsed-self.last_output_check > 10:
                    files = [p for p in self.output.rglob('*') if p.is_file()]
                    require(all(not p.is_symlink() for p in files)
                        and sum(p.stat().st_size for p in files) <= self.values['maximum_output_bytes'], 'Materialization output cap exceeded')
                    self.last_output_check = elapsed


def require_owned_cpu_allocation(output):
    require(os.getuid() == 1278 and os.environ.get('SLURM_JOB_ID')
        and int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) >= 16, 'The root coordinator must provide an owned >=16 CPU Slurm allocation')
    output = Path(output).absolute()
    require(not output.resolve().is_relative_to(ROOT.resolve()), 'Model-side data/H0 products must stay outside the source tree')
    require(not output.exists(), 'A fresh external output directory is required')
    output.mkdir(parents=True, exist_ok=False)
    return output


def close_context(context, decoder=None):
    refs = [*context['source_refs'].values(), *context['implementation_refs'].values(), *context['membership'].inputs]
    if decoder is not None:
        refs += decoder.extra_refs
        refs += [row['original_member']['source_frame'] for row in decoder.plan['records']['qm9']]
    unique = {ref['path']: ref for ref in refs}
    def verify(ref):
        context['native'].verify_binding(ref)
    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(verify, unique.values()))
