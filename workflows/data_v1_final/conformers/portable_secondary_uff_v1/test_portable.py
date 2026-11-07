"""Synthetic source/transport boundaries; not environment or science compatibility PASS."""
import base64,copy,pickle,types,unittest
from unittest import mock
from . import bridge
from .contract import canonical,sha,recipe_equivalence,prep_metadata,control_selection_rule,CONTROL_MODE,environment_for_controls
from .prepare_existing_controls import select_metadata


class PortableBoundaries(unittest.TestCase):
    def test_recipe_allows_only_exact_source_locator_and_output_root_changes(self):
        old={'rdkit_version':'2025.09.5','science_source_pins':[{'path':'/synthetic/main/core.py','bytes':4,'sha256':'a'*64}],
            'external_output_root':'/synthetic/main/out','candidate_multiplier':10,'uff_force_tolerance':1e-4,'dedup_rmsd_A':0.5}
        target={'path':'/synthetic/secondary/core.py','bytes':4,'sha256':'a'*64}
        new=copy.deepcopy(old);new['science_source_pins'][0]['path']=target['path'];new['external_output_root']='/synthetic/secondary/out'
        proof=recipe_equivalence(old,new,{old['science_source_pins'][0]['path']:target},new['external_output_root'])
        self.assertFalse(proof['scientific_values_changed'])
        for key,value in (('candidate_multiplier',20),('uff_force_tolerance',1e-3),('dedup_rmsd_A',0.4)):
            changed=copy.deepcopy(new);changed[key]=value
            with self.assertRaisesRegex(ValueError,'NONLOCATOR_RECIPE_CHANGE'):
                recipe_equivalence(old,changed,{old['science_source_pins'][0]['path']:target},new['external_output_root'])

    def test_pickle_bytes_pointer_and_atom_count_are_preserved_without_float_recode(self):
        original={'x':[1,2],'pos':[[0.0,-0.0,1.234567890123456e-200],[1.0,2.0,3.0]]}
        payload=pickle.dumps(original,protocol=4) # synthetic only, never reconstructs an actual record
        pointer={'source_path':'/synthetic/main_only/not_present.lmdb','real_index':17,'record_id':'synthetic_record',
            'record_payload_sha256':sha(payload),'total_atoms':2}
        task={'meta':{'molecule_id':'synthetic_new_mid'},'records':[pointer],'existing_conformers':[]}
        entry={'pointer_sha256':sha(canonical(pointer)),'payload_bytes':len(payload),'payload_sha256':sha(payload),
            'original_pickle_base64':base64.b64encode(payload).decode()}
        envelope={'task':task,'task_sha256':sha(canonical(task)),'record_payloads':[entry]}
        expected={'molecule_id':'synthetic_new_mid','task_sha256':sha(canonical(task))}
        core=types.SimpleNamespace(plain=lambda value:value,field=lambda value,key:value.get(key))
        with mock.patch.object(bridge,'STATE',{'core':core}):
            self.assertEqual(bridge.bind_envelope(envelope,expected),task)
            decoded=bridge.read_payload(pointer)
            self.assertEqual(pickle.dumps(decoded,protocol=4),payload)
            damaged=copy.deepcopy(envelope);damaged['record_payloads'][0]['original_pickle_base64']=base64.b64encode(payload+b'X').decode()
            with self.assertRaisesRegex(ValueError,'EXACT_ORIGINAL_RECORD_PICKLE_BYTES_REQUIRED'):
                bridge.bind_envelope(damaged,expected)
            bridge.bind_envelope(envelope,expected)
            wrong=copy.deepcopy(pointer);wrong['total_atoms']=3
            bridge.STATE['payloads'][sha(canonical(wrong))]=entry
            with self.assertRaisesRegex(ValueError,'ACTUAL_RECORD_MANIFEST_MISMATCH'):bridge.read_payload(wrong)

    def test_qa_allowlist_permits_exact16_old_controls_and_rejects_missing_or_population_release(self):
        protected=['principal_01112964','principal_00509656']+['synthetic_old_%03d'%i for i in range(334)]
        ids=protected[2:18]
        prep={'schema':'MAIN_EXISTING334_SECONDARY_CONTROL16_PREPARATION_V1',
            'status':'ROOT_APPROVED_EXISTING_PACKETS_FOR_SECONDARY_SOFTWARE_QA_ONLY','reviewer':'root','mode':CONTROL_MODE,
            'formal_generation_authorized':False,'main_preparation_on_legal_cpu_allocation':True,'automatic_retry':False,
            'protected_original_population_ids':protected,'molecule_ids':ids,'allowed_original_control_ids':ids,
            'forbidden_original_population_ids':sorted(set(protected)-set(ids)),
            'golden_expected':[{'molecule_id':mid,'task_sha256':'a'*64,'scientific_sha256_excluding_elapsed_seconds':'b'*64,
                'baseline_summary_status':'SUCCESS','baseline_packet_reference':{'path':'/synthetic/main/'+mid+'.json.gz'},
                'baseline_file_identity':{'uid':1278}} for mid in ids],
            'population_members_added':0,'main_production_once_ledger_accessed':False,'current_main_recovery_2plus14_scope_changed':False,
            'new_main_science_baseline_computed':False,'original_pilot_parent_state':'TIMEOUT','partial_audit_parent_job_id':'4520527',
            'partial_audit_parent_state':'COMPLETED','selection_rule':control_selection_rule(),
            'root_control_authorization_reference':{},'qa_slice_marker_reference':{},'original_audit_reference':{},
            'original_complete_packages_reference':{},'partial_audit_monitor_closure_reference':{},
            'slice_id':'synthetic_golden16','tasks_reference':{'path':'/synthetic/main/tasks.jsonl','bytes':16,'sha256':'c'*64}}
        self.assertEqual(set(prep_metadata(prep)),set(ids))
        for case in ('missing','duplicate','formal','population','new_baseline'):
            changed=copy.deepcopy(prep)
            if case=='missing':changed['molecule_ids'][0]='principal_01112964'
            elif case=='duplicate':changed['molecule_ids'][-1]=changed['molecule_ids'][0]
            elif case=='formal':changed['formal_generation_authorized']=True
            elif case=='population':changed['population_members_added']=16
            else:changed['new_main_science_baseline_computed']=True
            with self.assertRaises(ValueError):prep_metadata(changed)

    def test_fixed_hash_small_fast_rule_and_insufficient_count_never_widens(self):
        rows=[]
        for i in range(334):
            rows.append({'molecule_id':'synthetic_%03d'%i,'science_worker_seconds':60.0,
                'summary':{'status':'SUCCESS' if i<18 else 'EMBED_FAILED','heavy_atoms':32,
                    'expected_conformers':30,'elapsed_seconds':60.0},'detail':{'new_real_accepted_count':1}})
        chosen,report=select_metadata(rows)
        domain=control_selection_rule()['hash_domain']
        expected=sorted((sha((domain+row['molecule_id']).encode()),row['molecule_id']) for row in rows[:18])[:16]
        self.assertEqual([row['molecule_id'] for row in chosen],[mid for _,mid in expected])
        self.assertEqual(report['eligible_count'],18)
        for index,(key,value) in enumerate((('heavy_atoms',33),('expected_conformers',31),('elapsed_seconds',60.001))):
            rows[index]['summary'][key]=value
            if key=='elapsed_seconds':rows[index]['science_worker_seconds']=value
        chosen,report=select_metadata(rows)
        self.assertEqual(report['eligible_count'],15);self.assertEqual(chosen,[])
        self.assertEqual(report['status'],'ELIGIBLE_COUNT_BELOW16_NO_QA_SLICE')
        self.assertFalse(report['science_called']);self.assertFalse(report['thresholds_automatically_widened'])

    def test_actual_offline_schema_conversion_retains_ready_only_and_torch_difference(self):
        source={'path':'/synthetic/offline_validation.json','bytes':1,'sha256':'d'*64}
        raw={'schema':'SECONDARY_OFFLINE_ENVIRONMENT_VALIDATION_V1','status':'READY_FOR_GOLDEN16_COMPATIBILITY_TEST',
            'endpoint':'218.192.171.238:22','uid':1264,'user':'alpha','cpus':16,'node':'synthetic_cpu6','job_id':'90001',
            'memory_requested':False,'formal_generation_authorized':False,'golden_compatibility_accepted':False,
            'torch_matches_main_build_claimed':False,'dataset_records_read':0,'UFF_calls':0,'QM_calls':0,'forced_signals_sent':False,
            'python_path':'/synthetic/alpha/bin/python','version_difference_note':'Synthetic main2.10 vs secondary2.5.1+cpu',
            'versions':{'python':'3.11.14','numpy':'2.2.6','rdkit':'2025.09.5','torch':'2.5.1+cpu','torch_geometric':'2.7.0',
                'torch_cuda_build':None,'toy_numpy_svd_passed':True,'toy_pickle_tensor_PyG_float64_exact':True,'toy_rdkit_parse_atoms':3,
                'executable':'/synthetic/alpha/bin/python','scipy':'1.15.3','lmdb':'1.7.5','pyarrow':'17.0.0'}}
        before=copy.deepcopy(raw)
        review=environment_for_controls(raw,source,'synthetic_endpoint',{'allowed_cpu_nodes':['synthetic_cpu6']})
        self.assertEqual(raw,before)
        self.assertEqual(review['status'],'READY_FOR_GOLDEN16_COMPATIBILITY_TEST')
        self.assertFalse(review['formal_compatibility_passed']);self.assertFalse(review['scientific_compatibility_accepted'])
        self.assertFalse(review['torch_build_identical_to_main'])
        self.assertEqual(review['source_validation_reference'],source)
        wrong=copy.deepcopy(raw);wrong['versions']['rdkit']='2024.03.2'
        with self.assertRaises(ValueError):environment_for_controls(wrong,source,'synthetic_endpoint',{'allowed_cpu_nodes':['synthetic_cpu6']})


if __name__=='__main__':unittest.main()
