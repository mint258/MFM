"""Reproducible report from saved small actual receipts and Slurm/accounting metadata."""
import argparse,hashlib,json,subprocess,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import ROOT,REPO,on_login,pin,write_new

def main():
 on_login();p=argparse.ArgumentParser();p.add_argument('--tag',required=True);a=p.parse_args()
 assert a.tag.replace('_','').isalnum()
 inputs={
  'raw':ROOT/'artifacts/expansion/raw/sb5_pubchem_raw_inventory_v2_cpu_default_memory_v1/receipt.json',
  'shard0':ROOT/'artifacts/labels/source_status_v1/auto_memory_v1/shard_00/manifest.json',
  'shard0_resource':ROOT/'artifacts/labels/source_status_v1/auto_memory_v1/shard_00_resource_observation/closure.json',
  'frame':ROOT/'artifacts/vector_frame_audit/cpu_auto_memory_20261026_v1/frame_evaluation.json',
  'frame_run':ROOT/'artifacts/vector_frame_audit/cpu_auto_memory_20261026_v1/run/run_closed.json',
  'retention':ROOT/'artifacts/pprime_retention_v1/cpu_auto_memory_20261026_v2/stage_receipt.json',
  'secondary_environment':ROOT/'control/secondary_cluster_20261026_v1/offline_environment_1884762.json',
  'primary_authority':REPO/'configs/data_v1/user_cpu_auto_memory_20261026_v1.json',
  'secondary_authority':REPO/'configs/data_v1/secondary_cluster_user_authorization_20261026_v1.json',
  'source_check':ROOT/'control/secondary_all_new_sources_check_20261026_v1.json'}
 refs={k:pin(v) for k,v in inputs.items()};x={k:json.loads(v.read_text()) for k,v in inputs.items()}
 jobs=['4521092','4521093','4521094','4521110','4521118','4521124','4521125','4521129','4521130','4521131','4521132']
 raw=subprocess.run(['sacct','-j',','.join(jobs),'-X','-n','-P','-o','JobID,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'],check=True,text=True,capture_output=True).stdout
 rows=[]
 for line in raw.splitlines():
  v=line.split('|')
  if len(v)>=6 and v[0] in jobs:rows.append(dict(zip(('job_id','state','exit_code','elapsed_seconds','cpus','node'),v[:6])))
 assert len(rows)==len(jobs)
 counts={'pubchem_cid_smiles_records':x['raw']['counts']['records'],'pubchem_gzip_crc_full_eof':x['raw']['gzip_EOF_CRC_revalidated'],'pubchem_source_parts':x['raw']['counts'].get('part_count',x['raw']['source_index'].get('part_count')),
 'first_label_source_files':len(x['shard0']['files']),'first_label_canonical_task_rows':x['shard0']['canonical_rows'],'first_label_allocation_parent':'4521118','first_label_output_bytes':x['shard0']['unique_inode_output_bytes_before_manifest'],'first_label_peak_rss_bytes':x['shard0_resource']['maximum_observed_tree_rss_bytes'],
 'retained_frame_cases':len(x['frame_run']['results']),'frame_measurements':len(x['frame']['measurements']),'frame_contradictions':len(x['frame']['contradictions']),'frame_execution_errors':x['frame_run']['execution_errors'],'same_geometry_controls':len(x['frame']['same_geometry_SP_gradient_controls']),
 'retention_counts':x['retention']['details']['actual_counts'],'secondary_environment_status':x['secondary_environment']['status'],'secondary_environment_actual_job':x['secondary_environment']['job_id'],'secondary_actual_versions':x['secondary_environment']['versions'],'source_check':x['source_check']['status']}
 summary={'schema':'SECONDARY_MAIN_ACTUAL_PROGRESS_V1','observed_at_utc':datetime.now(timezone.utc).isoformat(),'inputs':refs,'computed_statistics':counts,'actual_main_stage_parent_rows':rows,'raw_sacct':raw,'source':pin(Path(__file__).absolute()),'guide_complete':False,'PPRIME_2000_full_QM_HOLD':True,'primary_and_secondary_job_ids_are_separate_namespaces':True,'snapshot_running_elapsed_is_not_terminal_cost':True,'no_scientific_data_body_read':True}
 summary_path=ROOT/f'control/secondary_main_actual_progress_{a.tag}.json';write_new(summary_path,summary)
 lines=['# 双集群与主数据线实际进度（脚本生成）','',f"观测时间：{summary['observed_at_utc']}",'','## 目的','','落实用户新增 alpha 集群授权，记录主集群已闭合工作及仍需通过的科学门槛。当前集群没有金钱计算费用；分配核时仍用于效率验收。','', '## 输入与哈希','']
 for k,v in refs.items():lines.append(f"- `{k}`：`{v['path']}`；{v['bytes']} B；SHA256 `{v['sha256']}`。")
 lines+=['','## 规则与参数','','Main CPU 分析节点为实际 cpu 分区2、8–19；S′/UFF/QM 11–19。Alpha 实际 CPU 分区1、3–6、sonmi1。每任务16CPU、最长48h、CPU-only；SBATCH 不指定内存或 exclusive，保留实际RSS/可用内存观察和200GB存储余量。两集群按端点、UID及实际job分别记录。UFF/QM配方、ROUTINE整分子VAL及除Se外的阈值不变。','','## 脚本计算的实际统计','', '```json',json.dumps(counts,ensure_ascii=False,indent=2),'```','','选定阶段的实际主集群父任务如下；本表不是全项目总成本，RUNNING耗时只是本次快照。','','|Job|状态|退出码|分配秒|CPU|节点|','|---|---|---|---:|---:|---|']
 for row in rows:lines.append('|'+ '|'.join(row[k] for k in ('job_id','state','exit_code','elapsed_seconds','cpus','node'))+'|')
 lines+=['','## 异常与处理','','原72项frame试验全部执行留存，但原15个协变准则失败仍保留；不放宽容差、不将READY或解析完成称作PASS，2000/full P′ QM保持HOLD。新只读诊断将核查实际输入几何与原生打印精度。retention首次4521125因共享父目录缺失失败；只修复该目录，采用新输出4521129成功，旧失败和成本保留。Alpha首次两次环境构建失败记录保留，离线安装1884762完成；只达到软件兼容测试准备状态。','','## 已知限制','','PubChem 124M原始行清点不是化学筛选、去污染或候选池。标签首分片不是完整1.5或D4；共同人群、单位/原生精度/数组shape及TRAIN-only统计仍未定稿。Alpha软件环境就绪不代表16个真实科学控制通过，也不代表已生成正式新数据。S′恢复仍按真实终态判断，不依据进度快照声明完成。D1模型共同签认及D1–D7、ordered10M、第一批2.5M实际生成仍未全部完成。','',f"完整机器证据：`{summary_path}`；本报告生成器：`{Path(__file__).absolute()}`。",'']
 output=REPO/f'docs/data_v1/secondary_main_actual_progress_{a.tag}.md'
 with output.open('x',encoding='utf-8',newline='\n') as stream:stream.write('\n'.join(lines))
 print(json.dumps({'summary':pin(summary_path),'report':pin(output),'guide_complete':False}))
if __name__=='__main__':main()