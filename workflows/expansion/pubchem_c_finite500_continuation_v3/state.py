"""Pure adoption/cost axes; old scheduling objects loaded from exact sibling source."""
import hashlib,importlib.util
from pathlib import Path
OLD_PATH=Path(__file__).absolute().parent.parent/'pubchem_c_finite500_queue_v2/state.py'
EXPECTED_OLD_SHA='9cc596ff88b7f1aa7afaaeddf8f9d8924b7b6ae23e3727426a86545a11bd31dd'


def need(ok,text):
    if not ok:raise ValueError(text)


def original():
    need(hashlib.sha256(OLD_PATH.read_bytes()).hexdigest()==EXPECTED_OLD_SHA,'EXACT_FROZEN_V2_PURE_STATE_SOURCE')
    spec=importlib.util.spec_from_file_location('_pubchem_c_frozen_pure_state_v2',OLD_PATH);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


OLD=original();N=OLD.N;NODES=OLD.NODES;TERMINAL=OLD.TERMINAL;BLOCKED=OLD.BLOCKED
check_partition=OLD.check_partition;choose_node=OLD.choose_node;next_shard=OLD.next_shard


def adoption(legacy,repaired,failed):
    need(set(legacy)==set(range(51)),'EXACT_IMPORTED_OLD0_THROUGH50_NO_HOLE')
    for i,row in legacy.items():
        need(row['shard_index']==i and row['status']=='CLOSED' and row['actual_state']=='COMPLETED' and row['actual_exit']=='0:0'
            and row['expected_rows']==250000,'REAL_OLD_CLOSED_SHARD_ONLY')
    need(failed['job_id']=='1884853' and failed['actual_state']=='FAILED' and failed['actual_exit']=='1:0'
        and failed['actual_allocated_core_seconds']==336 and failed['shard_index']==51,'ORIGINAL_FAILED51_COST_IS_IMMUTABLE')
    need(repaired['shard_index']==51 and repaired['job_id']=='1884855' and repaired['status']=='CLOSED'
        and repaired['actual_state']=='COMPLETED' and repaired['actual_exit']=='0:0' and repaired['expected_rows']==250000,
        'REAL_REPAIR51_C0_REQUIRED_NEVER_OLD_FAILED_CACHE_AS_SUCCESS')
    population={**legacy,51:repaired};attempts={}
    for row in [*legacy.values(),failed,repaired]:
        job=row['job_id'];need(job not in attempts,'ONE_PHYSICAL_PARENT_ACCOUNTING_ENTRY');attempts[job]=row
    need(len(population)==52 and len(attempts)==53 and sum(r['expected_rows'] for r in population.values())==13000000,'ADOPTION_POPULATION_AND_ALL_COST_AXES_CONSERVE')
    return population,attempts


def decision(population,attempted,free,now,deadline):
    need(type(deadline) in (int,float) and type(now) in (int,float),'REAL_FIXED_DEADLINE_VALUES')
    if now>=deadline:return 'FINITE_ABSOLUTE_DEADLINE_NO_RENEWAL',None,None
    if attempted-set(population):return 'HOLD_ATTEMPTED_WITHOUT_ACTUAL_REGISTRATION_NO_RETRY',None,None
    action,index=next_shard(population,attempted,{i:population[i] for i in (0,1) if i in population},6)
    if action!='ELIGIBLE':return action,index,None
    need(52<=index<=499,'NO_REDISPATCH_IMPORTED_OR_REPAIRED_SHARD')
    node=choose_node(free)
    if node is None:return 'WAIT_ACTUAL16_CPU_PLUS_CONTIGUOUS16_NON_C_RESERVE',index,None
    return 'ELIGIBLE',index,node
