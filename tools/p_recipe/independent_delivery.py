"""Seal independent P report sections and final endpoint hashes once.

Only closed scalar producers are consumed. No model loading, fitting, bootstrap,
telemetry summarization or plot regeneration occurs. D's A4 is inserted later.
"""
import json
import os
from pathlib import Path
import re
import stat
import time

A4_MARKER='<!-- P_A4_SECTION_PENDING -->'
SEAL_PATH='results/p_recipe/independent_delivery_20261126.json'
HASH_PATH='results/p_recipe/final_checkpoint_sha256.json'
BODY_PATH='docs/p_recipe/REPORT_P_SECTIONS.md'


def read(path):
    return json.loads(Path(path).read_text())


def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp.'+str(os.getpid()))
    with temporary.open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,allow_nan=False,indent=2)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)


def identity(path):
    path=Path(path);s=path.stat()
    if not stat.S_ISREG(s.st_mode):raise ValueError('A regular sealed input is required: '+str(path))
    return dict(path=str(path),bytes=s.st_size,mtime_ns=str(s.st_mtime_ns),inode=s.st_ino,device=s.st_dev,uid=s.st_uid)


def unchanged(saved):
    if identity(saved['path'])!=saved:raise ValueError('Sealed input changed; never silently rehash or replace: '+saved['path'])


def seal_checkpoint_hashes(path,checkpoints,*,should_stop=lambda:False,hash_function=None):
    if hash_function is None:
        from render_report import checkpoint_sha
        hash_function=checkpoint_sha
    path=Path(path)
    value=read(path) if path.exists() else dict(schema='P_FINAL_ENDPOINT_SHA256_V1',status='PARTIAL',checkpoints={})
    if set(value['checkpoints'])-set(checkpoints):raise ValueError('Final checkpoint selection changed')
    for arm,source in checkpoints.items():
        source=Path(source);before=identity(source)
        if arm in value['checkpoints']:
            row=value['checkpoints'][arm]
            if row['file']!=before:raise ValueError('Final checkpoint changed after its original hash')
            continue
        if should_stop():return None
        result=hash_function(source)
        if identity(source)!=before:raise ValueError('Final checkpoint changed while hashing')
        if not re.fullmatch('[0-9a-f]{64}',result):raise ValueError('Invalid SHA256 result')
        value['checkpoints'][arm]=dict(file=before,sha256=result)
        atomic(path,value)
        print(json.dumps(dict(phase='FINAL_ENDPOINT_HASH_SAVED',arm=arm,bytes=before['bytes'])),flush=True)
    if set(value['checkpoints'])!=set(checkpoints):raise ValueError('Missing final checkpoint')
    value.update(status='COMPLETE',only_final_endpoints=True,no_checkpoint_deserialization=True)
    atomic(path,value)
    return value


def report_dependencies(repo,content,configs,c):
    repo=Path(repo);paths={Path(c[k]) for k in ('plan','verdict','selection')}
    paths.update(map(Path,c['states']))
    for item in configs.values():
        base=Path(item['output'])
        paths.update(base/name for name in ('summary.json','readout/scores.json','clip_calibration.json'))
    for target in re.findall(r'\]\(([^)]+)\)',content):
        target=target.split('#',1)[0]
        if not target or '://' in target:continue
        p=(repo/'docs/p_recipe'/target).resolve()
        if not p.exists():raise ValueError('P report references missing original artifact: '+str(p))
        if p.suffix.lower() in {'.json','.csv'} and p.name not in {'cost_current.json'}:paths.add(p)
    return [identity(p.resolve()) for p in sorted(paths)]


def seal_independent(repo,c,*,should_stop=lambda:False):
    repo=Path(repo);sealpath=repo/SEAL_PATH
    if sealpath.exists():raise ValueError('P sections already sealed; reuse the original delivery')
    from render_report import render,table
    content,configs,summaries,results=render(read(c['plan']),read(c['verdict']),
        [read(p) for p in c['states']],read(c['selection']),c['code_commit'],require_external_A4=False)
    if content.count(A4_MARKER)!=1:raise ValueError('Exactly one explicit A4 insertion point required')
    inputs=report_dependencies(repo,content,configs,c)
    checkpoints={arm:Path(configs[arm]['output'])/f"samples_{configs[arm]['samples']}.pt"
                 for arm in ('T2','T3','T4') if arm in configs}
    hashes=seal_checkpoint_hashes(repo/HASH_PATH,checkpoints,should_stop=should_stop)
    if hashes is None:return None
    content+='\n'+table(['最终检查点','SHA256'],[[arm,row['sha256']] for arm,row in hashes['checkpoints'].items()])+'\n'
    # This is the immutable P body for later assembly, not the unique final REPORT.
    body=repo/BODY_PATH
    if body.exists():
        if body.read_text()!=content:raise ValueError('Partial report body differs; inspect original output')
    else:body.write_text(content)
    for item in inputs:unchanged(item)
    value=dict(schema='P_INDEPENDENT_DELIVERY_20261126_V1',status='P_SECTIONS_SEALED_WAIT_A4',
        authority='User2026-11-26: complete all remaining work independent of D first',
        created_at=time.time(),code_commit=c['code_commit'],body=identity(body),
        checkpoint_hashes=identity(repo/HASH_PATH),source_inputs=inputs,
        original_final_science_producers_reused=True,new_fits=0,new_bootstrap_draws=0,new_plots=0,
        final_REPORT_generated=False,complete_study=False,
        remaining=['D section5 original A4 COMPLETE+scores delivery','Insert A4 and assemble unique REPORT','Final exact-head source CI and PR merge'])
    atomic(sealpath,value)
    return value


def assemble_final(repo,seal,code_commit):
    """Consume sealed P text and original A4; never rerender, plot or hash P."""
    repo=Path(repo)
    if seal.get('status')!='P_SECTIONS_SEALED_WAIT_A4':raise ValueError('Independent P seal required')
    from final_report_22B import render_a4_section,ReportNotReady
    path=repo/'results/p_recipe/fixed_20261115/analysis_20261122/A4_descriptor_upper_controls.json'
    if not path.exists():raise ReportNotReady('Final REPORT waits for: external D section5 A4 delivery')
    section=render_a4_section(read(path))
    unchanged(seal['body']);unchanged(seal['checkpoint_hashes'])
    for item in seal['source_inputs']:unchanged(item)
    hashes=read(seal['checkpoint_hashes']['path'])
    if hashes['status']!='COMPLETE':raise ValueError('Final endpoint hashes not sealed')
    for row in hashes['checkpoints'].values():unchanged(row['file'])
    content=Path(seal['body']['path']).read_text()
    if content.count(A4_MARKER)!=1:raise ValueError('Sealed A4 insertion point changed')
    return content.replace(A4_MARKER,section)+'\n最终拼接代码提交：`'+code_commit+'`。P章节与最终权重SHA沿用原封存产物，没有重新生成。\n'