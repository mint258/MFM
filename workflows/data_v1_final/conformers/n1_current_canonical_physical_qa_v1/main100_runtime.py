"""Private Main18 physical-QA resource binding; no original module is mutated."""
import collections.abc,fcntl,json,os,pathlib,threading,time,types
import sys
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
SCOPED_SOURCE=ROOT/'repository/workflows/data_v1_final/conformers/n1_current_canonical_physical_qa_v1'
if str(SCOPED_SOURCE) not in sys.path:sys.path.insert(0,str(SCOPED_SOURCE))
import run_alpha4407_current_scope as CURRENT
from portable_n1_source_remaining_v1 import runtime as ORIGINAL,contract as C,storage as S
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import quota_provider as DAY
FLOOR=100000000000
CAP=512<<20
RESOURCE_BINDING='CURRENT_CANONICAL_N1_PHYSICAL_QA_MAIN18_DAY_CLIENT_LIVE_V2_100GB_V1'
FUTURE=ROOT/'control/root_current_all_future_ledger_v1.json'
FUTURE_LOCK=ROOT/'control/root_current_all_future_ledger_v1.lock'
FLOOR_POINTER=ROOT/'control/current_account_quota_floor_policy.json'
PROVIDER=ROOT/'control/ordinary_postprocess_20261105_v5/provider_review.json'
IDENTITY=ROOT/'control/ordinary_postprocess_20261105_v5/provider/identity.json'
HERE=pathlib.Path(__file__).absolute().parent

# An explicit private globals view, never setattr on the original contract.
CONTRACT100=CURRENT.View(C,RESERVE=FLOOR)
def private(function,**values):
    namespace=dict(function.__globals__,**values)
    value=types.FunctionType(function.__code__,namespace,function.__name__,function.__defaults__,function.__closure__)
    value.__kwdefaults__=function.__kwdefaults__
    C.need(value.__code__ is function.__code__,'EXACT_ORIGINAL_RESOURCE_CODE_OBJECT')
    return value

ORIGINAL_ADMIT100=private(ORIGINAL.admit,C=CONTRACT100)
CURRENT_ADMIT100=private(CURRENT.admit,OLD_RUNTIME=CURRENT.View(ORIGINAL,admit=ORIGINAL_ADMIT100))


def source_references():
    files=[HERE/'main100_runtime.py',HERE/'metadata100.py',HERE/'README.md',
        *[SCOPED_SOURCE/n for n in ('run_alpha4407_current_scope.py','scoped_identity.py')],
        pathlib.Path(DAY.__file__)]
    return [C.ref(p,2<<20) for p in files]


def resource_plan(plan):
    C.need(plan['role']=='physical_qa' and plan['endpoint']['id']=='main' and plan['endpoint']['uid']==1278
        and plan['cpus']==16 and plan['node']=='compute-0-18' and plan['wall_seconds']==14400
        and plan['stop_dispatch_before_wall_seconds']==900 and plan['output_cap_bytes']==CAP,
        'EXACT_MAIN18_16CPU_4H512MIB_PHYSICAL_QA_ONLY')
    C.need(plan['resource_binding']==RESOURCE_BINDING and plan['account_quota_floor_bytes']==FLOOR
        and plan['current_all_future_ledger_path']==str(FUTURE)
        and plan['quota_provider_review_reference']['path']==str(PROVIDER)
        and plan['quota_provider_identity_reference']['path']==str(IDENTITY),
        'EXACT_EXISTING_V5_PROVIDER_AND_CURRENT_V2_LEDGER_NOT_GENERAL_CLIENT')
    policy=C.load_path(FLOOR_POINTER)
    C.need(policy['schema']=='CURRENT_USER_ACCOUNT_QUOTA_FLOOR_POLICY_POINTER_V1'
        and policy['account_quota_floor_bytes']==FLOOR
        and policy['policy_reference']==plan['quota_floor_policy_reference'],
        'EXISTING_USER100GB_POLICY_NOT_A_NEW_SCIENCE_EXCEPTION')
    C.verify(plan['quota_floor_policy_reference'],2<<20)
    C.need(all(r in plan['source_references'] for r in source_references()),'EXPLICIT_PRIVATE_RESOURCE_AND_DAY_CLIENT_SOURCE_PINS')
    return plan


def live_future(plan,proof=None):
    # Mutable ledger is read as current metadata under its original lock, never
    # given an immutable DATA hash or used to alter the real free-byte reading.
    with C.literal(FUTURE_LOCK).open('rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_SH)
        path=C.literal(FUTURE);before=C.frame(path);value=json.loads(path.read_bytes())
        C.need(C.frame(path)==before and path.stat().st_uid==1278,'STABLE_OWN_CURRENT_FUTURE_METADATA_FRAME')
        C.need(value['schema']=='ROOT_CURRENT_ALL_FUTURE_METADATA_POINTER_V2'
            and value['totals_derived_live_from_entries'] is True and not value['unknown_future_entries'],
            'ALL_CURRENT_FUTURES_KNOWN_V2')
        rows=value['entries'];numbers=[v['future_reserved_bytes'] for v in rows.values()]
        C.need(all(type(n)is int and n>=0 for n in numbers)
            and sum(numbers)==value['known_future_reserved_bytes']==value['total_future_reserved_bytes'],
            'EXACT_CURRENT_ALL_FUTURE_ONCE_SUM')
        own=rows[plan['future_ledger_entry_key']]
        C.need(own['output_root']==plan['output_directory'] and own['forecast_bytes']==CAP
            and type(own['future_reserved_bytes'])is int and 0<=own['future_reserved_bytes']<=CAP,
            'THIS_QA512MIB_ALREADY_REGISTERED_ONCE')
        if proof is not None:
            C.need(str(own['job_id'])==str(proof['job_id']),'THIS_ACTUAL_PARENT_FUTURE_ENTRY')
        return value['total_future_reserved_bytes']


def admit(plan_path,proof_path,role):
    plan,proof=CURRENT_ADMIT100(plan_path,proof_path,role)
    resource_plan(plan)
    pins=proof['request']['source_references']
    C.need(all(r in pins for r in source_references()),'ACTUAL_REQUEST_INCLUDES_PRIVATE_RESOURCE_SOURCE')
    C.need(proof['account_free_bytes']-live_future(plan,proof)>=FLOOR,'ACTUAL_STARTUP_ALL_LIVE_FUTURE_PLUS100GB')
    return plan,proof


class LiveFuturePlan(collections.abc.Mapping):
    """Private Budget view: one documented live resource field; no plan rewrite."""
    def __init__(self,plan,proof):self.original,self.proof=plan,proof
    def __getitem__(self,key):
        return live_future(self.original,self.proof) if key=='total_future_reserved_bytes' else self.original[key]
    def __iter__(self):return iter(self.original)
    def __len__(self):return len(self.original)


class Budget(CURRENT.Budget):
    def __init__(self,plan,proof,out):
        # Original Budget constructor state/storage, with its Main Client import
        # explicitly bound to the existing frozen day provider implementation.
        resource_plan(plan)
        self.plan,self.proof,self.out=LiveFuturePlan(plan,proof),proof,pathlib.Path(out)
        self.stop=None;self.failure=None;self.lock=threading.RLock()
        self.written=0;self.reserved={};self.next=0;self.samples=[];self.started=time.monotonic()
        self.initial_elapsed=proof['allocation_elapsed_seconds'];self.client=None
        self.cost_group=None;self.cost_last=-1;self.cost_evidence=None
        S.initialize(self.out,plan['output_cap_bytes'])
        C.need(C.ref(DAY.__file__,2<<20) in proof['request']['source_references'],'ACTUAL_FROZEN_DAY_QUOTA_CLIENT_SOURCE')
        self.client=DAY.Client(plan['quota_provider_review_reference'],proof['request'])
    observe=private(ORIGINAL.Budget.observe,C=CONTRACT100)
    def report(self):
        value=super().report()
        value.update(account_quota_floor_bytes=FLOOR,current_all_future_ledger_path=str(FUTURE),
            quota_client='cpu_analysis_day_v1.quota_provider.Client',free_bytes_not_modified=True,
            legacy_ACCOUNT200GB_stop_label_if_present_is_original_diagnostic_only=True)
        return value


def main():
    # Every physical function is the original object/code. Current identity
    # authority and output-envelope changes are exactly the existing four-file
    # candidate; only its two runtime callables are replaced in a private view.
    return private(CURRENT.main,admit=admit,Budget=Budget)()


if __name__=='__main__':raise SystemExit(main())