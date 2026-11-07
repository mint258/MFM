"""Actual Alpha admission shared only by these independent new adapters."""
import os
from pathlib import Path
import sys
from workflows.expansion.coconut_alpha_cached735_v1 import support as S


def admit(plan,proof,plan_path,proof_path,schema,scope):
    from workflows.expansion.alpha_runtime_v1 import profile
    authority=profile.admit(plan,minimum_workers=16);request=proof['request']
    S.need(plan['schema']==schema and plan['scope_key']==request['scope_key']==scope
           and request['producer_plan_reference']==S.pin(plan_path),'EXACT_ROOT_ADAPTER_PLAN_SCOPE')
    argv=request['execution_argv']
    S.need(argv==plan['execution_argv'] and argv[argv.index('--plan')+1]==str(plan_path)
           and argv[argv.index('--startup-proof')+1]==str(proof_path)
           and sys.argv[-4:]==['--plan',str(plan_path),'--startup-proof',str(proof_path)],'EXACT_CURRENT_ADAPTER_CLI')
    S.need(proof['endpoint']==plan['endpoint']=='218.192.171.238:22'
           and proof['uid']==plan['uid']==os.getuid()==1264
           and str(proof['job_id'])==os.environ.get('SLURM_JOB_ID')
           and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'REAL_ALPHA_ADAPTER_JOB_UID_BOOT')
    refs={r['path']:r for r in request['source_references']}
    for file in [*Path(__file__).parent.glob('*.py'),Path(S.__file__)]:
        S.need(refs.get(str(file.absolute()))==S.pin(file),'EXACT_NEW_ADAPTER_AND_BORROWED_SUPPORT_SOURCE')
    for ref in plan['code_references']:S.read(ref,2<<20)
    return authority
