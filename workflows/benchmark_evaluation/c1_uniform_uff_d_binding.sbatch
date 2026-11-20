#!/bin/bash
#SBATCH --job-name=C1-native-uniform-UFF-D-bind
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_uniform_D_binding_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import json,math,os,unittest
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from workflows.data_v1_final.labels.common import D20_NAMES
from workflows.benchmark_data.admission import protect
from workflows.benchmark_data.shared_reader import SharedB0Reader
from workflows.benchmark_data.shared_access import check_access
from workflows.benchmark_data.pprime_tmpfs_queue import FORECAST
D3_NAMES=('PMI1','PMI2','PMI3','PBF','volume_A3','SASA_total_A2')
FEATURE_NAMES=list(D20_NAMES)+list(D3_NAMES)
def vector(value):
    if value is None or value.get('D20') is None:return None
    d20=value['D20']
    if d20['names']!=list(D20_NAMES) or len(d20['values'])!=20 or len(d20['valid_mask'])!=20:raise ValueError('Native D20 schema differs')
    numbers=[float(v) if valid and v is not None and math.isfinite(float(v)) else float('nan') for v,valid in zip(d20['values'],d20['valid_mask'])]
    conformers=value.get('conformers') or []
    d3=(conformers[0].get('D3') or {}) if conformers else {}
    numbers += [float(d3[name]) if d3.get(name) is not None and math.isfinite(float(d3[name])) else float('nan') for name in D3_NAMES]
    return numbers
class FeatureTests(unittest.TestCase):
    def fixture(self):return {'D20':{'names':list(D20_NAMES),'values':[float(i) for i in range(20)],'valid_mask':[True]*20},'conformers':[{'D3':dict(zip(D3_NAMES,[1.,2.,3.,4.,5.,6.]))}]}
    def test_native_order_and_first_conformer(self):
        row=self.fixture();row['conformers'].append({'D3':dict.fromkeys(D3_NAMES,999.)})
        self.assertEqual(vector(row),[float(i) for i in range(20)]+[1.,2.,3.,4.,5.,6.])
    def test_missing_geometry_keeps_global_2d_without_fill(self):
        row=self.fixture();row['conformers']=[]
        self.assertEqual(vector(row)[:20],[float(i) for i in range(20)])
        self.assertTrue(all(math.isnan(v) for v in vector(row)[20:]))
    def test_masked_native_field_is_not_zero_imputed(self):
        row=self.fixture();row['D20']['valid_mask'][4]=False
        self.assertTrue(math.isnan(vector(row)[4]))
    def test_entire_missing_result_remains_missing(self):self.assertIsNone(vector(None))
    def test_schema_drift_fails(self):
        row=self.fixture();row['D20']['names']=list(reversed(D20_NAMES))
        with self.assertRaises(ValueError):vector(row)
    def test_nonfinite_native_field_remains_missing(self):
        row=self.fixture();row['conformers'][0]['D3']['PBF']=float('inf')
        self.assertTrue(math.isnan(vector(row)[23]))
suite=unittest.defaultTestLoader.loadTestsFromTestCase(FeatureTests)
if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():raise SystemExit(1)

entry=json.loads("{\n  \"schema\": \"BENCHMARK_B0_AVAILABLE_DELIVERY_ENTRY_V1\",\n  \"status\": \"D_AVAILABLE_DIRECTIVE19_UNIFORM_SPRIME_SEALED_PPRIME_IN_PROGRESS\",\n  \"authority\": \"docs/benchmark/USER_DIRECTIVE_20261118.md@07be7a0f04085398eeda2b7548afa46c668ffd9a\",\n  \"data_root\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119\",\n  \"manifest\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/delivery/directive19_current_counts_4537016/manifest.json\",\n  \"domain_counts_csv\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/delivery/directive19_current_counts_4537016/domain_counts.csv\",\n  \"handoff_native_job\": 4537016,\n  \"handoff_native_state\": \"COMPLETED\",\n  \"handoff_native_exit\": \"0:0\",\n  \"source_groups\": 11,\n  \"domain_count_rows\": 12,\n  \"Pprime_current_job\": 4536588,\n  \"Pprime_current_node\": \"compute-0-12\",\n  \"Pprime_current_workers\": 8,\n  \"Pprime_followup_jobs\": [\n    4536590\n  ],\n  \"Pprime_all_ready\": false,\n  \"S_ready\": false,\n  \"P_ready\": false,\n  \"reference_quantum_status\": \"Downstream uniformly uses shared UFF Sprime; C1 property groups use Pprime; historical reference XYZ retained as provenance\",\n  \"no_local_database_copies\": true,\n  \"all_required_production_complete\": false,\n  \"supplemental_sources\": {\n    \"SAMPL6_7\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/provenance/SAMPL6_7/job_4536607/manifest.json\",\n    \"ExpansionRx_official_release\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/raw/ExpansionRx_official_release/job_4536975/manifest.json\"\n  },\n  \"active_evaluation_scope\": {\n    \"status\": \"B1_AND_LATER_SCOPE_EXCLUDES_FIVE_DEFERRED_ENDPOINTS\",\n    \"decision_date\": \"2026-11-19\",\n    \"endpoint_registry\": \"configs/benchmark_data/B1.deferred_tasks.json\",\n    \"selector\": \"workflows.benchmark_data.task_selection.select_active_tasks\",\n    \"strict_full_inventory_verification\": true,\n    \"expected_deferred_endpoint_count\": 5,\n    \"effective_at\": \"B1_TASK_INVENTORY_BEFORE_MODEL_FITS\",\n    \"b0_source_data_and_provenance\": \"UNALTERED\",\n    \"failure_policy\": \"BLOCK_B1_UNTIL_ALL_FIVE_DEFERRED_IDENTIFIERS_MATCH\",\n    \"scope_authority_commit\": \"fec1b994aa642ba8db74074134f909dcb4f165f0\",\n    \"full_inventory_verification\": \"REQUIRED_BEFORE_B1_FITTING_NOT_PERFORMED_BY_B0\"\n  },\n  \"directive19_resolutions\": {\n    \"authority_commit\": \"6d056a41f379b921d31017ecfed9ce84d1a5c71a\",\n    \"directive\": \"docs/benchmark/USER_DIRECTIVE_20261119.md\",\n    \"pka\": {\n      \"main\": \"molecular_macro_strongest_acid_and_strongest_base\",\n      \"mechanism\": \"uniquely_identifiable_single_ionization_site_only\",\n      \"single_site_evidence_required\": true,\n      \"predicted_microspecies_are_experimental\": false,\n      \"multisite_microscopic_assignment\": false,\n      \"SAMPL_exclusion\": \"complete_InChIKey; challenge_plus_local_ID\"\n    },\n    \"nmr\": {\n      \"split\": \"nmrshiftdb2-2018; Jonas_Kuhn_2019; Kwon_2020\",\n      \"prefer_author_split\": true,\n      \"published_test_molecule_count_match_required\": true,\n      \"CSTShift\": \"DFT_input_reference_upper_bound_only\"\n    },\n    \"geometry\": {\n      \"downstream\": \"uniform_Sprime_UFF\",\n      \"PM7_optimizer\": \"DO_NOT_RECONSTRUCT_OR_TRIAL\",\n      \"C1_property_group\": \"Pprime; explicitly_named_Pprime\",\n      \"Pprime_access\": \"corresponding_dataset_producer_sealed\"\n    },\n    \"seeds\": {\n      \"default\": 1,\n      \"second\": \"final_significant_improvement_or_specified_training_rollback_instability\"\n    },\n    \"B1_branch\": \"benchmark-b1-20261119\",\n    \"data_preparation_complete\": false\n  },\n  \"directive19_data_preparation\": {\n    \"NMR2018_author_split\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/NMR2018/job_4536853/manifest.json\",\n    \"NMR2018_targets\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/NMR2018/job_4536887/manifest.json\",\n    \"pKahub_macro_targets\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/pKahub/job_4536891/manifest.json\",\n    \"uniform_Sprime_scope\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/uniform_Sprime/geometry/shared_v1/queue.manifest.json\",\n    \"uniform_scope_ready\": true,\n    \"pKa_atomic_site_evidence_ready\": false,\n    \"NMR2018_published_test_count_reconciliation\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/NMR2018/job_4536946/manifest.json\",\n    \"NMR2018_test_molecule_counts_matched\": true,\n    \"pKa_single_site_definition_proposal\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/pKahub/job_4536942/manifest.json\",\n    \"pKa_single_site_definition_approval\": \"PENDING_USER_REPLY; proposal is not a training-label entry\"\n  },\n  \"active_target_manifests\": {\n    \"NMRShiftDB2\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/NMR2018/job_4536887/manifest.json\",\n    \"pKahub\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/directive19/pKahub/job_4536891/manifest.json\"\n  },\n  \"uniform_Sprime_producer\": {\n    \"job\": 4536924,\n    \"native_state\": \"COMPLETED\",\n    \"node\": \"compute-0-17\",\n    \"workers\": 2,\n    \"producer_progress_observed\": true,\n    \"previous_bootstrap_job\": 4536898,\n    \"previous_bootstrap_state\": \"FAILED\",\n    \"previous_bootstrap_exit\": \"9:0\",\n    \"previous_bootstrap_scientific_calls\": 0,\n    \"source_UFF_job\": 4536924,\n    \"D3_alignment_postprocessing_job\": 4536978,\n    \"geometry_generation_complete\": true,\n    \"D3_alignment_postprocessing_state\": \"COMPLETED/0:0\",\n    \"effective_source_final_writer_job\": 4536978,\n    \"outcome_counts\": {\n      \"D20_READY_NO_ACCEPTED_CONFORMERS\": 656,\n      \"D20_READY_STEREO_REFERENCE_UNAVAILABLE\": 14285,\n      \"D20_READY_UFF_UNSUPPORTED\": 11,\n      \"SPRIME_AND_D_READY\": 23287,\n      \"SPRIME_READY_D_PARTIAL\": 1\n    }\n  },\n  \"uniform_Pprime_chain\": {\n    \"prepare_job\": 4536979,\n    \"producer_jobs\": [\n      4536906,\n      4536907\n    ],\n    \"source_geometry_native_C0_required\": true,\n    \"ready\": false,\n    \"source_geometry_job\": 4536978,\n    \"queued_actual_conformers\": 53896,\n    \"source_geometry_sealed\": true,\n    \"prepare_native_state\": \"COMPLETED/0:0\",\n    \"current_workers\": 8,\n    \"current_job\": 4536906,\n    \"current_native_state\": \"RUNNING\",\n    \"observed_intents\": 8,\n    \"current_node\": \"compute-0-17\",\n    \"observed_CST\": \"2026-11-20T11:02:12+08:00\",\n    \"observed_pending\": 49311,\n    \"producer_progress_observed\": true,\n    \"observed_ready\": 4574,\n    \"producer_log\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B0_uniform_pprime_4536906.log\",\n    \"cross_node_read_allowed\": false,\n    \"observed_partial\": 3\n  },\n  \"both_scopes_final_handoff\": {\n    \"job\": 4536961,\n    \"native_state\": \"PENDING\",\n    \"submitted_afterok_jobs\": [\n      4536963,\n      4536599,\n      4536907\n    ],\n    \"manifest\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/delivery/final_all_scopes_4536961/manifest.json\",\n    \"production_closed\": false,\n    \"all_required_work_complete\": false,\n    \"metadata_only_no_SQLite_replay\": true\n  },\n  \"D3_source_alignment_recovery\": {\n    \"status\": \"SOURCE_UFF_AND_D3_REPAIR_CLOSED_GEOMETRY_SEALED\",\n    \"recorded_error_metadata_job\": 4536970,\n    \"unit_test_job\": 4536974,\n    \"source_check_job\": 4536976,\n    \"repair_job\": 4536978,\n    \"source_UFF_job\": 4536924,\n    \"source_seal_prepare_job\": 4536979,\n    \"superseded_zero_start_prepare_job\": 4536925,\n    \"successful_labels_and_source_coordinates_unchanged\": true,\n    \"original_failure_history_preserved\": true,\n    \"genuine_scientific_failure_retry\": false,\n    \"recorded_error_confirmed\": true,\n    \"unit_tests_passed\": 6,\n    \"source_check_status\": \"PASS\",\n    \"source_check_files\": 5264,\n    \"source_sealed\": true,\n    \"repair_native_state\": \"COMPLETED/0:0\",\n    \"remaining_partial_molecules\": 1,\n    \"repair_complete\": true,\n    \"repair_outcomes\": {\n      \"D3_REPAIRED\": 41243\n    }\n  },\n  \"Pprime_previous_closed_job\": {\n    \"job\": 4536581,\n    \"native_state\": \"COMPLETED\",\n    \"native_exit\": \"0:0\",\n    \"INTENT\": 0,\n    \"outcome_counts\": {\n      \"PENDING\": 164875,\n      \"PPRIME_PARTIAL_WITH_RECORDED_OUTCOMES\": 157,\n      \"PPRIME_READY\": 160048\n    }\n  },\n  \"Pprime_standby\": {\n    \"job\": 4536991,\n    \"previous_job\": 4536588,\n    \"followup_job\": 4536590,\n    \"native_state\": \"PENDING\",\n    \"scientific_calls\": 0,\n    \"acceptance_written\": false,\n    \"exclude_unrecovered_node18\": true,\n    \"superseded_zero_native_candidate\": 4536722,\n    \"exclude_uniform_active_node\": \"compute-0-17\",\n    \"exclusion_until\": \"Uniform scope tmpfs writer closed; both8+16 scratch peaks exceed actual node17 tmpfs\",\n    \"uniform_tail_must_exclude_allocated_standby_node_before_accept\": true,\n    \"scientific_record_grace_unchanged\": true,\n    \"native_TimeLimit_hours\": 24,\n    \"native_TimeMin_hours\": 6,\n    \"actual_speedup_not_yet_observed\": true,\n    \"previous_native_TimeMin_hours\": 12,\n    \"TimeMin_update_at_verified_pending_zero_runtime\": true\n  },\n  \"active_source_count_handoff\": {\n    \"historical_domain_table_preserved\": true,\n    \"unit_tests_and_source_check_pending\": false,\n    \"native_state\": \"COMPLETED/0:0\",\n    \"job\": 4537016,\n    \"source_check_files\": 5265,\n    \"unit_tests_passed\": 3,\n    \"source_check_python_files\": 3736,\n    \"source_check_errors\": 0\n  },\n  \"active_domain_counts_csv\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/delivery/directive19_current_counts_4537016/active_source_domain_counts.csv\",\n  \"historical_domain_counts_csv\": \"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/delivery/directive19_current_counts_4537016/domain_counts.csv\"\n}\n")
root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():
    current=sum(p.stat().st_size for p in (root/'labels/Pprime/shared_v1').glob('*.sqlite'))
    protect(root,512*1024**2+80000000000+max(0,FORECAST-current),quota,own_concurrent_bytes=40*1024**3)
scope_path=Path(entry['directive19_data_preparation']['uniform_Sprime_scope'])
scope=json.loads(scope_path.read_text())
for queue in (scope['queue'],scope['reused_source_queue']):
    access=check_access(queue)
    if not access or not access.get('immutable') or not access.get('cross_node_read_allowed'):
        raise RuntimeError('Actual uniform UFF source must be sealed before C1 consumption')
safe();out=b1/'C1_uniform_D_features'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True)
(out/'B0.DELIVERY.json').write_text(json.dumps(entry,indent=2)+'\n')
bindings={}
for row in pq.read_table(scope['geometry_bindings']).to_pylist():
    if row['dataset'] not in ('C7H10O2','PPE1694'):continue
    key=(row['dataset'],row['record_id'])
    if key in bindings:raise ValueError('Duplicate original source geometry binding')
    bindings[key]=row
readers={};reports=[];native_cache={}
try:
    for group,old_job in (('C7H10O2',4536995),('PPE1694',4536997)):
        old_path=b1/'reference_cv_binding'/('job_'+str(old_job))/'manifest.json'
        old=json.loads(old_path.read_text());spec=next(r for r in old['source_groups'] if r['dataset']==group)
        table=pq.read_table(spec['features']);updated=[];counts={}
        for row in table.to_pylist():
            route=bindings.get((group,row['record_id']));vector_values=None
            if route is not None:
                queue=route['shared_geometry_queue']
                if queue not in readers:readers[queue]=SharedB0Reader(queue)
                key=(queue,route['shared_geometry_dataset'],route['shared_geometry_record_id'])
                if key not in native_cache:native_cache[key]=readers[queue].get(key[1],key[2])
                source=native_cache[key];vector_values=vector(source['result'])
                status=source['state']
            else:status='NO_DOMAIN_ELIGIBLE_NATIVE_UFF_BINDING'
            row['D_features']=vector_values
            row['D_valid_mask']=[math.isfinite(v) for v in vector_values] if vector_values is not None else None
            row['D3_state']='NATIVE_UFF_'+status
            updated.append(row)
            counts[status]=counts.get(status,0)+1
            if len(updated)%256==0:safe()
        path=out/(group+'.parquet');safe()
        pq.write_table(pa.Table.from_pylist(updated,schema=table.schema),path,compression='zstd')
        new_spec=dict(spec,features=str(path),C1_D_geometry_source='First actual accepted sealed shared UFF conformer; never historical reference XYZ',C1_native_D_order=FEATURE_NAMES)
        binding=dict(old,source_entry=str(out/'B0.DELIVERY.json'),source_groups=[new_spec],C1_D_feature_rebinding_only=True,original_labels_and_scaffold_folds_unchanged=True,source_geometry_scope=str(scope_path),supersedes_C1_reference_geometry_feature_source=spec['features'])
        binding_path=out/(group+'_cv_binding.json');safe();binding_path.write_text(json.dumps(binding,indent=2)+'\n')
        reports.append(dict(dataset=group,features=str(path),cv_binding=str(binding_path),source_records=len(updated),native_geometry_state_counts=counts,native_D_feature_rows=sum(r['D_features'] is not None for r in updated)))
        print('C1_UNIFORM_UFF_D_BOUND',group,len(updated),counts,flush=True)
finally:
    for reader in readers.values():reader.close()
report=dict(status='C1_UNIFORM_UFF_NATIVE_D_FEATURES_CLOSED',job=os.environ['SLURM_JOB_ID'],source_entry=str(out/'B0.DELIVERY.json'),source_scope=str(scope_path),source_groups=reports,feature_order=FEATURE_NAMES,native_pretraining_D20_unchanged=True,D3_first_actual_accepted_UFF_only=True,native_missing_values_and_masks_preserved=True,new_geometry_or_D_calculation=False,source_reference_labels_unchanged=True,scaffold_folds_unchanged=True,old_C1_outputs_preserved=True,superseded_C1_LightGBM_jobs=[4537002,4537006],unstarted_TabPFN_jobs_cancelled=[4537008,4537009],independent_numeric_readback=False,new_unit_tests=suite.countTestCases())
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('C1_UNIFORM_UFF_D_SOURCE_CLOSED',out/'manifest.json',flush=True)

PY
