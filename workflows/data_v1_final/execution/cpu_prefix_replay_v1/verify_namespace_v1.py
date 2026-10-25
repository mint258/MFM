"""Prove only namespace/policy-path bindings differ from the closed CPU controls."""
import argparse,ast,json,pathlib
from workflows.data_v1_final.execution.cpu_analysis_v1 import policy as baseline_policy
REPO=baseline_policy.REPO
OLD=REPO/'workflows/data_v1_final/execution/cpu_analysis_v1'
NEW=REPO/'workflows/data_v1_final/execution/cpu_prefix_replay_v1'
FILES=('__init__.py','policy.py','probe_memory.py','runtime.py','runtime_v2.py','launch.py','launch_v2.py',
       'submit_cpu_pilot_v1.py','submit_cpu_pilot_v3.py','prepare_request_v2.py','run_stages_v1.py')
EDITS=(('cpu_analysis_v1','cpu_prefix_replay_v1'),
       ('configs/data_v1/cpu_analysis_small_scopes_v1.json','configs/data_v1/cpu_prefix_replay_scopes_v1.json'),
       ('configs/data_v1/run_decisions_v4.json','configs/data_v1/cpu_prefix_replay_decision_v1.json'))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=pathlib.Path,required=True)
    a=p.parse_args();assert not a.output.exists();rows=[]
    for name in FILES:
        before=baseline_policy.read_small(OLD/name);after=baseline_policy.read_small(NEW/name)
        expected=before
        for old,new in EDITS:expected=expected.replace(old.encode(),new.encode())
        assert expected==after,'UNDECLARED_NAMESPACE_SOURCE_EDIT:'+name
        inverse=after
        for old,new in reversed(EDITS):inverse=inverse.replace(new.encode(),old.encode())
        assert inverse==before
        assert ast.dump(ast.parse(inverse),include_attributes=False)==ast.dump(ast.parse(before),include_attributes=False)
        rows.append({'filename':name,'baseline_reference':baseline_policy.ref(OLD/name),
            'variant_reference':baseline_policy.ref(NEW/name),'inverse_full_file_bytes_equal':True,'normalized_AST_identical':True})
    cfgpath=REPO/'configs/data_v1/cpu_prefix_replay_scopes_v1.json'
    decisionpath=REPO/'configs/data_v1/cpu_prefix_replay_decision_v1.json'
    cfg=baseline_policy.load(cfgpath);decision=baseline_policy.load(decisionpath)
    assert cfg['decision_reference']==baseline_policy.ref(decisionpath)
    assert set(cfg['scopes'])=={'prefix_feature_paired_10000'} and cfg['formal_generation_authorized'] is False
    scope=cfg['scopes']['prefix_feature_paired_10000']
    expected={'prefix_start_ordinal':1,'input_prefix_limit':10000,'legacy_success_cids':8198,
        'legacy_unique_full_keys':8197,'legacy_rejections':1802,'legacy_feature_errors':753,'repair_or_pool_release':False}
    assert scope['parameters']==expected==decision['scope_parameters']
    assert (scope['memory_gib'],scope['wall_seconds'],scope['output_cap_bytes'])==(4,3600,268435456)
    assert decision['new_UFF_QM_calls']==0 and decision['automatic_submission_or_retry'] is False
    result={'schema':'CPU_PREFIX_RESOURCE_NAMESPACE_EQUIVALENCE_V1','status':'PASS','namespace':str(NEW),
        'baseline_namespace':str(OLD),'resource_guards_unchanged':True,
        'changes_restricted_to_namespace_and_policy_paths':True,'declared_edits':EDITS,'files':rows,
        'proof_source_reference':baseline_policy.ref(pathlib.Path(__file__).absolute()),
        'scope_policy_reference':baseline_policy.ref(cfgpath),'decision_reference':baseline_policy.ref(decisionpath),
        'formal_generation_authorized':False,'science_or_tests_executed':False,
        'limits':'Namespace/source binding proof only. Closed old resource-math boundaries are reused; new3scientificfixtures and actual10k require own CPU allocation/monitor closure.'}
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({'status':'PASS','files':len(rows),'proof':baseline_policy.ref(a.output)}))
if __name__=='__main__':main()