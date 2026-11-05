"""Pure bounded scheduling decisions; unknown outcomes are never retryable."""
N=124857440
NODES=('compute-0-1','compute-0-6','sonmi1')
TERMINAL={'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}
BLOCKED={'FAILED','UNKNOWN','HOLD','SUBMISSION_OUTCOME_UNKNOWN_NO_RETRY','PARTIAL'}


def check_partition(rows):
    if len(rows)!=500:raise ValueError('EXACT500_SHARDS')
    end=0
    for i,row in enumerate(rows):
        expected={'shard_index':i,'first_part':i,'last_part':i,'first_ordinal':i*250000+1,'last_ordinal':min((i+1)*250000,N)}
        if row!=expected or row['first_ordinal']!=end+1:raise ValueError('EXACT_FIXED_ONE_PART_COVERAGE')
        end=row['last_ordinal']
    if end!=N:raise ValueError('NO_HOLE_OR_EXTRA_PHYSICAL_ROW')


def initial_gate(rows):
    return set(rows)=={0,1} and all(v.get('status')=='CLOSED' and v.get('expected_rows')==250000
        and v.get('actual_state')=='COMPLETED' and v.get('actual_exit')=='0:0' for v in rows.values())


def choose_node(free):
    if set(free)!=set(NODES) or any(type(v) is not int or v<0 for v in free.values()):raise ValueError('ACTUAL_THREE_NODE_CPU_COUNTS')
    for node in sorted(NODES,key=lambda n:(-free[n],NODES.index(n))):
        if free[node]<16:continue
        after=dict(free);after[node]-=16
        if max(after.values())>=16:return node  # A contiguous16-CPU short-diagnosis slot remains.
    return None


def next_shard(observed,attempted,initial,max_nonterminal=2):
    if type(max_nonterminal) is not int or not 2<=max_nonterminal<=6:raise ValueError('ROOT_EXPLICIT_NONTERMINAL_CAP_2_THROUGH6')
    if not initial_gate(initial):return 'HOLD_INITIAL_TWO_ACTUAL_C0_CLOSURES',None
    if any(v['status'] in BLOCKED for v in observed.values()):return 'HOLD_FAILED_UNKNOWN_OR_PARTIAL_NO_RETRY',None
    if sum(v['status']!='CLOSED' for v in observed.values())>=max_nonterminal:return 'WAIT_AT_ROOT_NONTERMINAL_C_CAP',None
    for index in range(2,500):
        if index not in observed and index not in attempted:return 'ELIGIBLE',index
    if len(observed)==500 and all(v['status']=='CLOSED' for v in observed.values()):return 'ALL500_PHYSICAL_SHARDS_CLOSED_NO_POOL_RELEASE',None
    return 'HOLD_ATTEMPTED_WITHOUT_UNAMBIGUOUS_PARENT_NO_RETRY',None
