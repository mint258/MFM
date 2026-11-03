"""Full-population exact novelty with bounded per-worker cache and disk dedup.

No allocation or scheduler is created here. Invoke inside the approved Slurm
allocation, using a pinned resource/quota plan and existing reference manifest.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import stat
import time
from ..common import load,reference,require,dump_new,wp5_key
from ..portable_sources_v1.transport import verify,bind_plan,provenance
from ..nearest_exact import QUERY_FIELDS
from .engine import RECIPE,WIDTH,ALGORITHM,current_rss,file_frame
from .cache import QueryCache,canonical
from .workers import exact_batches


class Guard:
    def __init__(self,plan,root):
        self.plan=plan;self.root=root;self.last=0
        self.scope=Path(plan['output_scope_root']) if plan.get('runtime_profile_reference') else root
        if plan['quota_authority'].get('kind')=='gluster_directory_quota_deem_statfs':
            from ..alpha_runtime_v1.quota import budget_check
        elif plan['quota_authority'].get('kind')=='lustre':
            from ..completion_runtime_v1.lustre_quota import budget_check
        else:
            from ..completion_runtime_v1.quota import budget_check
        self.checker=budget_check

    def usage(self):
        # This runtime owns only a fixed small number of flat files, not one
        # output per query. Never scan a million-file generation output tree.
        if self.plan.get('runtime_profile_reference'):
            from ..alpha_runtime_v1.common import allocated_bytes
            return allocated_bytes(self.scope)
        total=0;seen=set()
        paths=self.scope.rglob('*') if self.scope!=self.root else self.root.iterdir()
        for path in paths:
            try:value=path.lstat()
            except FileNotFoundError:continue
            if self.scope!=self.root and stat.S_ISDIR(value.st_mode):continue
            require(stat.S_ISREG(value.st_mode) and value.st_uid==os.getuid(),'Dedicated flat own regular output tree required')
            if (value.st_dev,value.st_ino) in seen:continue
            seen.add((value.st_dev,value.st_ino))
            total+=max(value.st_size,value.st_blocks*512)
        return total

    def poll(self,force=False,reserve=0):
        now=time.monotonic()
        own=self.usage()
        require(own+reserve<=self.plan['output_cap_bytes'],'Exact output cap including bounded in-flight batch exceeded')
        if force or now-self.last>=30:
            require(current_rss()<=self.plan['parent_rss_cap_bytes'],'Exact parent RSS exceeds declared allowance')
            # Mutable SQLite and growing outputs receive no old-quota credit.
            self.checker(self.plan,own,self.scope,prequery_credit_provider=lambda cutoff:0)
            self.last=now


def allocation_guard(plan):
    """No explicit Slurm memory request is inferred from a software allowance."""
    workers=plan['workers'];cap=plan['worker_rss_cap_bytes'];parent=plan['parent_rss_cap_bytes']
    require(type(workers)is int and 1<=workers<=192 and type(cap)is int and cap>0 and type(parent)is int and parent>0,
        'Positive explicit software worker/parent allowances required')
    if plan.get('runtime_profile_reference'):
        from ..alpha_runtime_v1.profile import admit
        admit(plan,minimum_workers=16)
        require(workers*cap+parent<=plan['software_rss_budget_bytes'],'All exact caches/parent exceed Alpha software tree budget')
    else:
        require(socket.gethostname().split('.')[0].startswith('compute-0-') and os.environ.get('SLURM_JOB_ID')
            and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=workers,'Actual compute-node CPU allocation required')
    allocated=int(os.environ.get('SLURM_MEM_PER_NODE','0'))*(1<<20)
    if not allocated:allocated=int(os.environ.get('SLURM_MEM_PER_CPU','0'))*(1<<20)*int(os.environ['SLURM_CPUS_PER_TASK'])
    needed=workers*cap+parent
    if allocated>0:require(needed<=allocated,'Decoded caches exceed actual finite Slurm memory allocation')
    available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    require(available>=needed+plan.get('minimum_node_available_bytes',4<<30),'Actual MemAvailable must cover all software allowances and reserve')
    return {'actual_finite_slurm_memory_bytes':allocated or None,'actual_node_available_bytes':available,
        'declared_software_memory_bytes':needed,'explicit_Slurm_memory_request_inferred':False}


def _query(row):
    require(set(row)==QUERY_FIELDS,'Exact query fields differ or contain downstream features')
    wp5_key(row['full_key'])
    require(isinstance(row['generic_murcko'],str) and isinstance(row['generic_ring_systems'],list)
        and all(isinstance(v,str) for v in row['generic_ring_systems']),'Query scaffold/ring types differ')
    raw=bytes.fromhex(row['ecfp4_2048_hex']);require(len(raw)==WIDTH,'Query width differs')
    return raw


def rows(path,limit,expected_frame):
    require(file_frame(path)==expected_frame,'Query source file identity changed')
    with path.open('rb') as stream:
        s=os.fstat(stream.fileno())
        require([s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_uid]==expected_frame,'Same query source FD required')
        for ordinal in range(limit):
            line=stream.readline((1<<20)+1)
            require(line and len(line)<=1<<20,'Missing or unbounded query row')
            row=json.loads(line);yield ordinal,row,_query(row),len(line)
        s=os.fstat(stream.fileno())
        require([s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_uid]==expected_frame,'Query changed during source replay')
    require(file_frame(path)==expected_frame,'Query path changed during source replay')


def validate_query(path):
    q=load(path);cost=q.get('schema')=='expansion_exact_query_cost_pilot_v1'
    typed=q.get('schema')=='EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1'
    require(q.get('schema') in ('expansion_decontaminated_query_projection_v1','expansion_exact_query_cost_pilot_v1',
        'EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1'),
        'Full pool or explicit non-releasing cost projection required')
    require(q.get('fingerprint_recipe')==RECIPE and q.get('targets_present') is False
        and q.get('downstream_features_present') is False,'Exact query recipe/target contract differs')
    source=verify(q['projection'])
    if cost:
        require(q.get('candidate_release_authorized') is False and q.get('source_kind')=='v1_common_structure_projection',
            'Cost profile must not authorize pool release')
        verify(q['source_projection_manifest'])
    else:
        filtered=load(verify(q['filtered_pool_receipt']))
        if typed:
            from .contracts import typed_filtered
            typed_filtered(filtered)
            require(q.get('status')=='COMPLETE' and q['projection']['rows']==filtered['counts']['eligible_molecules'],
                'Complete typed query projection census required')
        else:
            require(filtered.get('schema')=='expansion_filtered_pool_v1' and filtered.get('status')=='COMPLETE'
                and filtered.get('all_sources_all_splits_verified') is True,'Complete all-split filtering required')
    return q,cost,source


def run(plan_path):
    plan=load(plan_path)
    bind_plan(plan)
    require(plan.get('schema')=='PUBCHEM_EXACT_CACHED_NN_PLAN_V1','Wrong exact NN plan schema')
    workers=plan['workers'];cap=plan['worker_rss_cap_bytes'];startup_memory=allocation_guard(plan)
    ref_path=verify(plan['reference_manifest']);query_path=verify(plan['query_manifest'])
    m=load(ref_path)
    require(m.get('schema')=='expansion_exact_ecfp4_reference_v1' and m.get('status')=='COMPLETE'
        and m.get('fingerprint_recipe')==RECIPE and m.get('targets_present') is False,'Invalid complete exact reference')
    fp_path=verify(m['fingerprints']);keys_path=verify(m['keys']);counts_path=verify(m['counts'])
    n=m['molecules'];require(type(n)is int and n>0 and fp_path.stat().st_size==n*WIDTH
        and keys_path.stat().st_size==n*28,'Complete reference cardinality differs')
    q,cost,source=validate_query(query_path)
    source_frame=file_frame(source)
    limit=plan.get('max_queries',q['projection']['rows'])
    require(type(limit)is int and 0<limit<=q['projection']['rows'],'Explicit positive query cardinality required')
    batch=plan['query_batch'];require(type(batch)is int and 1<=batch<=4096,'Bounded worker query batch required')
    commit_queries=plan.get('cache_commit_queries',4096)
    require(type(commit_queries)is int and 1<=commit_queries<=4096,'Explicit bounded exact-cache checkpoint size required')
    root=Path(plan['output_directory']);require(root.is_absolute() and not root.is_symlink(),'Own absolute output directory required')
    root.mkdir(parents=True,exist_ok=True)
    lock=os.open(root/'parent.lock',os.O_CREAT|os.O_RDWR,0o600)
    import fcntl
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    guard=Guard(plan,root);guard.poll(True,32<<20)
    ref_sha=plan['reference_manifest']['sha256']
    cache=QueryCache(root/'queries.sqlite',ref_sha,n)
    # SQLite itself cannot grow beyond the declared entire output allowance.
    cache.db.execute('PRAGMA max_page_count='+str(plan['output_cap_bytes']//4096))
    source_key=hashlib.sha256(canonical({'query_manifest':plan['query_manifest'],'limit':limit})).hexdigest()
    member=cache.source(source_key);old=cache.source_ingestion(source_key)
    began=time.monotonic();computed=0;evaluated=pruned=0;pids=set()
    try:
        if old is None:
            window=0
            for ordinal,row,raw,line_bytes in rows(source,limit,source_frame):
                cache.add(raw,ordinal,member)
                window+=line_bytes+4096
                if window>=8<<20:
                    cache.commit();guard.poll(True,32<<20);window=0
            cache.close_ingestion(source_key,{'rows':limit,'query_manifest':plan['query_manifest']})
        else:require(old=={'rows':limit,'query_manifest':plan['query_manifest']},'Closed source ingestion differs')
        cache.commit();guard.poll(True,64<<20)
        attempt=0
        while any((root/(source_key+'.'+str(attempt)+suffix)).exists() for suffix in
                ('.novelty.jsonl','.audit.jsonl','.workers.jsonl','.receipt.json')):attempt+=1
        metrics=root/(source_key+'.'+str(attempt)+'.workers.jsonl')
        with metrics.open('x',encoding='utf-8') as log:
            def ready(value):
                pids.add(value['worker_pid']);log.write(json.dumps({'kind':'reference_loaded',**value})+'\n');log.flush()
            pending=cache.pending_count(member)
            uncommitted=0;last_commit=time.monotonic()
            if pending:
                for result in exact_batches(fp_path,n,cache.pending_batches(batch,member),workers=workers,
                        worker_rss_cap_bytes=cap,ready_callback=ready):
                    for identity,raw,value in result.pop('results'):
                        cache.store(identity,raw,value);computed+=1
                        uncommitted+=1
                        evaluated+=value['evaluated_references'];pruned+=value['strictly_bound_pruned_references']
                    if uncommitted>=commit_queries or time.monotonic()-last_commit>=30:
                        cache.commit();uncommitted=0;last_commit=time.monotonic()
                    pids.add(result['worker_pid'])
                    log.write(json.dumps({'kind':'exact_batch',**result})+'\n');log.flush()
                    guard.poll(reserve=64<<20)
            cache.commit()
            log.flush();os.fsync(log.fileno())
        require(cache.pending_count(member)==0,'Source exact queries incomplete')
        # New attempt suffix preserves every interrupted export. Exact cache
        # results are reused; this replay never repeats a completed NN query.
        projection=root/(source_key+'.'+str(attempt)+'.novelty.jsonl')
        audit=root/(source_key+'.'+str(attempt)+'.audit.jsonl')
        counts=sqlite3.connect(counts_path.as_uri()+'?mode=ro',uri=True)
        try:
            with projection.open('x',encoding='utf-8') as out,audit.open('x',encoding='utf-8') as trace,keys_path.open('rb') as keys:
                window=0
                for ordinal,row,raw,line_bytes in rows(source,limit,source_frame):
                    value=cache.lookup(raw);index=value['reference_ordinal'];keys.seek(index*28)
                    key=keys.read(28).decode('ascii').rstrip('\n');wp5_key(key)
                    sc=counts.execute('SELECT n FROM scaffolds WHERE key=?',(row['generic_murcko'],)).fetchone()
                    rings=[counts.execute('SELECT n FROM rings WHERE key=?',(r,)).fetchone() for r in set(row['generic_ring_systems'])]
                    result={k:v for k,v in row.items() if k!='ecfp4_2048_hex'}
                    result.update(nearest_v1_tanimoto=value['score'],v1_scaffold_count=sc[0] if sc else 0,
                        v1_ring_system_count=min((r[0] if r else 0 for r in rings),default=n),v1_reference_sha256=ref_sha)
                    out.write(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
                    trace.write(json.dumps({'cid':row['cid'],'query_key':row['full_key'],'nearest_v1_key':key,
                        'reference_ordinal':index,'tanimoto':value['score']},separators=(',',':'))+'\n')
                    window+=line_bytes+4096
                    if window>=8<<20:
                        out.flush();trace.flush();guard.poll(True,32<<20);window=0
                for stream in (out,trace):stream.flush();os.fsync(stream.fileno())
        finally:counts.close()
        verify(m['fingerprints'])
        verify(m['keys']);verify(m['counts']);verify(plan['reference_manifest']);verify(plan['query_manifest'])
        guard.poll(True)
        receipt={'schema':'expansion_exact_novelty_v1','status':'COMPLETE' if not cost and limit==q['projection']['rows'] else 'BOUNDED_COST_PILOT',
            'nearest_similarity_exact':True,'downstream_features_used':False,'fingerprint_recipe':RECIPE,'algorithm':ALGORITHM,
            'reference':plan['reference_manifest'],'query_manifest':plan['query_manifest'],'filtered_pool_receipt':q.get('filtered_pool_receipt'),
            'queries':limit,'reference_molecules':n,'distinct_query_fingerprints':cache.source_count(member),
            'new_distinct_queries_computed_this_attempt':computed,'evaluated_references_this_attempt':evaluated,
            'strictly_bound_pruned_references_this_attempt':pruned,'wall_seconds':time.monotonic()-began,
            'worker_count_requested':workers,'worker_pids_observed':sorted(pids),'query_batch':batch,
            'worker_metrics':reference(metrics),'projection':{**reference(projection),'rows':limit},'nearest_identity_audit':reference(audit),
            'resource_plan':reference(plan_path),'timing_is_this_attempt_only':True}
        receipt['startup_memory_observation']=startup_memory
        receipt['endpoint_execution']=provenance(plan)
        dump_new(root/(source_key+'.'+str(attempt)+'.receipt.json'),receipt)
        return receipt
    finally:
        cache.close();os.close(lock)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True,type=Path)
    run(parser.parse_args().plan)


if __name__=='__main__':main()
