#!/bin/bash
#SBATCH --job-name=C1-reference-features-empty-startup-continuation
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-[0-7,14,18,20-22]
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=06:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_Pprime_reference_binding_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import sys, types
package = types.ModuleType('workflows.benchmark_evaluation')
package.__path__ = []
sys.modules[package.__name__] = package
module = types.ModuleType('workflows.benchmark_evaluation.pprime_features')
module.__package__ = package.__name__
sys.modules[module.__name__] = module
exec(compile('"""Read unchanged pretraining P fields from sealed native P-prime outcomes.\n\nNo quantum execution, conformer selection by success, value filling, unit\nconversion, averaging, or new physical masks are performed here.\n"""\nimport math\nimport numpy as np\nfrom workflows.data_v1_final.labels.common import component_values, MISSING\n\nclass NativePprimeLayout:\n    def __init__(self, schema, lookup):\n        self.lookup = lookup\n        self.molecule = [dict(c) for c in schema["columns"]["mol_labels"]\n                         if c["field_key"].startswith("P.")]\n        self.atom = [dict(c) for c in schema["columns"]["atom_labels"]\n                     if c["field_key"].startswith("P.")]\n        if not self.molecule or not self.atom:\n            raise ValueError("Original pretraining P scalar columns are required")\n        for column in self.molecule + self.atom:\n            key = column["field_key"].split(".")\n            if len(key) < 4 or not key[1] or not column["source_path"] or not column["unit"]:\n                raise ValueError("Original P field task, source path and unit are required")\n            column["native_task"] = key[1]\n\n    def extract(self, result, n_atoms):\n        if type(n_atoms) is not int or n_atoms <= 0:\n            raise ValueError("Original geometry atom count is required")\n        if result.get("Pprime_ready") is not True:\n            return None, None, {"status": "NATIVE_PPRIME_UNAVAILABLE", "state": result.get("state")}\n        tasks = {}\n        for detail in result["tasks"]:\n            name = detail["task"]\n            if name in tasks:\n                raise ValueError("A native quantum task is duplicated")\n            tasks[name] = detail\n        molecule = np.full(len(self.molecule), np.nan, dtype=np.float64)\n        atom = np.full((n_atoms, len(self.atom)), np.nan, dtype=np.float64)\n        issues = []\n        for kind, columns in (("molecule", self.molecule), ("atom", self.atom)):\n            for index, column in enumerate(columns):\n                detail = tasks.get(column["native_task"])\n                if detail is None or detail.get("scope_status", detail.get("status")) != "SUCCESS":\n                    issues.append({"field": column["field_key"], "reason": "NATIVE_TASK_MISSING_OR_FAILED"})\n                    continue\n                value = self.lookup(detail, column["source_path"])\n                field = {name: column[name] for name in ("source_path", "component", "level")}\n                values, indices, reason = component_values(field, value, n_atoms)\n                if reason is not None:\n                    issues.append({"field": column["field_key"], "reason": reason})\n                    continue\n                if column["registry_id"] in (detail.get("numeric_issues") or []):\n                    issues.append({"field": column["field_key"], "reason": "SOURCE_NUMERIC_ISSUE"})\n                    continue\n                if kind == "molecule":\n                    if len(values) != 1 or indices != [None]:\n                        raise ValueError("Original molecular P component no longer has a scalar layout")\n                    if type(values[0]) in (int, float) and math.isfinite(values[0]):\n                        molecule[index] = values[0]\n                else:\n                    if len(values) != len(indices) or len(set(indices)) != len(indices):\n                        raise ValueError("Original atomic P source indices are incomplete or duplicated")\n                    for native_index, scalar in zip(indices, values):\n                        if type(native_index) is not int or not 0 <= native_index < n_atoms:\n                            raise ValueError("Native P atom index is outside the original geometry")\n                        if type(scalar) in (int, float) and math.isfinite(scalar):\n                            atom[native_index, index] = scalar\n        return molecule, atom, {"status": "NATIVE_PPRIME_COMPONENTS_BOUND",\n                                "native_missing_components": issues}\n\ndef first_actual_conformer(source):\n    """Use producer order and the actual ID; never look for a later successful P-prime."""\n    conformers = (source.get("result") or {}).get("conformers") or []\n    if not conformers:\n        return None\n    first = conformers[0]\n    if first.get("geometry_source") != "UFF_Sprime" or first.get("converged") is not True:\n        raise ValueError("The first delivered geometry is not an accepted native UFF conformer")\n    return int(first["conformer_id"])\n\ndef remap_to_original_atoms(atom_features, model_atom_to_source, original_atom_count):\n    """Missing source atom mappings remain NaN; never assign a predicted pKa site."""\n    if atom_features is None:\n        return None\n    values = np.asarray(atom_features, dtype=np.float64)\n    if values.ndim != 2 or len(model_atom_to_source) != len(values):\n        raise ValueError("Original geometry atom map and P-prime rows differ")\n    output = np.full((original_atom_count, values.shape[1]), np.nan, dtype=np.float64)\n    used = set()\n    for model_index, source_index in enumerate(model_atom_to_source):\n        if source_index is None or source_index == -1:\n            continue\n        if type(source_index) is not int or not 0 <= source_index < original_atom_count or source_index in used:\n            raise ValueError("Source atom mapping is not an unambiguous original atom identity")\n        used.add(source_index)\n        output[source_index] = values[model_index]\n    return output\n\ndef append_unmapped_native_hydrogens(model_atom_to_source, native_atomic_numbers):\n    """The native AddHs operation appends H; it does not invent source atom IDs."""\n    mapping = list(model_atom_to_source)\n    if len(mapping) > len(native_atomic_numbers):\n        raise ValueError("Source atom map is longer than the actual native geometry")\n    if any(z != 1 for z in native_atomic_numbers[len(mapping):]):\n        raise ValueError("An unmapped appended native atom is not hydrogen")\n    return mapping + [None] * (len(native_atomic_numbers)-len(mapping))\n', module.__name__, 'exec'), module.__dict__)
import importlib.util, json, math, os
from collections import Counter, OrderedDict
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem
from workflows.benchmark_data.shared_reader import SharedB0Reader
from workflows.benchmark_data.pprime_reader import PprimeReader
from workflows.benchmark_data.shared_access import check_access
from workflows.benchmark_data.admission import protect
from workflows.benchmark_evaluation.pprime_features import NativePprimeLayout, first_actual_conformer, remap_to_original_atoms, append_unmapped_native_hydrogens
from workflows.data_v1_final.labels.common import MISSING
entry = json.loads('{\n  "schema": "BENCHMARK_B0_AVAILABLE_DELIVERY_ENTRY_V1",\n  "status": "D_AVAILABLE_DIRECTIVE19_UNIFORM_SPRIME_SEALED_PPRIME_IN_PROGRESS",\n  "authority": "docs/benchmark/USER_DIRECTIVE_20261118.md@07be7a0f04085398eeda2b7548afa46c668ffd9a",\n  "data_root": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119",\n  "manifest": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/delivery/directive19_current_counts_4537016/manifest.json",\n  "domain_counts_csv": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/delivery/directive19_current_counts_4537016/domain_counts.csv",\n  "handoff_native_job": 4537016,\n  "handoff_native_state": "COMPLETED",\n  "handoff_native_exit": "0:0",\n  "source_groups": 11,\n  "domain_count_rows": 12,\n  "Pprime_current_job": 4536588,\n  "Pprime_current_node": "compute-0-12",\n  "Pprime_current_workers": 8,\n  "Pprime_followup_jobs": [\n    4536590\n  ],\n  "Pprime_all_ready": false,\n  "S_ready": false,\n  "P_ready": false,\n  "reference_quantum_status": "Downstream uniformly uses shared UFF Sprime; C1 property groups use Pprime; historical reference XYZ retained as provenance",\n  "no_local_database_copies": true,\n  "all_required_production_complete": false,\n  "supplemental_sources": {\n    "SAMPL6_7": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/provenance/SAMPL6_7/job_4536607/manifest.json",\n    "ExpansionRx_official_release": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/raw/ExpansionRx_official_release/job_4536975/manifest.json"\n  },\n  "active_evaluation_scope": {\n    "status": "B1_AND_LATER_SCOPE_EXCLUDES_FIVE_DEFERRED_ENDPOINTS",\n    "decision_date": "2026-11-19",\n    "endpoint_registry": "configs/benchmark_data/B1.deferred_tasks.json",\n    "selector": "workflows.benchmark_data.task_selection.select_active_tasks",\n    "strict_full_inventory_verification": true,\n    "expected_deferred_endpoint_count": 5,\n    "effective_at": "B1_TASK_INVENTORY_BEFORE_MODEL_FITS",\n    "b0_source_data_and_provenance": "UNALTERED",\n    "failure_policy": "BLOCK_B1_UNTIL_ALL_FIVE_DEFERRED_IDENTIFIERS_MATCH",\n    "scope_authority_commit": "fec1b994aa642ba8db74074134f909dcb4f165f0",\n    "full_inventory_verification": "REQUIRED_BEFORE_B1_FITTING_NOT_PERFORMED_BY_B0"\n  },\n  "directive19_resolutions": {\n    "authority_commit": "6d056a41f379b921d31017ecfed9ce84d1a5c71a",\n    "directive": "docs/benchmark/USER_DIRECTIVE_20261119.md",\n    "pka": {\n      "main": "molecular_macro_strongest_acid_and_strongest_base",\n      "mechanism": "uniquely_identifiable_single_ionization_site_only",\n      "single_site_evidence_required": true,\n      "predicted_microspecies_are_experimental": false,\n      "multisite_microscopic_assignment": false,\n      "SAMPL_exclusion": "complete_InChIKey; challenge_plus_local_ID"\n    },\n    "nmr": {\n      "split": "nmrshiftdb2-2018; Jonas_Kuhn_2019; Kwon_2020",\n      "prefer_author_split": true,\n      "published_test_molecule_count_match_required": true,\n      "CSTShift": "DFT_input_reference_upper_bound_only"\n    },\n    "geometry": {\n      "downstream": "uniform_Sprime_UFF",\n      "PM7_optimizer": "DO_NOT_RECONSTRUCT_OR_TRIAL",\n      "C1_property_group": "Pprime; explicitly_named_Pprime",\n      "Pprime_access": "corresponding_dataset_producer_sealed"\n    },\n    "seeds": {\n      "default": 1,\n      "second": "final_significant_improvement_or_specified_training_rollback_instability"\n    },\n    "B1_branch": "benchmark-b1-20261119",\n    "data_preparation_complete": false\n  },\n  "directive19_data_preparation": {\n    "NMR2018_author_split": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/NMR2018/job_4536853/manifest.json",\n    "NMR2018_targets": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/NMR2018/job_4536887/manifest.json",\n    "pKahub_macro_targets": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/pKahub/job_4536891/manifest.json",\n    "uniform_Sprime_scope": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/uniform_Sprime/geometry/shared_v1/queue.manifest.json",\n    "uniform_scope_ready": true,\n    "pKa_atomic_site_evidence_ready": false,\n    "NMR2018_published_test_count_reconciliation": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/NMR2018/job_4536946/manifest.json",\n    "NMR2018_test_molecule_counts_matched": true,\n    "pKa_single_site_definition_proposal": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/pKahub/job_4536942/manifest.json",\n    "pKa_single_site_definition_approval": "PENDING_USER_REPLY; proposal is not a training-label entry"\n  },\n  "active_target_manifests": {\n    "NMRShiftDB2": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/NMR2018/job_4536887/manifest.json",\n    "pKahub": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/pKahub/job_4536891/manifest.json"\n  },\n  "uniform_Sprime_producer": {\n    "job": 4536924,\n    "native_state": "COMPLETED",\n    "node": "compute-0-17",\n    "workers": 2,\n    "producer_progress_observed": true,\n    "previous_bootstrap_job": 4536898,\n    "previous_bootstrap_state": "FAILED",\n    "previous_bootstrap_exit": "9:0",\n    "previous_bootstrap_scientific_calls": 0,\n    "source_UFF_job": 4536924,\n    "D3_alignment_postprocessing_job": 4536978,\n    "geometry_generation_complete": true,\n    "D3_alignment_postprocessing_state": "COMPLETED/0:0",\n    "effective_source_final_writer_job": 4536978,\n    "outcome_counts": {\n      "D20_READY_NO_ACCEPTED_CONFORMERS": 656,\n      "D20_READY_STEREO_REFERENCE_UNAVAILABLE": 14285,\n      "D20_READY_UFF_UNSUPPORTED": 11,\n      "SPRIME_AND_D_READY": 23287,\n      "SPRIME_READY_D_PARTIAL": 1\n    }\n  },\n  "uniform_Pprime_chain": {\n    "prepare_job": 4536979,\n    "producer_jobs": [\n      4536906,\n      4536907\n    ],\n    "source_geometry_native_C0_required": true,\n    "ready": false,\n    "source_geometry_job": 4536978,\n    "queued_actual_conformers": 53896,\n    "source_geometry_sealed": true,\n    "prepare_native_state": "COMPLETED/0:0",\n    "current_workers": 8,\n    "current_job": 4536906,\n    "current_native_state": "RUNNING",\n    "observed_intents": 8,\n    "current_node": "compute-0-17",\n    "observed_CST": "2026-11-20T11:02:12+08:00",\n    "observed_pending": 49311,\n    "producer_progress_observed": true,\n    "observed_ready": 4574,\n    "producer_log": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B0_uniform_pprime_4536906.log",\n    "cross_node_read_allowed": false,\n    "observed_partial": 3\n  },\n  "both_scopes_final_handoff": {\n    "job": 4536961,\n    "native_state": "PENDING",\n    "submitted_afterok_jobs": [\n      4536963,\n      4536599,\n      4536907\n    ],\n    "manifest": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/delivery/final_all_scopes_4536961/manifest.json",\n    "production_closed": false,\n    "all_required_work_complete": false,\n    "metadata_only_no_SQLite_replay": true\n  },\n  "D3_source_alignment_recovery": {\n    "status": "SOURCE_UFF_AND_D3_REPAIR_CLOSED_GEOMETRY_SEALED",\n    "recorded_error_metadata_job": 4536970,\n    "unit_test_job": 4536974,\n    "source_check_job": 4536976,\n    "repair_job": 4536978,\n    "source_UFF_job": 4536924,\n    "source_seal_prepare_job": 4536979,\n    "superseded_zero_start_prepare_job": 4536925,\n    "successful_labels_and_source_coordinates_unchanged": true,\n    "original_failure_history_preserved": true,\n    "genuine_scientific_failure_retry": false,\n    "recorded_error_confirmed": true,\n    "unit_tests_passed": 6,\n    "source_check_status": "PASS",\n    "source_check_files": 5264,\n    "source_sealed": true,\n    "repair_native_state": "COMPLETED/0:0",\n    "remaining_partial_molecules": 1,\n    "repair_complete": true,\n    "repair_outcomes": {\n      "D3_REPAIRED": 41243\n    }\n  },\n  "Pprime_previous_closed_job": {\n    "job": 4536581,\n    "native_state": "COMPLETED",\n    "native_exit": "0:0",\n    "INTENT": 0,\n    "outcome_counts": {\n      "PENDING": 164875,\n      "PPRIME_PARTIAL_WITH_RECORDED_OUTCOMES": 157,\n      "PPRIME_READY": 160048\n    }\n  },\n  "Pprime_standby": {\n    "job": 4536991,\n    "previous_job": 4536588,\n    "followup_job": 4536590,\n    "native_state": "PENDING",\n    "scientific_calls": 0,\n    "acceptance_written": false,\n    "exclude_unrecovered_node18": true,\n    "superseded_zero_native_candidate": 4536722,\n    "exclude_uniform_active_node": "compute-0-17",\n    "exclusion_until": "Uniform scope tmpfs writer closed; both8+16 scratch peaks exceed actual node17 tmpfs",\n    "uniform_tail_must_exclude_allocated_standby_node_before_accept": true,\n    "scientific_record_grace_unchanged": true,\n    "native_TimeLimit_hours": 24,\n    "native_TimeMin_hours": 6,\n    "actual_speedup_not_yet_observed": true,\n    "previous_native_TimeMin_hours": 12,\n    "TimeMin_update_at_verified_pending_zero_runtime": true\n  },\n  "active_source_count_handoff": {\n    "historical_domain_table_preserved": true,\n    "unit_tests_and_source_check_pending": false,\n    "native_state": "COMPLETED/0:0",\n    "job": 4537016,\n    "source_check_files": 5265,\n    "unit_tests_passed": 3,\n    "source_check_python_files": 3736,\n    "source_check_errors": 0\n  },\n  "active_domain_counts_csv": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/delivery/directive19_current_counts_4537016/active_source_domain_counts.csv",\n  "historical_domain_counts_csv": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/delivery/directive19_current_counts_4537016/domain_counts.csv"\n}\n')
root = Path(entry['data_root'])
b1 = root.parent / 'benchmark_B1_20261119'
quota = Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')

def safe():
    protect(root, 2147483648, quota, own_concurrent_bytes=40 * 1024 ** 3)
scope_path = Path(entry['directive19_data_preparation']['uniform_Sprime_scope'])
scope = json.loads(scope_path.read_text())
geometry_queues = (scope['reused_source_queue'], scope['queue'])
quantum_queues = (str(root / 'labels/Pprime/shared_v1/queue.sqlite'), str(root / 'directive19/uniform_Sprime/labels/Pprime/shared_v1/queue.sqlite'))
queue_pairs = dict(zip(geometry_queues, quantum_queues))
for path in tuple(geometry_queues) + tuple(quantum_queues):
    declaration = check_access(path)
    if not declaration or not declaration.get('immutable') or (not declaration.get('cross_node_read_allowed')):
        raise RuntimeError('Both actual native Pprime scopes must be sealed before reference/atomic C1 consumption')
schema_path = Path('/lfshome/zixiao/data_v1_20261025/D3_v31_pilot_20261105_v1/schema.json')
pretraining = json.loads(schema_path.read_text())
wire_path = Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts/wp5_parquet_v2.py')
spec = importlib.util.spec_from_file_location('_original_pretraining_wp5_wire_reference', wire_path)
wire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wire)

def lookup(detail, path):
    value = wire.lookup(detail, path)
    return MISSING if value is wire.MISSING else wire.native(value)
layout = NativePprimeLayout(pretraining, lookup)
safe()
out = b1 / 'C1_Pprime_reference_features/job_4537149'
out.mkdir(parents=True)
groups = ('Pprime', 'Pprime_plus_D')
for name in groups:
    (out / name).mkdir()
(out / 'B0.DELIVERY.json').write_text(json.dumps(entry, indent=2) + '\n')
routes = {}
for route in pq.read_table(scope['geometry_bindings']).to_pylist():
    key = (route['dataset'], route['record_id'])
    if key in routes:
        raise ValueError('Duplicate original geometry route')
    if route['shared_geometry_queue'] not in queue_pairs:
        raise ValueError('Undeclared shared geometry queue')
    routes[key] = route
geometry_readers = {p: SharedB0Reader(p) for p in geometry_queues}
quantum_readers = {p: PprimeReader(p) for p in quantum_queues}
cache = OrderedDict()

def native_features(dataset, record_id, original_atom_count=None):
    route = routes.get((dataset, record_id))
    if route is None:
        return (None, None, 'NO_NATIVE_SOURCE_GEOMETRY_ROUTE', None)
    queue = route['shared_geometry_queue']
    geometry = geometry_readers[queue].get(route['shared_geometry_dataset'], route['shared_geometry_record_id'])
    cid = first_actual_conformer(geometry)
    if cid is None:
        return (None, None, geometry['state'], None)
    key = (queue, geometry['shared_molecule_id'], cid)
    if key in cache:
        molecular, atomic, state = cache.pop(key)
    else:
        result = quantum_readers[queue_pairs[queue]].get(key[1], cid)
        molecular, atomic, _ = layout.extract(result, len(geometry['result']['atomic_numbers']))
        state = result['state']
    cache[key] = (molecular, atomic, state)
    while len(cache) > 1024:
        cache.popitem(last=False)
    if original_atom_count is not None and atomic is not None:
        mapping = append_unmapped_native_hydrogens(route['model_atom_to_source'], geometry['result']['atomic_numbers'])
        atomic = remap_to_original_atoms(atomic, mapping, original_atom_count)
    return (None if molecular is None or not np.isfinite(molecular).any() else molecular.tolist(), atomic, state, cid)
reports = []
try:
    for dataset in ('C7H10O2', 'PPE1694'):
        parent = b1 / 'C1_uniform_D_features/job_4537119' / (dataset + '_cv_binding.json')
        binding = json.loads(parent.read_text())
        oldspec = next((s for s in binding['source_groups'] if s['dataset'] == dataset))
        source = pq.read_table(oldspec['features'])
        schema = pa.schema(list(source.schema) + [pa.field('features', pa.list_(pa.float64())), pa.field('native_Pprime_state', pa.string()), pa.field('native_UFF_conformer_id', pa.int32())])
        buffers = {name: [] for name in groups}
        counts = Counter()
        for row in source.to_pylist():
            p, _, state, cid = native_features(dataset, row['record_id'])
            d = row['D_features']
            counts[state] += 1
            for name in groups:
                vector = p if name == 'Pprime' else p + d if p is not None and d is not None and any((math.isfinite(v) for v in d)) else None
                buffers[name].append(dict(row, features=vector, native_Pprime_state=state, native_UFF_conformer_id=cid))
            if sum(counts.values()) % 128 == 0:
                safe()
        for name in groups:
            target = out / name / (dataset + '.parquet')
            safe()
            pq.write_table(pa.Table.from_pylist(buffers[name], schema=schema), target, compression='zstd')
            new_spec = dict(oldspec, features=str(target), C1_feature_group=name, C1_feature_vector_field='features', C1_native_P_schema=str(schema_path))
            result = dict(binding, source_groups=[new_spec], source_entry=str(out / 'B0.DELIVERY.json'), native_Pprime_queues=list(quantum_queues), original_labels_and_scaffold_folds_unchanged=True)
            path = out / name / (dataset + '_cv_binding.json')
            path.write_text(json.dumps(result, indent=2) + '\n')
            reports.append(dict(dataset=dataset, feature_group=name, cv_binding=str(path), source_records=len(buffers[name]), native_quantum_states=dict(counts)))
        print('C1_PPRIME_REFERENCE_GROUP_CLOSED', dataset, dict(counts), flush=True)
    joung_binding_path = b1 / 'Joung_gas_context/job_4537021/manifest.json'
    joung_binding = json.loads(joung_binding_path.read_text())
    oldspec = joung_binding['source_groups'][0]
    source = pq.read_table(oldspec['features'])
    schema = pa.schema(list(source.schema) + [pa.field('features', pa.list_(pa.float64())), pa.field('native_Pprime_state', pa.string())])
    parent = b1 / 'C1_Pprime_features/job_4537124/Pprime/Joung2020.parquet'
    pvalues = {r['record_id']: r for r in pq.read_table(parent).to_pylist()}
    buffers = {name: [] for name in groups}
    counts = Counter()
    for row in source.to_pylist():
        native = pvalues.get(row['record_id'])
        p = None if native is None else native['features']
        state = 'NATIVE_PPRIME_ROW_ABSENT' if native is None else native['feature_state']
        counts[state] += 1
        d = row['D_features']
        context = list(row['solvent_rdkit_2d']) + [float(row['is_gas'])]
        for name in groups:
            values = p + context if name == 'Pprime' and p is not None else p + d if name == 'Pprime_plus_D' and p is not None and (d is not None) else None
            buffers[name].append(dict(row, features=values, native_Pprime_state=state))
    for name in groups:
        target = out / name / 'Joung2020.parquet'
        safe()
        pq.write_table(pa.Table.from_pylist(buffers[name], schema=schema), target, compression='zstd')
        newspec = dict(oldspec, features=str(target), C1_feature_group=name, C1_feature_vector_field='features', C1_solvent_context='Original solvent2D and explicit gas flag; no solvent geometry or solvent P labels')
        path = out / name / 'Joung2020_cv_binding.json'
        path.write_text(json.dumps(dict(joung_binding, source_groups=[newspec], source_entry=str(out / 'B0.DELIVERY.json'), original_labels_and_scaffold_folds_unchanged=True), indent=2) + '\n')
        reports.append(dict(dataset='Joung2020', feature_group=name, cv_binding=str(path), source_records=len(buffers[name]), native_quantum_states=dict(counts)))
    print('C1_PPRIME_OPTICAL_CONTEXT_CLOSED', len(pvalues), dict(counts), flush=True)
    for nucleus in ('13C', '1H'):
        source_path = b1 / 'B1_NMR_features/job_4536984' / (nucleus + '.parquet')
        parquet = pq.ParquetFile(source_path)
        atom_type = parquet.schema_arrow.field('atoms').type.value_type
        extended_atoms = pa.struct(list(atom_type) + [pa.field('Pprime_features', pa.list_(pa.float64())), pa.field('Pprime_valid_mask', pa.list_(pa.bool_()))])
        fields = [pa.field('atoms', pa.list_(extended_atoms)) if f.name == 'atoms' else f for f in parquet.schema_arrow]
        schema = pa.schema(fields + [pa.field('native_Pprime_state', pa.string()), pa.field('native_UFF_conformer_id', pa.int32())])
        target = out / ('NMRShiftDB2_' + nucleus + '.parquet')
        counts = Counter()
        with pq.ParquetWriter(target, schema, compression='zstd') as writer:
            for batch in parquet.iter_batches(batch_size=128):
                rows = []
                for row in batch.to_pylist():
                    prefix = 'NMR2018:' + nucleus + ':'
                    if not row['record_id'].startswith(prefix):
                        raise ValueError('Unknown original NMR2018 source record namespace')
                    source_id = 'NMRShiftDB2:2018:' + nucleus + ':' + row['record_id'][len(prefix):]
                    original = Chem.Mol(row['original_mol_binary'])
                    if original is None:
                        raise ValueError('Original author graph is not available')
                    _, atomic, state, cid = native_features(row['dataset'], source_id, original.GetNumAtoms())
                    atoms = []
                    for atom in row['atoms']:
                        index = atom['original_atom_index']
                        values = None if atomic is None or not np.isfinite(atomic[index]).any() else atomic[index].tolist()
                        atoms.append(dict(atom, Pprime_features=values, Pprime_valid_mask=None if values is None else [math.isfinite(v) for v in values]))
                        counts['atomic_points'] += 1
                        counts['available_Pprime_atomic_points'] += values is not None
                    rows.append(dict(row, atoms=atoms, native_Pprime_state=state, native_UFF_conformer_id=cid))
                    counts['source_spectra'] += 1
                    counts[state] += 1
                safe()
                writer.write_table(pa.Table.from_pylist(rows, schema=schema))
        reports.append(dict(dataset='NMRShiftDB2', task=nucleus, features=str(target), source_records=counts['source_spectra'], counts=dict(counts), feature_group='Pprime_plus_RDKit_atom', model='LightGBM_ONLY', original_labels_and_author_split_unchanged=True))
        print('C1_PPRIME_ATOMIC_SOURCE_CLOSED', nucleus, dict(counts), flush=True)
finally:
    for reader in geometry_readers.values():
        reader.close()
    for reader in quantum_readers.values():
        reader.close()
report = dict(status='C1_PPRIME_REFERENCE_OPTICAL_AND_ATOMIC_FEATURES_CLOSED', job=os.environ['SLURM_JOB_ID'], source_entry=str(out / 'B0.DELIVERY.json'), source_scope=str(scope_path), source_groups=reports, pretraining_schema=str(schema_path), molecule_P_fields=[c['field_key'] for c in layout.molecule], atom_P_fields=[c['field_key'] for c in layout.atom], native_P_units_and_component_order_preserved=True, geometry='First actual accepted shared UFF conformer and its actual native ID; no success selection', source_original_atom_map_preserved=True, unmapped_native_appended_H='No invented source atom index', new_QM_or_geometry_calculation=False, no_database_copy=True, native_missing_values_not_imputed=True, independent_numeric_readback=False, original_feature_job=4537149, output_namespace_job=4537149, native_producer_identity_is_report_job=True, recovery_declaration=os.environ['BENCHMARK_FEATURE_RECOVERY_DECLARATION'])
safe()
(out / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
print('C1_PPRIME_REFERENCE_OPTICAL_ATOMIC_FEATURE_SOURCE_CLOSED', out / 'manifest.json', flush=True)

PY
