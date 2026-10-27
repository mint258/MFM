"""Record actual closed metadata v29 without opening scientific payloads."""
import datetime,json,pathlib
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q
Q.on_login();R=Q.ROOT;refs={}
def read(k,p):
 refs[k]=Q.pin(R/p);return Q.load(R/p)
previous=read('previous','control/active_checkpoint_v28.json')
main=read('Main_master34','control/owned_accounting_checkpoint34_cpu_auto_memory_20261027_v1.json')
b='control/secondary_cluster_20261026_v1/alpha_short_followups_v1/'
t=read('Alpha33_verified_transfer',b+'alpha33_verified_transfer_receipt_v1.json')
for item in t['references']:
 a=Q.pin(item['Main_copy']['path']);assert a==item['Main_copy'] and a['bytes']==item['producer']['bytes'] and a['sha256']==item['producer']['sha256']
a=read('Alpha_master33',b+'alpha33_verified_metadata_v1/alpha_owned_accounting_checkpoint33_v1.json')
c=read('Alpha_C_closed31',b+'alpha33_verified_metadata_v1/pubchem_C_actual_closed_progress_20261027_v3.json')
csv=read('Alpha_CSV6_C0_summary',b+'alpha33_verified_metadata_v1/csv6_full1884803_actual_closed_summary_v1.json')
ll=Q.load(R/'control/sprime_wave2_controller_v1/live_v1/latest.json');refs['Sprime_state']=ll['state_reference'];assert Q.pin(ll['state_reference']['path'])==ll['state_reference'];s=Q.load(ll['state_reference']['path'])
closed=[v['close']['closure_counts'] for v in s['stages'].values() if v.get('close',{}).get('closure_counts',{}).get('valid_packets',0)>0]
f=read('footer2208','artifacts/labels/source_status_v1/footer_continuation_full_v1/manifest.json')
l=read('labels_bounded_C0','artifacts/labels/source_status_v1/bounded_projection32_v1/manifest.json')
pm=read('PM7_5000_C0','artifacts/conformers/pm7_population_cache_v1/batch5000_000_v1/receipt.json')
g=read('Pprime_input_geometry_C0','artifacts/pprime_causal15_main_v1/actual_input_geometry_readonly_v1/geometry_and_JSON_report.jsonl')
kr=read('Kraken_profile_C0','artifacts/expansion/marcel_kraken_keys_profile_v1/receipt.json')
for k,p in {'labels_C0_cost':'control/accounting/labels_bounded32_4521789_v1.json','PM7_5000_C0_cost':'control/accounting/pm7_population5000_4521775_v1.json','Pprime_failed15_cost':'control/accounting/pprime_causal15_failed_4521766_v1.json','Pprime_readonly15_C0_cost':'control/accounting/pprime15_readonly_recovery_4521802_v1.json','Pprime_geometry_C0_cost':'control/accounting/pprime15_geometry_readonly_4521845_v1.json','Sprime_v3_launch':'control/sprime_wave2_controller_v3_actual_finite_launch_v1.json','Sprime_second_HOLD_cause':'control/sprime59_actual_lock_cause_recovery_v1.json','TDC_all44_C0':'artifacts/expansion/tdc_zip44_identity_main_v1/receipt.json','TDC_all44_C0_cost':'control/accounting/tdc_identity_4521757_v1.json','Drugs_profile_C0':'artifacts/expansion/marcel_drugs_keys_profile_v1/receipt.json','Drugs_profile_C0_cost':'control/accounting/drugs_keys_profile_4521818_v1.json','Drugs_full_submission':'control/submissions/dv1_q_drugs_keys_full_20261027_v1.json','Drugs_full_profile_budget_review':'control/marcel_drugs_full_actual_profile_cost_review_v1.json','Kraken_profile_C0_cost':'control/accounting/kraken_keys_profile_4521859_v1.json','repository_check20_C0':'control/repository_source_check_v20_actual.json','labels_full6_fixtures':'control/repository_source_check_v20_actual.fixtures6.json','repository_check20_C0_cost':'control/accounting/source20_label6_4521863_v1.json','labels_full_source8':'control/labels_full_source8_install_v2.json','PM7_controller_source7':'control/pm7_controller_source7_install_v1.json','public_source16':'control/github_source_publication_v16.json','v28_status_correction':'control/progress_v28_report_status_correction_v1.json'}.items():refs[k]=Q.pin(R/p)
comparisons=[{'condition':v['condition'],'arms':v['outer_arms'],'coordinate_outside_token_bound':v['coordinate_components_outside_native_token_bound'],'Gram_outside_token_bound':v['centered_Gram']['outside_propagated_native_token_bound'],'distance_outside_token_bound':v['pair_distances']['outside_squared_distance_token_bound'],'nonoverlapping_distance_intervals':v['pair_distances']['nonoverlapping_distance_token_intervals']} for v in g['comparisons']]
js=[v['xTB_JSON_selection_observation'] for v in g['observations'] if 'xTB_JSON_selection_observation' in v]
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
v={'schema':'DATA_V1_ACTIVE_CHECKPOINT_V29','observed_utc':now,'goal_complete':False,'guide_complete':False,'stop_instruction':previous['stop_instruction'],'sessions':previous['sessions'],'source':dict(previous['source'],new_uncommitted_source='footer3,TDC8,PM7population8,Krakenprimitive8,Sprimecontroller5,boundedlabels6,Pprime recovery8,Drugskeys9,Krakenkeys8,Pprimegeometry8,full-label8,PM7controller7 and actual progress docs',new_source_check_commit_pending=True),
'Main':{'actual_master34_parents':len(main['actual_parents']),'observed_allocated_core_hours':main['observed_allocated_core_hours'],'active_at_master34':main['active_at_observation'],
'Sprime':{'controller_pid':2761781,'status':s['status'],'reason':s.get('reason'),'closed_batches':len(closed),'valid_packets':sum(x['valid_packets'] for x in closed),'all179_closed':len(closed)==179,'closure_is_Common_or_quality_release':False,'state':refs['Sprime_state']},
'labels':{'footer_status':f['status'],'observed_files':f['observed_files'],'bounded_status':l['status'],'matched_parity_rows':l['parity']['matched_rows'],'parity_mismatches':l['parity']['mismatch_count'],'unique_output_bytes_before_manifest':l['unique_new_output_bytes_before_manifest'],'bounded_is_full_population':False,'full8_source_installed':True,'full6_pure_actual_C0':True,'full_storage_and_execution_review_pending':True,'D4':False},
'PM7':{'status':pm['status'],'selected_molecules':pm['selected_molecules'],'selected_records':pm['selected_records'],'geometry_complete_molecules':pm['geometry_complete_molecules'],'unstarted_molecules':pm['unstarted_molecules'],'error_count':pm['error_count'],'original256_not_recomputed':True,'full247_source7_installed_not_submitted':True,'full_range_review_waits_actual_Sprime179':True,'D7':False},
'Pprime':{'original15FAIL_and_full2000_HOLD_preserved':True,'new15_QA_failed_output_stage_4521766_preserved':True,'all15_outputs_recovered_without_new_QM':True,'original_WP5_unknown_cases_preserved':g['original_WP5_unknown_cases'],'actual_input_comparisons':comparisons,'xTB_JSON_observations':len(js),'all_JSON_single_target_no_duplicates_and_parser_equal':all(x['target_key_assignments_all_scopes']==1 and x['JSON_duplicate_key_extra_assignments_all_scopes']==0 and x['original_parser_equal_recovered_record'] for x in js),'general_rotation_vector_failures_remain':True,'repeated_baseline_and_exact_P90_pass_original_checks':True,'cause':'UNKNOWN; solver convergence/precision/orientation hypothesis not established','new_QM_calls_from_readonly_recovery_and_geometry':0}},
'Alpha':{'master33_parents':a['parent_count'],'observed_allocated_core_hours':a['allocated_core_hours_observed'],'active_at_master33':a['actual_active_job_ids'],'C_point':c,'CSV6':{'actual_job':'1884803','actual_parent_C0':True,'physical_records':1162144,'physical_rows_not_molecules':True,'all6_full_SHA_CRC_EOF':True,'technical_errors':0,'QM7b_native_identity':'UNKNOWN_UNCHANGED'},'COCONUT1884790':'latest queue observation RUNNING; closed prefixes are not full-source acceptance','C_controller':'finite500v2 max6, no duplicate manual submit or automatic retry/renew'},
'external':{'TDC':{'original_rows':81809,'derived_keys':81807,'unresolved_original_SMILES':2,'unknowns_retained':True},'Drugs':{'profile_C0_10000':True,'profile_unknowns':0,'full_job':'4521858','full_completion_pending_at_checkpoint':True,'all558002_conformers_and75099_CSV_names_authorized':True,'all290_native_SMILES_variant_groups_retained':True},'Kraken':{'profile_job':'4521859','profile_status':kr['status'],'actual_relation_rows':kr['complete_source_relationship_rows'],'completed_by_kind':kr['completed_by_kind'],'unknown_by_kind':kr['unknown_by_kind'],'root_union_counts':kr['root_union_counts'],'comparison_counts':kr['root_SMILES_vs_MolBlock_comparison_counts'],'full_review_pending':True},'source_or_global_decontamination_pool_release':False},
'resource_policy':previous['resource_policy'],'references':refs,
'next':['Keep actual Sprime179 chain advancing; after all closed independently retire future caps, finalize90069/Common/physical IDs/lateN1 gates.','Actual PM7controller6 CPU fixtures then root range grant, import completed5000 and run original remaining246 whole-molecule ranges.','Full-label source8/6 fixtures accepted; actual whole-cache storage/cost/reserve review then finite continuations, calibration/native frames/withinmolecule masks and finalCommon TRAIN norm.','Finish Drugs full/Kraken full, resolve TDC2 and QM7b native identity; keep fullC500/COCONUT running naturally.','D1-D7/D3/D5/D6/D7 and ordered10M/first2.5M UFF+D remain outstanding; no final PR.']}
checkpoint=Q.write_new(R/'control/active_checkpoint_v29.json',v)
text=f'''# 双集群实际进度 v9

生成于 {now}。全指南仍在执行，未开最终PR。

S′有限队列PID2761781，当前{len(closed)}批/{sum(x['valid_packets'] for x in closed):,}个验证包闭合，状态{s['status']}。早前激活锁冲突已经单独留证并修复；没有重跑相应科学任务。包闭合仍不等同Common或科学质量验收。

2,208个源footer全部完成。标签值有界缓存4521789 C0：228窗口闭合、10,455项跨全部14任务及base的比对一致、差异0，输出269,037,356字节（manifest前）。全量续算8件源码及6项新控制测试现已安装/实际通过；全量存储审核、源TRAIN校准、原生frame/precision、最终mask和D4仍待完成。

PM7前5,000分子/39,511记录4521775 C0：几何与HoF全部闭合，未启动/未知/错误0；复用了首256分子的耐久结果。全人口247分片有限控制器已安装，实际6项测试与S′179全闭合后的Root范围审批仍待完成。D7未验收。

P′限定15调用的留存输出已全部只读恢复，没有新增QM。实际输入坐标全部在原生十进制token传播界内符合刚性旋转；10份xTB JSON均单一目标字段、无重复键，原parser与留存记录一致。重复基线和精确90°旋转通过原检查，一般旋转仍失败。原15FAIL/2000与full HOLD保持，根因未确定，未放宽阈值。

TDC全部44成员/81,809原行身份扫描C0：81,807取得键，2项原SMILES未决保留。Drugs 10,000构象试点C0且未知0，全部558,002构象身份任务4521858已提交。Kraken身份试点4521859 C0，保留全部22,839来源关系及所有图键差异；全量审批继续处理。均未放行候选池。

Alpha已核验传回实际master33、原始记账、31个闭合PubChem分片和六份CSV全量小报告。PubChem点时闭合775万原始行，未去重去污染。六CSV任务1884803 C0，共1,162,144物理记录，含空行等非分子记录，不能作为分子数；QM7b原生图身份仍待解决。COCONUT与500片有限PubChem队列继续运行。

Main master34：{len(main['actual_parents'])}父任务/{main['observed_allocated_core_hours']:.6f}观察分配核时；Alpha master33：{a['parent_count']}父任务/{a['allocated_core_hours_observed']:.6f}核时。均为独立点时快照，失败和启动成本保留。

机器检查点 `{checkpoint['path']}`，SHA `{checkpoint['sha256']}`。
'''
p=Q.REPO/'docs/data_v1/secondary_main_actual_progress_20261027_v9.md';assert not p.exists();p.write_text(text,encoding='utf-8')
p=Q.REPO/'docs/interfaces/STATUS.md';old=p.read_bytes();prefix=f'''## 2026-10-27 最新实际进度 v9

见[实际进度v9](../data_v1/secondary_main_actual_progress_20261027_v9.md)。S′当前{len(closed)}批/{sum(x['valid_packets'] for x in closed):,}包闭合；PM7首5000分子/39511记录C0；标签有界缓存10455比对一致。P′实际输入几何/JSON选择已核验，一般旋转科学检查仍FAIL，质量HOLD保持。TDC全44身份扫描C0、2未决保留；Drugs全量已提交、Kraken身份试点C0。Alpha六CSV全量C0、PubChem31片/775万原行闭合。D1–D7及扩充最终交付继续执行。

'''.encode();p.write_bytes(prefix+old)
print(json.dumps({'checkpoint':checkpoint,'report':Q.pin(Q.REPO/'docs/data_v1/secondary_main_actual_progress_20261027_v9.md'),'Sprime_closed':len(closed),'guide_complete':False}))