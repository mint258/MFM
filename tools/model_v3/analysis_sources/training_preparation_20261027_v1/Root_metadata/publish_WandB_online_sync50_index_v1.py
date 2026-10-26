"""One explicit metadata publication after all fixed50 actual C0 closures."""
import argparse,datetime,hashlib,html,json,os,pathlib,stat
from urllib.parse import quote
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
p=argparse.ArgumentParser();p.add_argument('--closure',type=pathlib.Path,required=True);a=p.parse_args();v=json.loads(a.closure.read_bytes());assert v['status']=='EXPLICIT_COMPLETED_PARENTS_C0_AND_METADATA_VERIFIED' and v['accepted_count']==50 and v['remaining_count']==0 and v['next_run_ids']==[]
def ref(p):
 d=p.read_bytes();return dict(path=str(p),bytes=len(d),sha256=hashlib.sha256(d).hexdigest())
f=json.loads(pathlib.Path(v['fixed50']['path']).read_bytes());assert ref(pathlib.Path(v['fixed50']['path']))==v['fixed50'];rows=f['runs'];assert len(rows)==50 and set(v['accepted_run_ids'])=={x['run_id'] for x in rows}
accepted={x['run_id']:{**x,'job_id':j['job_id']} for j in v['jobs'] for x in j['records']};assert len(accepted)==50
body=[]
for row in rows:
 x=accepted[row['run_id']];rp=pathlib.Path(x['result']['path']);assert ref(rp)==x['result'];r=json.loads(rp.read_bytes());m=r['actual_remote_metadata'];assert m==r['expected_remote_metadata'] and r['failure'] is None and r['source_hash_before_after_equal'] is True and r['original_sync_marker_unchanged'] is True
 url='https://wandb.ai/'+quote(m['entity'],safe='')+'/'+quote(m['project'],safe='')+'/runs/'+quote(row['run_id'],safe='')
 body.append('<tr><td><a href="'+html.escape(url,quote=True)+'">'+html.escape(row['run_id'])+'</a></td><td>'+html.escape(m['project'])+'</td><td>'+html.escape(m['state'])+'</td><td>'+str(m['history_rows'])+'</td><td>'+str(m['first_step'])+'–'+str(m['last_step'])+'</td><td>'+x['job_id']+'</td><td>'+html.escape(r['action'])+'</td></tr>')
finished=sum(x['native_exit_code']==0 for x in rows);failed=sum(x['native_exit_code']==1 for x in rows);assert finished==37 and failed==13
stamp=datetime.datetime.now(datetime.timezone.utc).isoformat();page='<!doctype html><meta charset="utf-8"><title>模型 v3 W&B 在线同步核验</title><style>body{font:15px system-ui;margin:2em;line-height:1.6}table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:.35em .6em}th{background:#eee}</style><h1>模型 v3：50 条完整记录已同步核验</h1><p>生成时间（UTC）：'+html.escape(stamp)+'</p><p>固定 50 条完整日志均已核验在线运行 ID、项目、原始结束状态、全部历史行数及步数范围；37 条 finished，13 条 failed。原始离线文件和同步标记保持不变。每条核验对应表内实际正常结束的 CPU 作业，不代表模型科学验收。</p><p>7 条原生结构不完整的历史日志未上传：na6kbsm1、nkuzk09z、qpz3wu8g、541vw89g、l073kg4n、6r1osqwv、nwnifyhl。它们的原件及失败证据保留。本页范围仅为固定 50 条；之后产生的 S profile 和长程分段另行核验。</p><p>4sgxpx8j 原已在作业 4521410 的官方同步命令中上传；本轮仅核验已有云端记录，未重发，原 4521410 失败终态保留。</p><table><thead><tr><th>Run</th><th>Project</th><th>原状态</th><th>历史行数</th><th>Step</th><th>核验作业</th><th>动作</th></tr></thead><tbody>'+''.join(body)+'</tbody></table>'
archive=B/'runs/phase1_full_corpus/wandb_archive/model_v3_20261025';assert archive.is_dir();out=archive/'online_sync50_20261027_v1.html';assert not out.exists();out.write_text(page,encoding='utf-8')
entry=B/'W&B_训练记录.html';s=entry.lstat();assert stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and not entry.is_symlink();before=entry.read_bytes();assert b'data-model-v3-online-20261027-v1' not in before
backup=N/'WandB_unified_entry_before_online50_v1.html';assert not backup.exists();backup.write_bytes(before)
addition='\n<p data-model-v3-online-20261027-v1><a href="runs/phase1_full_corpus/wandb_archive/model_v3_20261025/online_sync50_20261027_v1.html">模型 v3：50 条完整记录的在线同步核验与 W&amp;B 链接</a></p>\n'.encode('utf-8')
with entry.open('ab') as stream:stream.write(addition);stream.flush();os.fsync(stream.fileno())
assert entry.read_bytes()==before+addition
report=dict(schema='model_v3_WandB_online_sync50_index_publication_actual_v1',status='PUBLISHED_FIXED50_VERIFIED_ONLINE_INDEX',captured_utc=stamp,closure=ref(a.closure),online_index=ref(out),unified_entry_before=ref(backup),unified_entry_after=ref(entry),existing_entry_prefix_retained=True,counts=dict(complete_verified=50,original_finished=37,original_failed=13,incomplete_excluded=7),later_native_logs_included=False,SDKs_deleted=False,science_acceptance=False)
r=N/'WandB_sync50_online_index_publication_actual_v1.json';assert not r.exists();r.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(index=ref(out),receipt=ref(r),counts=report['counts'])))