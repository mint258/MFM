"""Publish final B3 task delivery from closed producer metadata only.

Root invokes this only after observing the actual closing Native parent C0.
No Parquet, SQLite, numeric label, hash, readback or independent QA is opened.
"""
import argparse,collections,json,os
from pathlib import Path

REPO=Path(__file__).absolute().parents[4]
DATA=Path('/lfshome/zixiao/data_v1_20261025')

def need(ok,message):
    if not ok:raise ValueError(message)

def load(filename):return json.loads(Path(filename).read_text(encoding='utf-8-sig'))
def reference(filename):return {'path':str(filename),'bytes':Path(filename).stat().st_size}
def ref_path(value):return value['path'] if isinstance(value,dict) else str(value)

def assemble(scope,producer,initial,refs,closing_parent):
    need(closing_parent['state']=='COMPLETED' and closing_parent['exit_code']=='0:0','ACTUAL_NATIVE_C0_REQUIRED_BEFORE_DELIVERY')
    need(str(closing_parent['job_id'])==str(producer['actual_job_id']),'ACTUAL_CLOSING_PARENT_ID_DIFFERS')
    need(scope['schema']=='PPRIME_FINAL_PHYSICAL_FIRST2_CONTINUATION_SCOPE_V1','FINAL_FROZEN_PHYSICAL_SCOPE_REQUIRED')
    need(producer['schema']=='PPRIME_FINAL_PHYSICAL_FIRST2_PRODUCER_V1'
         and producer['status']=='COMPLETED_ALL_MISSING_PHYSICAL_RECORDS','CLOSED_FINAL_NATIVE_PRODUCER_REQUIRED')
    need(ref_path(producer['scope'])==refs['scope']['path'],'PRODUCER_FINAL_SCOPE_REFERENCE_DIFFERS')
    needed=scope['needed_records'];completed=producer['records_completed'];reused=scope['reused_closed_records']
    need(scope['unknown_native_intents']==0 and producer['prior_scope_unknown_native_intents']==0
         and completed==needed==producer['records_assigned'],'FINAL_PHYSICAL_RECORD_COMPLETION_REQUIRED')
    claims=producer['claim_status_counts']
    need(claims.get('CLOSED_TWELVE_OUTCOMES',0)==needed and sum(claims.values())==needed,'UNCLOSED_NATIVE_INTENT_REMAINS')
    need(scope['actual_first2_records']==reused+needed,'FINAL_REUSED_PLUS_NEW_PARTITION_DIFFERS')
    need(producer['original_native_recipe_900s_unchanged'] and producer['no_Pprime_rank_ge_2']
         and producer['no_new_N1_generation'] and producer['no_automatic_native_retry'],'ORIGINAL_PPRIME_SCIENTIFIC_SCOPE_REQUIRED')
    need(scope['no_Pprime_rank_ge_2'] and scope['no_new_N1_generation'] and scope['no_padding_or_duplication'],'FROZEN_REAL_FIRST2_ONLY_REQUIRED')
    batches=producer['batches']
    need(sum(batch['completed'] for batch in batches)==completed
         and sum(batch['all12_success'] for batch in batches)==producer['all12_success'],'CLOSED_PRODUCER_METADATA_TOTALS_DIFFER')
    need(0<=producer['all12_success']<=completed,'INVALID_PRODUCER_SUCCESS_COUNT')
    families=collections.defaultdict(lambda:{'files':0,'bytes':0,'rows':0})
    for batch in batches:
        for item in batch['files']:
            target=families[item['family']];target['files']+=1;target['bytes']+=item['bytes'];target['rows']+=item['rows']
    raw_bytes=sum(batch['raw_outputs']['bytes'] for batch in batches)
    history={'delivery_reference':refs['initial_delivery'],'producer_manifest_reference':refs['initial_manifest'],
        'raw_output_root':str(Path(initial['manifest']).parent),'missing_molecule_ids':initial['missing_molecule_ids'],
        'missing_reason':initial['missing_reason'],'molecules':initial['molecules'],
        'records_completed':initial['first2_records_completed'],'all12_success':initial['all12_success'],
        'records_with_scientific_task_failures':initial['records_with_scientific_task_failures'],
        'status_at_initial_delivery':initial['status']}
    return {'schema':'WINDOW2_FINAL_PPRIME_FIRST2_DELIVERY_V1','status':'FINAL_ACTUAL_FIRST2_COMPUTATION_COMPLETE',
        'scope_reference':refs['scope'],'producer_manifest_reference':refs['producer'],
        'actual_closing_native_parent':closing_parent,'producer_status':producer['status'],
        'population':'Frozen final Common TRAIN/VAL; all historical raw roles retained',
        'actual_chosen_MIDs':scope['actual_chosen_MIDs'],'actual_first2_records':scope['actual_first2_records'],
        'existing_closed_geometry_records_reused':reused,'new_geometry_records_completed':completed,
        'new_records_all12_success':producer['all12_success'],
        'new_records_with_scientific_task_failures':completed-producer['all12_success'],'unresolved_records':0,
        'reused_subset_all12_success':None,'success_count_scope':'New final delta only; no extrapolation to reused subset',
        'shortfall_state_reference':scope['record_level_state_table'],'shortfall_counts':scope['shortfall_counts'],
        'historical_initial_fill':history,'original_ready_delivery_reference':refs['original_ready'],
        'original_ready_and_initial_raw_labels_retained':True,'new_raw_output_root':str(Path(refs['producer']['path']).parent),
        'new_family_parquet':dict(sorted(families.items())),
        'new_family_parquet_files':sum(value['files'] for value in families.values()),
        'new_family_parquet_bytes':sum(value['bytes'] for value in families.values()),'new_raw_output_sqlite_bytes':raw_bytes,
        'fixed_random_seed':20261025,'selection':'first min(2,actual_available) in the frozen physical-ID order',
        'native_tasks_per_geometry':12,'native_timeout_seconds':900,'old_closed_QM_recomputed':False,
        'Pprime_third_or_later_computed':False,'new_N1_generation':False,'padding_or_duplicate_geometry':False,
        'scientific_task_failures_retained_with_original_masks':True,'independent_readback':False,
        'additional_hash_or_QA_jobs':False,'D4_D6_or_Model_ACK_claimed':False}

def document(value):
    history=value['historical_initial_fill'];parent=value['actual_closing_native_parent']
    return f'''# B3 最终实际前二 P′ 交付

最终 Common TRAIN/VAL 范围为 {value['actual_chosen_MIDs']:,} 个 MID、{value['actual_first2_records']:,} 条实际固定随机前二记录；复用既有闭合几何标签 {value['existing_closed_geometry_records_reused']:,} 条，只新增完成 {value['new_geometry_records_completed']:,} 条。不足两个真实几何的原因保留在 scope 原状态表，不复制、不补齐、不另生成 N1，不计算第三及以后构象。

闭合 Native parent 为 {parent['job_id']}（{parent['state']}，{parent['exit_code']}，elapsed {parent.get('elapsed','未单列')}）。保持原十二任务、每调用 900 秒和 seed 20261025。新增记录中 {value['new_records_all12_success']:,} 条十二项均成功，{value['new_records_with_scientific_task_failures']:,} 条实际任务失败按原标签与掩码保留，未解决记录 0；不外推复用子集的成功率。

历史初批 {history['molecules']:,} 个分子、{history['records_completed']:,} 条记录的交付保留：原 ready 之后闭合的 80,740 个 TRAIN/VAL 成功补齐分子，扣除 12 个已 ready，得到 80,728 个初批缺失 MID。原缺失 MID 引用、原始原因、{history['all12_success']:,} 条全成功和 {history['records_with_scientific_task_failures']:,} 条科学任务失败均在最终配置 historical_initial_fill 中保留；这批原文件和更早 ready 原标签均未重算或删除。

- [最终配置](../../configs/data_v1/Pprime_final_first2_v1_DELIVERY.json)：完整计数、path/bytes、逐 family 元数据及状态表引用。
- [历史初批配置](../../configs/data_v1/Pprime_initial_fill_v1_DELIVERY.json)：原缺失原因与原 MID 表。
- 最终 scope：`{value['scope_reference']['path']}`。
- 新增 raw root：`{value['new_raw_output_root']}`；初批 raw root：`{history['raw_output_root']}`。

本交付仅闭合 B3 最终实际前二计算；D4 独立统计、D6 和 Model ACK 由各自交付声明。统计直接复用原 producer 元数据，无额外 SHA、数值读回、独立 QA 或逐作业验收收据。
'''

def write(filename,text):
    filename=Path(filename);filename.parent.mkdir(parents=True,exist_ok=True)
    temporary=filename.with_name(filename.name+'.writing');temporary.write_text(text,encoding='utf-8');os.replace(temporary,filename)

def publish(args):
    scope=load(args.scope);producer=load(args.producer);initial=load(args.initial_delivery)
    refs={'scope':reference(args.scope),'producer':reference(args.producer),'initial_delivery':reference(args.initial_delivery),
        'initial_manifest':reference(initial['manifest']),'original_ready':reference(args.original_ready)}
    closing={'job_id':str(args.native_job_id),'state':args.native_state,'exit_code':args.native_exit_code}
    if args.native_elapsed:closing['elapsed']=args.native_elapsed
    value=assemble(scope,producer,initial,refs,closing)
    write(args.document,document(value));value['task_document_reference']=reference(args.document)
    write(args.output,json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    return reference(args.output)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope',default=str(DATA/'window2_final_pprime_scope_20261106_v3/manifest.json'))
    parser.add_argument('--producer',default=str(DATA/'window2_final_pprime_labels_20261105_v1/manifest.json'))
    parser.add_argument('--initial-delivery',default=str(REPO/'configs/data_v1/Pprime_initial_fill_v1_DELIVERY.json'))
    parser.add_argument('--original-ready',default='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/pprime_complete_remaining_20261104_v1/final_delivery/completion_manifest.json')
    parser.add_argument('--native-job-id',required=True);parser.add_argument('--native-state',required=True)
    parser.add_argument('--native-exit-code',required=True);parser.add_argument('--native-elapsed')
    parser.add_argument('--output',default=str(REPO/'configs/data_v1/Pprime_final_first2_v1_DELIVERY.json'))
    parser.add_argument('--document',default=str(REPO/'docs/data_v1/Pprime_final_first2_v1_DELIVERY.md'))
    args=parser.parse_args();print(json.dumps(publish(args)),flush=True)

if __name__=='__main__':main()
