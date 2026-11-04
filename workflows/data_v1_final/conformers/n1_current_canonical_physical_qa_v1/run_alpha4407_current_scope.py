"""Original Alpha4407 physical QA, privately bound to a current identity scope."""
import json,pathlib,types
import scoped_identity as SCOPED
from portable_n1_source_physical_qa_v1 import run as ORIGINAL,identity as OLD_ID
from portable_n1_source_remaining_v1 import runtime as OLD_RUNTIME,contract as C

class View:
    def __init__(self,target,**values):self.target=target;self.values=values
    def __getattr__(self,name):return self.values[name] if name in self.values else getattr(self.target,name)

def admit(plan_path,proof_path,role):
    plan,proof=OLD_RUNTIME.admit(plan_path,proof_path,role);SCOPED.check_plan(plan)
    name=plan['job_name']
    C.need(pathlib.Path(plan_path)==C.MAIN/'control/requests'/(name+'.plan.json')
      and pathlib.Path(proof_path)==C.MAIN/'control/queue_startup'/(name+'.json'),
      'NEW_SCOPE_HAS_EXPLICIT_CANONICAL_PLAN_AND_PROOF_PATHS')
    request=proof['request_reference']
    C.need(request['path']==str(C.MAIN/'control/requests'/(name+'.json'))
      and C.load(request)==proof['request']
      and OLD_RUNTIME.fields(proof['job_metadata'])['JobName']==name,
      'CURRENT_SCOPE_CANONICAL_REQUEST_AND_ACTUAL_JOB_NAME')
    return plan,proof

class Budget(OLD_RUNTIME.Budget):
    def write(self,path,raw,key=None):
        if pathlib.Path(path).suffix=='.json':
            value=json.loads(raw)
            value.update(identity_scope=SCOPED.SCOPE,historical_noncanonical_coverage='UNKNOWN',
              all_global_registered_extra_identity_tables_included=False,
              registry_membership_status='PENDING_ROOT_ACTUAL_PARENT_TERMINAL_ACCEPTANCE')
            raw=C.canonical(value)+b'\n'
        return super().write(path,raw,key)

def main():
    # No shared-module mutation. Every physical/math/QA function remains the
    # original object. Only authority, admission namespace and output envelopes differ.
    identity=View(OLD_ID,authority=SCOPED.authority,census=SCOPED.census)
    runtime=View(OLD_RUNTIME,admit=admit,Budget=Budget)
    namespace=dict(ORIGINAL.main.__globals__,ID=identity,R=runtime,ROOT=SCOPED.OUTPUT)
    private=types.FunctionType(ORIGINAL.main.__code__,namespace,ORIGINAL.main.__name__,ORIGINAL.main.__defaults__,ORIGINAL.main.__closure__)
    return private()

if __name__=='__main__':raise SystemExit(main())
