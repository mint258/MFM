"""Idempotent local metadata publication after an actual Root sync closure."""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import re
import socket
import sys

HERE=Path(__file__).absolute().parent
sys.path.insert(0,str(HERE.parent/'native_additional4_metadata_v1'))
from close import P,N,ref,bind,read,write,require
ARCHIVE=P/'runs/phase1_full_corpus/wandb_archive/model_v3_20261025'
ROOT_HTML=P/'W&B_训练记录.html'


def content(value):return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()


def fresh_or_equal(path,raw):
    require(len(raw)<=2<<20,'Small publication artifact cap exceeded')
    if path.exists():require(path.read_bytes()==raw,'Existing immutable publication differs')
    else:
        with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return ref(path)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--closure',type=Path,required=True);p.add_argument('--run-ids',nargs='+',required=True)
    p.add_argument('--slug',required=True);p.add_argument('--output-root',type=Path,required=True)
    p.add_argument('--pins-sha256',required=True);a=p.parse_args()
    require(os.getuid()==1278 and socket.gethostname()=='sonmi','Actual Root local metadata publication required')
    source=ref(HERE/'source_pins.json');require(source['sha256']==a.pins_sha256,'Publisher source differs')
    own=read(source)
    for leaf in own['files']:
        actual=ref(HERE/leaf['relative_path'])
        require((actual['bytes'],actual['sha256'])==(leaf['bytes'],leaf['sha256']),'Publisher source changed')
    for raw in own['source_dependencies']:bind(raw)
    require(re.fullmatch('[a-z0-9_]{1,100}',a.slug),'Explicit safe publication slug required')
    closure_ref=ref(a.closure);closed=read(closure_ref)
    require(closed['schema'] in {'native_additional4_sync_Root_closure_v1','native_k17_sync_Root_closure_v1'}
        and closed['status']=='ROOT_CLOSED_C0_METADATA_VERIFIED'
        and closed['accepted_count']==len(a.run_ids)==len(set(a.run_ids))
        and [r['run_id'] for r in closed['records']]==a.run_ids
        and closed['SDK_current_independent_rehash'] is False and closed['SDK_bytes_read_or_decoded_by_Root'] is False,
        'Exact explicit successful Root closure and metadata-only boundary required')
    for job in closed['jobs']:
        require(job['actual_terminal']['state']=='COMPLETED' and job['actual_terminal']['exit_code']=='0:0'
            and job['source_before_after_and_current_equal'] is True,'Actual C0/source closure missing')
        bind(job['result']);bind(job['supervisor']);bind(job['inline_QA']);bind(job['inline_QA_XML'])
        bind(job['actual_terminal']['raw_sacct'])
        for path,sha in job['current_source_hashes'].items():require(ref(path)['sha256']==sha,'Closed source changed before publication')
    rows=[]
    for record in closed['records']:
        bind(record['result']);bind(record['actual_invocation']);value=record['actual_remote_metadata']
        require(value['run_id']==record['run_id'] and value['state']==('failed' if record['native_exit_code'] else 'finished'),
            'Preserved native run state differs')
        rows.append(dict(run_id=record['run_id'],url=record['url'],entity=value['entity'],project=value['project'],
            original_native_state=value['state'],native_exit_code=record['native_exit_code'],history_rows=value['history_rows'],
            first_step=value['first_step'],last_step=value['last_step'],sync_job_id=record['sync_job_id'],
            action=record['action'],source_scope=record['source_scope'],sync_result=record['result'],
            API_verification_scope='actual_sync_job_saved_complete_step_readback',
            cloud_API_requeried_by_Root=False,Root_current_SDK_independent_SHA_verified=False,
            SDK_hash_evidence='actual_worker_before_after; Root only current stat',scientific_acceptance=False))
    index=dict(schema='model_v3_explicit_online_append_index_v1',status='ONLINE_SYNC_JOB_AND_ROOT_METADATA_CLOSED',
        created_UTC=closed['created_UTC'],closure=closure_ref,records=rows,count=len(rows),
        finished=sum(row['original_native_state']=='finished' for row in rows),
        failed=sum(row['original_native_state']=='failed' for row in rows),
        fixed50_or_offline_index_modified=False,scientific_acceptance=False)
    stem='online_'+a.slug;index_path=ARCHIVE/(stem+'.json');page_path=ARCHIVE/(stem+'.html')
    title=f'模型 v3：新增 {len(rows)} 条在线记录核验'
    table=''.join('<tr>'+''.join('<td>'+cell+'</td>' for cell in (
        '<a href="'+html.escape(row['url'],quote=True)+'">'+html.escape(row['run_id'])+'</a>',
        html.escape(row['project']),row['original_native_state'],str(row['history_rows']),
        str(row['first_step'])+'–'+str(row['last_step']),row['sync_job_id'],html.escape(row['source_scope'] or '')))
        +'</tr>' for row in rows)
    page=('''<!doctype html><meta charset="utf-8"><title>'''+title+'''</title><style>body{font:15px system-ui;margin:2em;line-height:1.6}table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:.35em .6em}th{background:#eee}</style><h1>'''+title+'</h1><p>Root 元数据闭合时间（UTC）：'+html.escape(closed['created_UTC'])+
        '</p><p>实际同步 CPU 作业正常结束；保存的 API 回读已核对原运行 ID、项目、结束状态、全部历史行数与步范围。失败运行仍为 failed；profile 与单段日志完成不表示 B 精度验收。</p>'+
        '<p>Root 本次未重读 SDK 原始字节或重新查询云端；SDK 哈希证据来自实际同步作业内前后校验，本地源码、证书和 marker 的当前核验见元数据。<a href="'+index_path.name+'">元数据与来源</a></p>'+
        '<table><thead><tr><th>Run</th><th>Project</th><th>原状态</th><th>历史行数</th><th>Step</th><th>同步作业</th><th>范围</th></tr></thead><tbody>'+table+'</tbody></table>\n').encode()
    marker='data-model-v3-'+a.slug.replace('_','-')
    link=('<p '+marker+'><a href="runs/phase1_full_corpus/wandb_archive/model_v3_20261025/'+page_path.name+'">'+title+'</a></p>\n').encode()
    lock_path=ARCHIVE/'.archive.lock';lock_ref=ref(lock_path)
    descriptor=os.open(lock_path,os.O_RDWR|os.O_NOFOLLOW)
    try:
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(ref(lock_path)==lock_ref,'Archive lock identity/content changed')
        old_index=ref(ARCHIVE/'index.json');old_page=ref(ARCHIVE/'online_sync50_20261027_v1.html')
        before=ref(ROOT_HTML);old=ROOT_HTML.read_bytes();baseline=own['baseline_root_html']
        require(hashlib.sha256(old[:baseline['bytes']]).hexdigest()==baseline['sha256'],'Original775B root prefix differs')
        a.output_root.mkdir(mode=0o700,parents=True,exist_ok=True)
        backup_path=a.output_root/'root_html_before_append.html'
        if backup_path.exists():
            backup=ref(backup_path);require(old.startswith(backup_path.read_bytes()),'Current root lost original backup prefix')
        else:backup=fresh_or_equal(backup_path,old)
        index_ref=fresh_or_equal(index_path,content(index));page_ref=fresh_or_equal(page_path,page)
        token=marker.encode();count=old.count(token)
        require(count in (0,1),'Duplicate unified entry marker')
        changed=count==0
        if changed:
            tmp=ROOT_HTML.parent/('.'+stem+'.root_pending')
            with tmp.open('xb') as stream:
                stream.write(old+b'\n'+link);stream.flush();os.fsync(stream.fileno())
            os.chmod(tmp,ROOT_HTML.stat().st_mode&0o777)
            require(ref(ROOT_HTML)==before,'Unified HTML changed concurrently')
            os.replace(tmp,ROOT_HTML)
        else:require(link.strip() in old,'Existing marker has a different link')
        current=ROOT_HTML.read_bytes()
        require(current.startswith(old) and current.count(token)==1,'Append-only prefix or idempotence failed')
        require(ref(ARCHIVE/'index.json')==old_index and ref(ARCHIVE/'online_sync50_20261027_v1.html')==old_page,
            'Old offline index/online50 page changed during publication')
        receipt=dict(schema='model_v3_online_metadata_append_receipt_v1',status='PUBLISHED_IDEMPOTENT_METADATA',
            source_manifest=source,closure=closure_ref,run_ids=a.run_ids,index=index_ref,page=page_ref,
            root_html_before_this_invocation=before,root_html_backup=backup,root_html_after=ref(ROOT_HTML),
            root_entry_appended_this_invocation=changed,original775B_prefix_preserved=True,
            old_offline_index_unchanged=old_index,old_online50_page_unchanged=old_page,
            SDK_read_or_retransmitted=False,cloud_API_called=False,scientific_acceptance=False)
        receipt_path=a.output_root/('PUBLISH_RECEIPT.json' if changed else 'IDEMPOTENT_RECHECK.json')
        if receipt_path.exists():require(read(receipt_path)['index']==index_ref,'Existing receipt differs')
        else:write(receipt_path,receipt)
    finally:os.close(descriptor)
    print(json.dumps(dict(status='PUBLISHED_IDEMPOTENT_METADATA',run_ids=a.run_ids,
        index=index_ref,page=page_ref,root_entry_appended=changed,SDK_read=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())
