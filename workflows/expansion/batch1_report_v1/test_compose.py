"""Small actual-byte metadata fixture: no molecule DATA, native or Arrow work."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from . import compose as C,accounting as A


class Source(unittest.TestCase):
    def test_complete_evidence_cannot_hide_unknown_partial_graph_or_failed_costs(self):
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder)
            def save(name,value):
                path=root/(name+'.json');raw=C.canonical(value);path.write_bytes(raw)
                return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            doc={};refs={};reader=C.Reader()
            original=dict(accepted=110046364,chemReject=14764875,technicalUnresolved=46201)
            current=dict(accepted=110050006,chemReject=14764875,technicalUnresolved=42559)
            doc['pool']=dict(schema='PUBCHEM_EXACT_MINCID_OVERLAY_POOL_V1',status='MATERIALIZED_UNFILTERED_NO_RELEASE',
                source_rows=124857440,source_counts=current,unique_full_keys=109875599,
                counts=dict(duplicate_fullkey_aliases=174407),source_snapshot_sha256='a'*64)
            refs['pool']=save('pool',doc['pool'])
            doc['acquisition']=dict(schema='PUBCHEM_ACQUIRED_SOURCE_SNAPSHOT_V1',status='ACQUISITION_AND_FULL_EOF_CID_INVENTORY_COMPLETE',
                source_records=124857440,compressed_source=dict(sha256='a'*64))
            first=dict(X01=11876899,X02=205635,X03=2323543,X04=358726,X05=72)
            doc['funnel']=dict(schema='PUBCHEM_CLOSED_SCREENING_FUNNEL_V1',fragment_count=502,source_rows=124857440,
                first_rule_counts_are_mutually_exclusive=True,overlap_rule_counts_are_not_additive=True,
                technical_UNKNOWN_is_not_chemical_exclusion=True,pool_authority_reference=refs['pool'],
                original_source_counts=original,corrected_source_counts=current,recovered_original_technical_records=3642,
                chemical_first_rule_counts=first,unique_full_keys=109875599,duplicate_fullkey_aliases=174407)
            doc['regression']=dict(schema='ALPHA_COMMON_SELECTION_REGRESSION_BIND_PRODUCER_V1',
                result=dict(passed=True,failed_checks=[],metrics=dict(agreement=1.,boolean_counts=dict(unexplained=0))))
            policy=dict(identity_kinds=['full','wp5'],wp5_definition='InChIKey[:14]+":"+InChIKey[-1]',composition_veto=False,
                lower_bound_veto=False,wildcard_veto=False,removed_subdatasets={'moleculenet':['PDBbind']})
            doc['filtered']=dict(schema='PUBCHEM_EXACT_KEY_FILTERED_SHARDS_V1',status='COMPLETE',source_pool_receipt=refs['pool'],
                input_unique_molecules=109875599,eligible_molecules=105670833,excluded_molecules=4204766,
                original_candidate_fields_and_types_preserved=True,policy=policy,
                original_identity_source_dispositions={name:dict(original_identity_rows=1,dispositions={'EXACT_KEYED':1})for name in C.SOURCES})
            refs['filtered']=save('filtered',doc['filtered'])
            doc['novelty']=dict(schema='PUBCHEM_SHARDED_FULL_POOL_NOVELTY_V1',status='COMPLETE',nearest_similarity_exact=True,
                queries=105670833,filtered_pool_reference=refs['filtered'],reference_molecules=1196122)
            refs['novelty']=save('novelty',doc['novelty'])
            doc['rank']=dict(schema='expansion_nested_queues_v1',status='CANDIDATE_ORDER_COMPLETE_NO_CONFORMERS_COMPUTED',
                queue_molecules_each=5000000,first_batch_molecules_each=1250000,seed=20261025,
                downstream_features_used=False,pool_molecules=105670833,filtered_pool=refs['filtered'],novelty_receipt=refs['novelty'])
            refs['rank']=save('rank',doc['rank'])
            doc['source']=dict(schema='PUBCHEM_UFF3_ORDERED_SOURCE_MANIFEST_V1',status='ALL2500000_ORDERED_SOURCE_GRAPHS_PROJECTED_NO_UFF',
                molecules=2500000,molecules_by_stream={'R':1250000,'N':1250000},ranking_receipt=refs['rank'],typed_filtered_pool=refs['filtered'])
            refs['source']=save('source',doc['source'])
            summary=dict(schema='EXPANSION_DISTRIBUTION_COUNTED_SUMMARY_V1',status='ALL_REQUIRED_NUMERICAL_POPULATIONS_AND_EXACT_COVERAGE_COMPLETE',
                populations=C.GROUPS,coverage_gain=dict(same_queries=1000000,minimum_similarity_gain=0.))
            population_refs={group:save(group,dict(authority_reference=refs['source'],expected_molecules=1250000))for group in('R','N')}
            doc['graph']=dict(schema='PUBCHEM_DISTRIBUTION_FOLLOWUP_REPORT_V1',status='COMPLETE',report_scope='TASK2_1_AND_TASK2_9_GRAPH_DISTRIBUTIONS',
                original_distribution_report=dict(schema='EXPANSION_DISTRIBUTION_REPORT_RECEIPT_V1',status='ALL_REQUIRED_DISTRIBUTION_NUMERICS_AND_FIGURES_COMPLETE',
                    augmented_reference_before_after_complete=True,artifacts=[save('summary',summary)],population_manifest_references=population_refs))
            for role in('before','after'):
                coverage=dict(schema='EXPANSION_EXACT_SCIENTIFIC_COVERAGE_V1',status='COMPLETE',queries=1000000,projection=dict(rows=1000000),
                    nearest_similarity_exact=True,reference_role=role,reference_molecules=1196122 if role=='before' else 3696122,baseline_receipt={'fixture':'same actual membership pin'})
                doc['graph'][role+'_coverage_reference']=save(role,coverage)
            doc['quality']=dict(schema='PUBCHEM_UFF3_VALIDITY_REVIEW_V1',mode='full',status='COMPLETE_ORIGINAL_MASK_AND_ROBUST_REVIEW_REPORT',
                source_molecules_by_stream={'R':1250000,'N':1250000},source_state_counts={'SAVED':2500000},new_R_N_TRAIN_fit=False,
                all_stream_field_counts=[dict(field_id=str(i),canonical_records=2500000,newly_masked_records=0)for i in range(27)])
            refs['quality']=save('quality',doc['quality'])
            bins={'0':2,'1':2,'2':1,'3':2499994,'UNKNOWN':1};conformers=sum(int(k)*bins[k]for k in('0','1','2','3'))
            doc['closure']=dict(schema='PUBCHEM_UFF3_CANDIDATE_STORAGE_CLOSURE_V1',status='COMPLETE_CANDIDATE_DATASET_NOT_TRAINING_RELEASE',
                maximum_delivered_conformers=3,source_manifest=refs['source'],qa_report_reference=refs['quality'],recipe_sha256='b'*64,
                full_source_bidirectional_identity_and_rank_closure=True,saved_D20_D3_and_coordinate_F64_bits_equal_delivered_families=True,
                report_metrics=dict(schema='PUBCHEM_UFF3_FINAL_REPORT_METRICS_V1',status='COMPLETE_SAVED_METADATA_ONLY',molecules=2500000,
                    groups=[dict(group_type='all',delivery_molecules=bins,known_actual_conformer_denominator=conformers)]),
                logical_census_and_saved_evidence=dict(actual_exported_conformers=conformers,unknown_actual_export_count_molecules=1,source_state_counts={'SAVED':2500000}))
            doc['pilot']=dict(schema='PUBCHEM_UFF3_ALLOCATION_RECEIPT_V1',mode='pilot',status='COMPLETE_CANDIDATE_PILOT_NOT_TRAINING_RELEASE',
                expected_molecules=10000,closed_family_export_molecules=10000,maximum_conformers=3,source_manifest=refs['source'],recipe_sha256='b'*64)
            C.validate(doc,refs,reader)
            fake=copy.deepcopy(doc);fake['graph']['report_scope']='TASK2_1_BASELINE'
            with self.assertRaisesRegex(ValueError,'Complete graph report'):C.validate(fake,refs,reader)
            fake=copy.deepcopy(doc);fake['closure']['report_metrics']['groups'][0]['delivery_molecules']['UNKNOWN']=0
            with self.assertRaisesRegex(ValueError,'delivery0/1/2/3/UNKNOWN'):C.validate(fake,refs,reader)
            raw='JobIDRaw|State|ExitCode|UID|ElapsedRaw|AllocCPUS|TotalCPU|\n1|COMPLETED|0:0|1264|3600|16|00:00.123|\n1.batch|COMPLETED|0:0|1264|3600|16|16:00:00|\n2|FAILED|1:0|1264|60|32|Unknown|\n'
            account=save('native_account',dict(endpoint='218.192.171.238:22',uid=1264,raw_sacct=raw))
            inventory=dict(inventory_complete_for_declared_goal_scope=True,coverage_statement='Small synthetic fixture includes failed and adopted parents.',
                parents=[dict(endpoint='218.192.171.238:22',uid=1264,job_id=str(job),stage='UFF',disposition=disposition,accounting_reference=account)
                         for job,disposition in((1,'adopted'),(2,'failed'))])
            cost=A.summarize(inventory,reader)
            self.assertEqual(cost['allocated_core_seconds'],59520);self.assertEqual(len(cost['parents']),2)
            self.assertEqual(cost['parents'][0]['TotalCPU_seconds_decimal'],'0.123')
            self.assertEqual(next(row for row in cost['groups']if row['group_type']=='stage')['TotalCPU_unavailable_parents'],1)
            cost['pilot_native_parent']=cost['parents'][0]
            doc['pilot']['runtime']={'job_id':'1'}
            pilot_group=dict(group_type='producer_job',producer_job_id='1',molecules=10000,
                delivery_molecules={'0':1000,'1':1000,'2':1000,'3':7000,'UNKNOWN':0},
                known_actual_conformer_denominator=24000,journal_unavailable_molecules=0,molecules_without_measured_call_timings=0,
                native_call_timings={'optimize':dict(measured_calls=30000,wall_nanoseconds=72000,
                    known_actual_conformers_in_measured_call_molecules=24000,return_events_without_timing=0)})
            pilot_metrics=C.pilot_summary(doc['pilot'],{'groups':[pilot_group]},cost['pilot_native_parent'])
            self.assertEqual(pilot_metrics['allocated_core_seconds_per_source_molecule'],'5.76')
            self.assertEqual(pilot_metrics['projected2500000_allocated_core_hours'],'4000')
            self.assertEqual(pilot_metrics['native_operations']['optimize']['wall_nanoseconds_per_known_retained_conformer'],'3')
            partial=copy.deepcopy(pilot_group);partial['journal_unavailable_molecules']=1
            self.assertEqual(C.pilot_summary(doc['pilot'],{'groups':[partial]},cost['pilot_native_parent'])['native_operations']['optimize']['status'],'PARTIAL_RECORDED_TIMING')
            partial['delivery_molecules']['3']-=1;partial['delivery_molecules']['UNKNOWN']=1
            self.assertIsNone(C.pilot_summary(doc['pilot'],{'groups':[partial]},cost['pilot_native_parent'])['native_operations']['optimize']['wall_nanoseconds_per_known_retained_conformer'])
            self.assertIsNone(C.pilot_summary(doc['pilot'],{'groups':[]},cost['pilot_native_parent'])['known_retained_conformers'])
            # Exercise actual Markdown assembly on the same tiny metadata, not
            # a second statistics implementation or a fabricated DATA run.
            doc['pool']['population_version']='fixture-version';doc['funnel']['chemical_overlap_rule_counts']=first
            doc['filtered'].update(exact_index=account,eval_exclusions=account)
            total=doc['closure']['report_metrics']['groups'][0]
            total.update(known_delivery_molecules=2499999,source_state_counts={'SAVED':2500000},native_call_timings={},
                stored_worker_or_generation_clocks={'worker_CPU_seconds':dict(observed_molecules=0,unavailable_molecules=2500000,total_seconds_decimal=None)},
                recorded_cache_counts={},diagnostic_code_top20=[])
            doc['closure']['report_metrics']['catalogs']={'diagnostics':account}
            doc['closure']['logical_census_and_saved_evidence']['D20_evidence_state_counts']={'PRESENT_VALID':2499999,'UNKNOWN':1}
            doc['closure'].update(storage=dict(categories=[],linear10M_projection=None),finalizer_own_closed_sql_and_catalog_allocated_bytes=123)
            doc['quality'].update(worst20_per_field=account,mask_reason_sets=account)
            for row in doc['quality']['all_stream_field_counts']:row['source_ineligible_records']=0
            summary.update(scaffold_long_tail={group:dict(distinct_scaffolds=1,singleton_scaffolds=0)for group in C.GROUPS},numeric=[],identity_match_counts={})
            summary['coverage_gain'].update(mean_similarity_gain=.1,queries_with_strictly_improved_coverage=10)
            for name in C.REQUIRED:refs.setdefault(name,account)
            figures={name:{}for name in('descriptor_distributions.png','elements_and_scaffold_long_tail.png','functional_group_prevalence.png','exact_nearest_coverage_before_after.png')}
            text=C.render(doc,refs,summary,{},total,cost,figures)
            self.assertIn('not zero',text);self.assertIn('59520 core-seconds',text)
            self.assertIn('worker_CPU_seconds',text);self.assertIn('None',text)
            repeated=copy.deepcopy(inventory);repeated['parents'].append(repeated['parents'][0])
            with self.assertRaisesRegex(ValueError,'exactly once'):A.summarize(repeated,reader)
            with self.assertRaisesRegex(ValueError,'SHA/frame'):reader.json(dict(account,sha256='0'*64))


if __name__=='__main__':unittest.main()
