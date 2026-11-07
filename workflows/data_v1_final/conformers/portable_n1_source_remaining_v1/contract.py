"""Small immutable V4 contracts. No science, scheduler, or environment initialization."""
from __future__ import annotations
import hashlib,json,os,pathlib,re,stat

KERNEL='2476767636d97b2a334dcf1f8b8e789e137a268acc6404ade61b7162690d211f'
SCIENCE7={
 'common.py':(7240,'ffa4fc9b6ce97be5b62af926c35337168b687f1f80a0fdd3564957dfe169b83b'),
 'science.py':(12865,KERNEL),
 'selection.py':(3377,'41f21f5586c06f3c6fd7cfa9712623adc8091da996c72f6d71170dd4b716e2cb'),
 'statistics_tools.py':(3900,'22422b92fde096a64c019683cf265514b99351b002fa8bc450f6eeaf932808ed'),
 'run_pilot.py':(11440,'f7733b23602d9883159bbedc2ea712fb3054e9e7963950c6fd6c10c1f582868f'),
 'sprime_v6.py':(20644,'d6f1d29a6de673a1faf186e095c4fef7534a81022a09a4840ec65e5d8fa424d3'),
 'prepare.py':(6040,'4b10dc5c0c2c1f3c42250ca1c8541c43661ada301484f92a6ce7bfce512f4a10')}
READERS={'runtime':(22298,'be42f5033ee3fd9fe95da09e8b8efb8ca1dedb711a3766049380b0ed5d7ea300'),
 'contract':(14390,'f8a9ecb744d47808baf4eaed60449ff41d89380a8cfc30d0cc1c480b4b70aaf5')}
MAIN=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
ALPHA=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
MAIN_LEDGER=MAIN/'artifacts/conformers/n1_pprime2_pilot_v2/once_ledger'
REGISTRY=MAIN/'artifacts/conformers/portable_n1_source_remaining_v1/assignment_registry.sqlite'
SCOPE='n1_source_remaining_parallel_v1'
N1_PORT=(13972,'3f044d9582184647f191539980eb653b5ec1393b132484943cc929d8fe02f2ee')
N1_CORE=(19231,'d1bbd7bc1b70e6b97bb16aa3a04ad3fc0f4bf1c60e79ebaad92624334f32a495')
N1_CONTRACT=(23797,'b2f8fc9ae2dff01913ffb87139896c67483dc0434ee0befadce8b3a8f173078e')
SOURCE_N=1
ELIGIBLE='ELIGIBLE_UNCLAIMED_AFTER_ORDINARY_SOURCE_CENSUS'
PACK_COMPRESSED=256<<20;PACK_RAW=256<<20;ADMIN=64<<20;RESERVE=200000000000
TERMINAL={'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}


def need(ok,message):
    if not ok:raise ValueError(message)


def canonical(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def value_sha(v):return sha(canonical(v))
def task_key(mid,cohort=None):return sha(('n1-pprime2-once-generation-v1:'+mid).encode())
def seed(mid,cohort=None):
    return max(int.from_bytes(hashlib.sha256(('sprime-ETKDGv3-v1-n1-pprime2:'+mid).encode()).digest()[:4],'big')&0x7fffffff,1)
def triple(r):return {k:r[k] for k in ('path','bytes','sha256')}


def literal(path):
    p=pathlib.Path(path)
    need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'LITERAL_NONSYMLINK_PATH')
    return p


def frame(p):
    s=literal(p).stat()
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_uid)


def ref(p,limit=None,check=lambda:None):
    p=literal(p);before=frame(p);need(stat.S_ISREG(p.stat().st_mode),'REGULAR_FILE')
    if limit is not None:need(before[2]<=limit,'FINITE_FILE_BOUND')
    h=hashlib.sha256();n=0
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):check();h.update(block);n+=len(block)
    need(frame(p)==before and n==before[2],'SOURCE_FD_FRAME_CHANGED')
    return {'path':str(p),'bytes':n,'sha256':h.hexdigest()}


def verify(r,limit=None,check=lambda:None):
    need(ref(r['path'],limit,check)==triple(r),'ACTUAL_WHOLE_SHA_OR_BYTES_CHANGED:'+r['path'])
    return pathlib.Path(r['path'])


def load(r,limit=2<<20):return json.loads(verify(r,limit).read_bytes())
def load_path(p,limit=2<<20):return load(ref(p,limit),limit)


def exclusive(p,raw):
    p=literal(p);p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return {'path':str(p),'bytes':len(raw),'sha256':sha(raw)}


def save(p,v):return exclusive(p,canonical(v)+b'\n')


def review(plan,locator_map=None):
    original=plan['root_review_reference'];actual=(locator_map or {}).get(original['path'],original)
    need(actual['bytes']==original['bytes'] and actual['sha256']==original['sha256'],'ROOT_REVIEW_COPY_BYTE_IDENTITY')
    r=load(actual)
    need(r['schema']=='ROOT_DISJOINT_REMAINING_REVIEW_V4' and r['status']=='APPROVED' and r['reviewer']=='root'
         and r['plan_body_sha256']==value_sha({k:v for k,v in plan.items() if k!='root_review_reference'}),
         'EXACT_CONCRETE_ROOT_V4_PLAN_REVIEW')
    need(r['no_retry_or_claim_reset'] is True and r['no_scientific_recipe_change'] is True,'UNCHANGED_ONCE_AND_SCIENCE')
    if plan.get('role')=='run':
        need(r['exact_frozen_N1_shard_authorized']is True and r['not_an_override_of_old_full_source_false']is True
            and r['user_two_times_comparable_allocated_cost_stop_new_natural_drain']is True
            and r['aggregate_allocation_ceiling_over500_corehours_reviewed']is True,'INDEPENDENT_EXACT_FINITE_N1_SCIENCE_AND_COST_REVIEW')
    return r


def endpoint(spec):
    need(spec['id'] in ('main','alpha') and spec['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED','ACTUAL_ENDPOINT_DEFAULT_MEMORY_POLICY')
    expected=('202.38.247.57:22',1278,MAIN) if spec['id']=='main' else ('218.192.171.238:22',1264,ALPHA)
    need((spec['address'],spec['uid'],pathlib.Path(spec['root']))==expected,'EXACT_MAIN_OR_ALPHA_ENDPOINT')
    return spec


def validate_shards(shards):
    ids=set()
    for row in shards:
        need(re.fullmatch('[a-zA-Z0-9_-]+',row['shard_id']) and row['shard_id'] not in ids,'UNIQUE_LITERAL_SHARD_ID')
        ids.add(row['shard_id']);endpoint(row['endpoint'])
        need(row['cpus'] in ((16,32,64,96) if row['endpoint']['id']=='main' else (16,64)),'EXACT_ROOT_FREE_CPU_WORKER_MENU')
        need(row['wall_seconds']==86400 and row['stop_dispatch_before_wall_seconds']==900,'ONE_DAY_NATURAL_DRAIN')
        need(type(row['output_cap_bytes'])is int and row['output_cap_bytes']>=8<<30,'FINITE_PARENT_CAP')
        # Actual original N1 per-task3*bound is frozen before assignment; reserve
        # it at dispatch. A256MiB decode cap is not a universal per-task write.
        need(pathlib.Path(row['endpoint']['root'])/'outputs' in literal(row['output_directory']).parents
             or (row['endpoint']['id']=='main' and MAIN/'artifacts/conformers' in literal(row['output_directory']).parents),
             'OWN_ENDPOINT_OUTPUT_ROOT')
    need(ids,'NONEMPTY_ROOT_SHARDS')


def weighted_assignment(metas,shards):
    """Deterministic geometry-size scheduling heuristic, explicitly not a runtime forecast."""
    validate_shards(shards);load={s['shard_id']:0 for s in shards};owners={}
    def score(m):return max(1,int(m['heavy_atoms']))**2*min(10*int(m['expected_conformers']),300)
    for m in sorted(metas,key=lambda x:(-score(x),x['molecule_id'])):
        key=m['task_key'];need(key==task_key(m['molecule_id'],m['cohort']) and key not in owners,'ORIGINAL_UNIQUE_TASK_KEY')
        owner=min(shards,key=lambda s:(load[s['shard_id']]/s['cpus'],s['shard_id']))
        owners[key]=owner['shard_id'];load[owner['shard_id']]+=score(m)
    return owners,load


# Own namespace wiring to ORIGINAL pure objects, never modify old module/global.
def original():
    import importlib
    value=importlib.import_module('workflows.data_v1_final.conformers.n1_pprime2_source_full_v1.contract')
    need((ref(value.__file__)['bytes'],ref(value.__file__)['sha256'])==N1_CONTRACT,'ORIGINAL_N1_PURE_CONTRACT_BYTES')
    return value

def sha_value(value):return value_sha(value)
O=original()
validate_task=O.validate_task;proposed_seed=O.proposed_seed
select_real_second=O.select_real_second;expanded_orders=O.expanded_orders


def reserve_task(task):
    # Verbatim formula from original pilot_v4.io.reserve_task; no runtime forecast.
    n=len(task['source_atomic_numbers']);baseline=len(canonical(task['existing_conformers'][0]));pointer=len(canonical(task['records'][0]))
    bound=(4<<20)+4096*n+4*baseline+16*pointer
    need(bound<=PACK_RAW,'TASK_PACKET_RESERVATION_EXCEEDS_REVIEWED_CAP_NO_DISPATCH')
    return 3*bound
