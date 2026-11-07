"""One-shot native closed-block credits and inline unchanged all-future caps."""
from decimal import Decimal
import os
from pathlib import Path
import stat
import time
from ..alpha_runtime_v1 import common as Q
from ..alpha_runtime_v1.quota import validate_snapshot
from .quality_authority import read
from .terminal import parent


CENSUS_METADATA_LIMIT_BYTES=64<<20


def read_census(ref):
    """Only native census JSON, not a wider science/DATA read permission."""
    Q.need(type(ref['bytes'])is int and 0<=ref['bytes']<=CENSUS_METADATA_LIMIT_BYTES,
           'Native census metadata must fit the explicit64MiB bound')
    path=Q.verify(ref);before=Q.frame(path);value=Q.load(path)
    Q.need(before==Q.frame(path),'Census metadata changed during JSON parsing')
    Q.need(isinstance(value,dict)and value.get('endpoint')==Q.ENDPOINT and value.get('uid')==Q.UID
        and ((isinstance(value.get('entries'),list)and 'records'not in value)
             or(isinstance(value.get('records'),list)and 'entries'not in value))
        and value.get('whole_DATA_SHA_reread')is False,
        'Explicit Alpha native census entries/records document only; never raw science DATA')
    return value

def totals(caps,credits):
    Q.need(set(caps)==set(credits)and all(type(v)is int and v>=0 for v in [*caps.values(),*credits.values()]),'Exact complete nonnegative scope caps/credits')
    Q.need(all(credits[k]<=caps[k]for k in caps),'Actual closed scope already exceeds its unchanged total cap')
    remaining={k:caps[k]-credits[k]for k in caps}
    return remaining,{k:sum(v for name,v in remaining.items()if name!=k)for k in caps}


def evidence(binding,closed=True):
    plan=read(binding['plan_reference']);proof=read(binding['startup_proof_reference'])
    runtime=binding['runtime']
    Q.need(proof['request']['producer_plan_reference']==binding['plan_reference']
        and str(proof['job_id'])==str(runtime['job_id'])and proof['uid']==Q.UID and proof['endpoint']==Q.ENDPOINT,
        'Actual same allocation startup/plan identity')
    if closed:parent(runtime,binding['accounting_reference'])
    return Path(plan['output_directory'])


def excluded_201(bindings):
    roots=[evidence(b,False).absolute()for b in bindings]
    Q.need(any(str(b['runtime']['job_id'])=='1885201'for b in bindings),
           'Explicit actual201 output directory must be excluded even if its plan declares shared exact scope')
    return roots


def census(base_reference,closed_allocations,active_exclusions,output,uff_root=None):
    """Stat only: no raw DATA hashing, no active201 file enumeration."""
    Q.need(os.getuid()==Q.UID,'Native census must run as actual Alpha1264')
    base=read(base_reference);old=read_census(base['closed_physical_census_reference'])
    Q.need(base['endpoint']==Q.ENDPOINT and base['uid']==Q.UID,'Actual baseline budget endpoint/UID')
    excluded=excluded_201(active_exclusions)
    blocked=lambda path:any(path==r or r in path.parents for r in excluded)
    seen={};records=[]
    def add(path,scope,old_frame=None):
        path=Path(path).absolute()
        if blocked(path):return
        Q.need(path.is_relative_to('/gfshome/alpha'),'Actual Alpha closed path only')
        a=path.lstat();b=path.lstat()
        stamp=lambda x:(x.st_dev,x.st_ino,x.st_uid,x.st_mode,x.st_nlink,x.st_size,x.st_blocks,x.st_mtime_ns,x.st_ctime_ns)
        Q.need(a.st_uid==Q.UID and(stat.S_ISREG(a.st_mode)or stat.S_ISDIR(a.st_mode))and stamp(a)==stamp(b),
               'Stable native own regular/directory closed census, never symlinks')
        if old_frame:
            Q.need(all(getattr(a,k)==old_frame[k]for k in ('st_uid','st_size','st_mtime_ns','st_ctime_ns','st_nlink')),
                   'Previously closed baseline file changed; do not silently invent replacement credit')
        key=(a.st_dev,a.st_ino)
        if key in seen:
            Q.need(seen[key]==scope,'Shared inode crosses budget scopes; credit owner is ambiguous')
            return
        Q.need(scope in base['scope_total_caps_bytes'],'Known inherited budget scope')
        seen[key]=scope
        records.append(dict(path=str(path),scope=scope,dev_u64=format(a.st_dev,'016x'),ino_u64=format(a.st_ino,'016x'),
            uid=a.st_uid,kind='file'if stat.S_ISREG(a.st_mode)else'directory',logical_bytes=a.st_size if stat.S_ISREG(a.st_mode)else 0,
            allocated_bytes=a.st_blocks*512,mtime_ns=a.st_mtime_ns,ctime_ns=a.st_ctime_ns))
    for item in old['entries']:add(item['path'],item['scope'],item['frame'])
    # Latest actual C0 allocation for a same-stage pilot/full root wins. A
    # full run intentionally extends the pilot; do not credit that prefix twice.
    latest={}
    for binding in closed_allocations:
        root=evidence(binding,True).absolute()
        previous=latest.get(str(root))
        if previous and previous.get('generation_receipt_reference') and binding.get('generation_receipt_reference'):
            a=read(previous['generation_receipt_reference'])['closed_ledger']['closed_at_unix_ns']
            b=read(binding['generation_receipt_reference'])['closed_ledger']['closed_at_unix_ns']
            if a>b:continue
        latest[str(root)]=binding
    closed_allocations=list(latest.values())
    roots=[];summaries=[]
    for binding in closed_allocations:
        root=evidence(binding,True).absolute();Q.need(not any(root==p or root in p.parents or p in root.parents for p in excluded),'Closed root must not overlap active201 in either direction')
        roots.append(str(root))
        if binding.get('generation_receipt_reference'):
            from .ledger_summary import summarize
            Q.need(binding['scope']=='UFF','Generation summary belongs only to actual UFF scope')
            summary=summarize(binding,root);summaries.append(summary)
            records[:]=[r for r in records if not(Path(r['path'])==root or root in Path(r['path']).parents)]
            continue
        for current,dirs,files in os.walk(root,followlinks=False):
            Q.need(not blocked(Path(current)),'Closed root overlaps active201')
            for name in dirs:Q.need(not(Path(current)/name).is_symlink(),'Closed census directory symlink')
            add(current,binding['scope'])
            for name in files:add(Path(current)/name,binding['scope'])
    if uff_root is not None and Path(uff_root).exists():
        uff=Path(uff_root).absolute()
        covered=[Path(r)for r,b in zip(roots,closed_allocations)if b['scope']=='UFF']
        for current,dirs,files in os.walk(uff,followlinks=False):
            current=Path(current)
            Q.need(not any((current/n).is_symlink()for n in dirs),'Legacy UFF directory symlink')
            inside=any(current==r or r in current.parents for r in covered)
            ancestor=current==uff or any(current in r.parents for r in covered)
            Q.need(inside or ancestor or not dirs and not files,
                   'Existing UFF output has no actual terminal allocation binding; cannot assume legacyB=0')
            summarized=[Path(s['path'])for s in summaries]
            if current in summarized:
                dirs[:]=[]
                continue
            dirs[:]=[name for name in dirs if current/name not in summarized]
            add(current,'UFF')
            for name in files:
                Q.need(inside or name=='uff_alpha_routing.lock','Unknown legacy UFF file needs its actual terminal scope binding')
                add(current/name,'UFF')
    credits={name:0 for name in base['scope_total_caps_bytes']}
    for r in [*records,*summaries]:credits[r['scope']]+=r['allocated_bytes']
    remaining,other=totals(base['scope_total_caps_bytes'],credits)
    doc=dict(endpoint=Q.ENDPOINT,uid=Q.UID,baseline_budget_reference=base_reference,
        records=records,generation_summaries=summaries,closed_allocations=closed_allocations,excluded_active_allocations=active_exclusions,
        excluded_active_output_directories=[str(r)for r in excluded],current_closed_output_roots=roots,
        closed_credit_bytes_by_scope=credits,
        maximum_eligible_ns=max([max(r['mtime_ns'],r['ctime_ns'])for r in records]+[s['maximum_eligible_ns']for s in summaries]+[0]),
        whole_DATA_SHA_reread=False,active201_files_enumerated=False,cross_node_device_identity_assumed=False,
        observed_unix_seconds=time.time())
    return Q.write(output,doc)


def inline(base_reference,census_reference):
    base=read(base_reference);c=read_census(census_reference)
    Q.need(c['baseline_budget_reference']==base_reference and c['endpoint']==Q.ENDPOINT and c['uid']==Q.UID,
           'Actual current census for inherited budget')
    remaining,other=totals(base['scope_total_caps_bytes'],c['closed_credit_bytes_by_scope'])
    return dict(endpoint=Q.ENDPOINT,uid=Q.UID,baseline_budget_reference=base_reference,
        closed_census_reference=census_reference,scope_total_caps_bytes=base['scope_total_caps_bytes'],
        closed_credit_bytes_by_scope=c['closed_credit_bytes_by_scope'],remaining_reserved_bytes_by_scope=remaining,
        other_future_reserved_bytes_for_each_scope=other,total_remaining_reserved_bytes=sum(remaining.values()),
        minimum_free_after_all_future_bytes=base['minimum_free_after_all_future_bytes'])


def validate(value,plan):
    base=read(value['baseline_budget_reference']);c=read_census(value['closed_census_reference'])
    Q.need(value['endpoint']==c['endpoint']==base['endpoint']==Q.ENDPOINT
        and value['uid']==c['uid']==base['uid']==Q.UID
        and value['scope_total_caps_bytes']==base['scope_total_caps_bytes']
        and value['minimum_free_after_all_future_bytes']==base['minimum_free_after_all_future_bytes'],
        'Inline budget inherits actual unchanged caps/floor/identity; no per-job approval schema')
    credits={name:0 for name in base['scope_total_caps_bytes']};seen=set()
    for r in c['records']:
        key=(r['dev_u64'],r['ino_u64']);Q.need(key not in seen and r['uid']==Q.UID and type(r['allocated_bytes'])is int and r['allocated_bytes']>=0,'Deduplicated actual own nonnegative native closed facts')
        seen.add(key);credits[r['scope']]+=r['allocated_bytes']
    from .ledger_summary import summarize
    summaries=c.get('generation_summaries',[])
    summary_roots=[]
    for s in summaries:
        binding=s['generation_binding'];root=evidence(binding,True).absolute()
        Q.need(summarize(binding,root)==s,'Current compact summary still equals actual terminal sealed ledger/extras')
        Q.need(not any(root==p or root in p.parents or p in root.parents for p in summary_roots),
               'Compact generation roots must not overlap')
        Q.need(not any(Path(r['path'])==root or root in Path(r['path']).parents for r in c['records']),
               'No per-file double credit inside compact generation summary')
        summary_roots.append(root);credits[s['scope']]+=s['allocated_bytes']
    remaining,other=totals(base['scope_total_caps_bytes'],credits)
    Q.need(credits==value['closed_credit_bytes_by_scope']==c['closed_credit_bytes_by_scope']
        and remaining==value['remaining_reserved_bytes_by_scope']and other==value['other_future_reserved_bytes_for_each_scope']
        and sum(remaining.values())==value['total_remaining_reserved_bytes'],
        'Exact inherited cap minus native closed blocks and all-other remaining arithmetic')
    excluded=excluded_201(c['excluded_active_allocations'])
    Q.need(all(not any(Path(r['path'])==p or p in Path(r['path']).parents for p in excluded)for r in [*c['records'],*summaries]),
           'Active201 never becomes closed credit')
    Q.need(c['baseline_budget_reference']==value['baseline_budget_reference']
        and c['maximum_eligible_ns']==max([max(r['mtime_ns'],r['ctime_ns'])for r in c['records']]+[s['maximum_eligible_ns']for s in summaries]+[0]),
        'Census baseline and exact maximum native credit eligibility')
    for b in c['closed_allocations']:evidence(b,True)
    q=validate_snapshot(Q.load(plan['quota_snapshot']),plan['quota_authority'])
    cutoff=Decimal(str(q['quota_query_started_unix_seconds']))*Decimal(1000000000)
    Q.need(cutoff>c['maximum_eligible_ns'],'Wait for a fresh actual quota capture including all closed credits; never subtract post-query bytes')
    return value