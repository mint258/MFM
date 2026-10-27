"""Record point-time closed metadata; never inspect scientific payload bodies."""
import datetime,json
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q
Q.on_login();R=Q.ROOT;refs={}
def read(key,rel):
 p=R/rel;refs[key]=Q.pin(p);return Q.load(p)
previous=read('previous','control/active_checkpoint_v27.json')
main=read('Main_master32','control/owned_accounting_checkpoint32_cpu_auto_memory_20261027_v1.json')
base='control/secondary_cluster_20261026_v1/alpha_short_followups_v1/'
alpha=read('Alpha_master32',base+'alpha_owned_accounting_checkpoint32_v1.json')
cp=read('Alpha_C_closed20',base+'pubchem_C_actual_closed_progress_20261027_v2.json')
transfer=read('Alpha32_transport_manifest',base+'alpha32_point_metadata_transfer_manifest_v1.json')
assert transfer['schema']=='ALPHA_METADATA_TRANSFER_MANIFEST_V1' and transfer['uid']==1264 and len(transfer['references'])==3
for producer in transfer['references']:
 copy=R/base/Path(producer['path']).name;actual=Q.pin(copy)
 assert actual['bytes']==producer['bytes'] and actual['sha256']==producer['sha256']
raw=alpha['raw_sacct_reference'];copy=R/base/Path(raw['path']).name
assert Q.pin(copy)['sha256']==raw['sha256'] and Q.pin(copy)['bytes']==raw['bytes']
refs['Alpha_master32_raw_Maincopy']=Q.pin(copy)
l=Q.load(R/'control/sprime_wave2_controller_v1/live_v1/latest.json');refs['Sprime_state']=l['state_reference'];assert Q.pin(l['state_reference']['path'])==l['state_reference'];s=Q.load(l['state_reference']['path'])
closed=[x['close']['closure_counts'] for x in s['stages'].values() if x.get('close',{}).get('closure_counts',{}).get('valid_packets',0)>0]
f=read('full_footer','artifacts/labels/source_status_v1/footer_continuation_full_v1/manifest.json')
assert f['observed_files']==2208 and not f['errors'] and not f['pending_file_ids'] and f['reused_original_Parquet_open_calls']==0
external={m:read(m+'_probe','artifacts/expansion/marcel_'+m+'/receipt.json') for m in ('drugs_identity_v1','kraken_opcodes_v1')}
for key,rel in {
 'footer_partial_cost':'control/accounting/footer_partial_4521720_v1.json',
 'footer_continuation_C0_cost':'control/accounting/footer_continuation_4521749_v1.json',
 'Drugs_C0_cost':'control/accounting/marcel_drugs_identity_4521750_v1.json',
 'Kraken_C0_cost':'control/accounting/marcel_kraken_opcodes_4521755_v1.json',
 'source_publication16':'control/github_source_publication_v16.json',
 'repository_check18_PASS':'control/repository_source_check_v18_actual.json',
 'TDC_identity_actual_submission':'control/submissions/dv1_q_tdc_all44_identity_20261027_v1.json',
 'TDC_source_contract_correction':'control/tdc_identity_source_contract_correction_v1.json',
 'PM7_population_source8':'control/pm7_population_source8_install_v1.json',
 'PM7_population256_spec_not_submitted':'control/pm7_population256_stage_v1/stage_spec.json',
 'PM7_population_additive_quota':'control/pm7_population256_root_approvals_v1/quota_review.json',
 'Pprime_zeroQM_spec_not_submitted':'control/pprime_causal15_prepare_stage_v1/stage_spec.json',
}.items():refs[key]=Q.pin(R/rel)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
v={'schema':'DATA_V1_ACTIVE_CHECKPOINT_V28','observed_utc':now,'goal_complete':False,'guide_complete':False,
 'stop_instruction':previous['stop_instruction'],'sessions':previous['sessions'],
 'source':{'execution_commit':'c66d3303d7aeb4b11a5f9e96775f13d1a5ea0204','public_commit':'81fb0823c4023e248c56e388a77f34b9bbb62934','exact_tree':'8f56a88dfd2dbed1d8d894b412b616c49bd7e986','new_uncommitted_source':'footer continuation3,TDC identity8 with contract correction,PM7 population8,this generator and new progress docs','new_source_check_commit_pending':True,'final_PR':False},
 'Main':{'master32_parents':len(main['actual_parents']),'observed_core_hours':main['observed_allocated_core_hours'],
  'Sprime':{'controller_pid':2716517,'finite_seconds':60000,'status':s['status'],'reason':s.get('reason'),'closed_batches':len(closed),'valid_packets':sum(x['valid_packets'] for x in closed),'closure_is_scientific_success_or_Common':False,'state':refs['Sprime_state'],'do_not_manually_duplicate_chain':True},
  'labels_footer':{k:f[k] for k in ('status','observed_files','observed_label_files','observed_base_files','reused_files','newly_observed_files','actual_row_groups','actual_column_chunks','actual_source_metadata_bytes_read','actual_label_footer_rows','actual_base_footer_rows','reused_original_Parquet_open_calls','guide1p5_complete','normalization_completed')},
  'labels_numeric':'512 lossless pilot closed; new bounded parts source in progress. Full registry masks/native precision/frame/robustTRAIN calibration/Common/norm/D4 not accepted.',
  'PM7':'CanonicalHoF32 actual203 valid/16golden exact. New whole-population driver8 installed. Literal256 plan,additive64GiB quota,scope/spec ready NOT submitted on13 while higher-priority Sprime owns capacity. Keep original effective8GiB STOP; geometry PENDING and technical closure separate; no full/D7 acceptance.',
  'Pprime':'Original15FAIL/full2000HOLD remain. Fixed6/15call diagnostic zeroQM prepare ready NOT submitted on13. Original900s timeout/program/keywords/seeds. Originalengine initialize asset SHA before any native invoke. Resource-only true node19 adaptation under static audit, not applied.'},
 'Alpha':{'master32_parents':alpha['parent_count'],'observed_core_hours':alpha['allocated_core_hours_observed'],'active_at_snapshot':alpha['actual_active_job_ids'],'C_closed_point':cp,'controller_pid1838':'finite500v2,reviewed original state dir v1,max6C,noauto retry or auto renew','COCONUT1884790':'last observed RUNNING8h16m,no activeSQLite query','CSV1884803':'last observed RUNNING2h08m,output growing,no activeParquet reads'},
 'external':{'Drugs':external['drugs_identity_v1']['result']['observation'],'Kraken':external['kraken_opcodes_v1']['result']['observation'],'TDC':'Actual4521757 submitted all44/81809 original rows frozen identity keys; completion/accounting pending. Contract corrected68 total=23dirs+44CSV+1other before body; no headerprobe edit.','global_decontamination_pool_release':False},
 'resource_policy':previous['resource_policy'],'references':refs,
 'next':['Complete bounded numeric labels then full TRAIN calibration/native frames/masks and exact normalization once Common frozen.','Keep Sprime179 chain advancing and later final90069 index/Common physical IDs/lateN1 quality gates.','Run actual PM7 population256/17pure then <=5000 batches; run zeroQM Pprime prep and separately reviewed15QA without releasing failed scientific gate.','Finish actual TDC keys,Kraken primitive structure and all Drugs native identities; all planned sources including QM7b need closure before pool release.','Continue Alpha full500C/COCONUT/CSV natural completion and accounted finite lease control.','D1-D7,D3 real50kTRAIN5kVAL,D5nested120k240k600k and20kheldconfs,D6F32familyLMDB/localCPUthroughput,D7 fullpopulation orders/cards; filtered1M/ordered10M/10kUFFpilot/first2.5M UFF+D outstanding.']}
checkpoint=Q.write_new(R/'control/active_checkpoint_v28.json',v)
text=f'''# 双集群实际进度 v8

生成于 {now}。这是实际闭合元数据的点时汇总，全指南仍在执行。

标签目录续算 4521749 C0/113秒/16核，2,208 个文件全部完成、待处理0、错误0。复用407个已闭合文件且未重读其Parquet；新完成1,801个。实际共1,317,456行组、41,454,804列块。这里只核验目录；数值标签、掩码和归一化仍待完成。

S′ wave2当前 {len(closed)} 批、{sum(x['valid_packets'] for x in closed):,} 个验证包闭合，有限队列状态为 {s['status']}。包闭合不等同科学成功或Common验收。

Drugs结构核验4521750 C0/242秒：75,099个原CSV名称、558,002个SDF记录，全数名称对应；290个名称组存在不同SMILES字节，后继保留全部原ID与构象身份，不能任挑一个。Kraken4521755 C0/32秒，安全opcode探针完整到EOF，未执行pickle构造；受限原语结构读取待完成。TDC4521757已提交全部44源成员的81,809行身份投影。

Alpha点时闭合20个PubChem分片、5,000,000原始行，其中4,697,224通过当前化学筛选、302,620化学排除、156技术未决；尚未去重去污染，不能当作可用候选池。完整500片有限队列、COCONUT与CSV全源仍在运行。

Main master32为{len(main['actual_parents'])}父任务/{main['observed_allocated_core_hours']:.6f}观察分配核时；Alpha master32为{alpha['parent_count']}父任务/{alpha['allocated_core_hours_observed']:.6f}核时，失败与启动成本保留。

PM7人口缓存首256分子规格已准备，P′限定诊断的零QM准备规格也已准备，二者当前均未提交，等待CPU13容量或真实新节点资源绑定。原P′15FAIL/2000与full HOLD保留。D1–D7及扩充最终交付未全部完成，未开最终PR。

机器检查点 `{checkpoint['path']}`，SHA `{checkpoint['sha256']}`。
'''
p=Q.REPO/'docs/data_v1/secondary_main_actual_progress_20261027_v8.md';assert not p.exists();p.write_text(text,encoding='utf-8')
s=Q.REPO/'docs/interfaces/STATUS.md';old=s.read_bytes();prefix=f'''## 2026-10-27 最新实际进度：全部标签目录闭合

见[实际进度v8](../data_v1/secondary_main_actual_progress_20261027_v8.md)。2,208个源footer全部完成，待处理/错误均0；标签值、掩码、D4仍未放行。S′当前{len(closed)}批/{sum(x['valid_packets'] for x in closed):,}验证包闭合。Drugs原名称全对应，290多SMILES组完整保留；Kraken安全opcode探针C0；TDC全44身份任务已提交。Alpha点时20片/500万原始行完成，尚未去重去污染。原P′质量HOLD保持，D1–D7与扩充交付继续执行，未开最终PR。

'''.encode();s.write_bytes(prefix+old)
print(json.dumps({'checkpoint':checkpoint,'report':Q.pin(p),'Sprime_closed':len(closed),'goal_complete':False}))