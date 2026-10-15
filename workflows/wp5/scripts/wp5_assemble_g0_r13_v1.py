"""Assemble R12 technical G0 from actual metadata only; no QM, queue mutation or submission."""
import argparse, ast, copy, hashlib, json, math, os, socket, time
from pathlib import Path
import wp5_submit_formal_v13 as submitter
ROOT = submitter.ROOT
CALL_ID = 'call_e92f4936799142f49105fe45329daf89'
DECISION = ROOT/'submission/recovery_attempt_v12/user_approved_drain_and_one_phase_v1.json'
DECISION_SHA = '878cc6a0bcadb07ecc311b3bb81a866662360f1f6cdf8228e5abcaf0b380bcd7'

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def verified(reference):
    if ref(reference['path'])['sha256'] != reference['sha256']:
        raise ValueError('ACTUAL_METADATA_SHA_DIFFERS: '+reference['path'])
    return read(reference['path'])

def atomic_new(path, obj):
    path = Path(path)
    if path.exists():
        if read(path) != obj:
            raise ValueError('PRESERVE_EXISTING_G0: '+str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name+'.'+str(os.getpid())+'.pending')
    with tmp.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.link(tmp, path); tmp.unlink()

def assemble(a):
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='sonmi':
        raise ValueError('ROOT_COORDINATOR_ZIXIAO_UID1278_ON_SONMI_REQUIRED')
    old = read(ROOT/'gates/g0_ready_for_recovery_v11.json')
    prepared = ROOT/'submission/recovery_attempt_v13/prepared_plan_v13.json'
    plan = read(prepared)
    if plan.get('version')!=13 or plan.get('status')!='PREPARED_NOT_SUBMITTED' or len(plan.get('main',[]))!=72 or len(plan.get('cleanup',[]))!=6:
        raise ValueError('EXACT_ACTUAL_PREPARED12_REQUIRED')
    contract = verified(plan['production_contract'])
    authority = read(a.recovery_authority)
    if authority.get('status')!='USER_APPROVED_ONE_PHASE_RECOVERY':
        raise ValueError('ACTUAL_NEW_R12_ONE_PHASE_AUTHORITY_REQUIRED')
    if authority.get('production_contract')!=plan['production_contract'] or authority.get('original_submission_sha256')!=submitter.digest(ROOT/'submission/submitted_jobs.json'):
        raise ValueError('AUTHORITY_CONTRACT_OR_ORIGINAL_PHASE_DIFFERS')
    if ref(DECISION)['sha256']!=DECISION_SHA:
        raise ValueError('ACTUAL_APPROVAL_DECISION_SHA_DIFFERS')
    decision = read(DECISION)
    question = decision.get('question_item_id')
    if isinstance(question, str):
        question = json.loads(question)
    if question != ['request_user_input_async', CALL_ID, 0] or decision.get('status')!='USER_APPROVED':
        raise ValueError('CURRENT_USER_REPLY_CALL_NOT_BOUND')
    approved_prepared=ROOT/'submission/recovery_attempt_v12/prepared_plan_v12.json'
    approved_plan=read(approved_prepared)
    if decision.get('production_contract')!=approved_plan['production_contract'] or decision.get('prepared_plan')!=ref(approved_prepared):
        raise ValueError('ORIGINAL_ACTUAL_USER_DECISION_PLAN_DIFFERS')
    directive=read(ROOT/'submission/recovery_attempt_v12/user_continue_all_calculations_20261012_v1.json')
    if directive.get('status')!='USER_DIRECTED_CONTINUE' or directive.get('scientific_scope_change_authorized') is not False or directive.get('final200_required') is not True:
        raise ValueError('ACTUAL_CONTINUOUS_DIRECTIVE_NOT_BOUND')
    if {k:contract.get('previous_contract',{}).get(k) for k in ('path','sha256')}!={k:approved_plan['production_contract'].get(k) for k in ('path','sha256')}:
        raise ValueError('METADATA_REPAIR_PARENT_IS_NOT_ACTUAL_APPROVED_CONTRACT5')
    evidence = submitter.validate_recovery_evidence(authority, plan, prepared, a.recovery_authority)
    terminal = submitter.fresh_all_prior_terminal(plan)
    g3 = read(a.g3)
    g4_path = ROOT/'gates/g4_frozen_manifest_v7.json'
    g4 = read(g4_path)
    if g3.get('status')!='PASS' or g3.get('production_contract')!=plan['production_contract']:
        raise ValueError('CURRENT_REMAINING_G3_NOT_PASS_FOR_CONTRACT6')
    if g4.get('status')!='PASS' or g4.get('production_contract')!=plan['production_contract']:
        raise ValueError('ACTUAL_G4_MANIFEST7_DIFFERS')
    if verified(g4['report']).get('status')!='PASS':
        raise ValueError('ACTUAL_G4_REPORT_NOT_PASS')
    quota = g3['quota']
    peak = float(g3['original_full_scope_peak_bytes'])
    permanent = int(g3['confirmed_materialized_permanent_bytes'])
    remaining = float(g3['remaining_writeback_peak_bytes'])
    headroom = float(g3['headroom_bytes'])
    if quota.get('returncode')!=0 or not math.isclose(peak-permanent, remaining, abs_tol=0.01, rel_tol=0):
        raise ValueError('CURRENT_G3_ACTUAL_QUOTA_OR_LIFETIME_ACCOUNTING_NOT_CLOSED')
    if not math.isclose(int(quota['remaining_bytes'])-remaining, headroom, abs_tol=0.01, rel_tol=0) or headroom<float(g3['required_headroom_bytes']):
        raise ValueError('CURRENT_G3_REMAINING_HEADROOM_NOT_PASS')
    if int(g3['future_training_reserve_bytes'])!=400000000000:
        raise ValueError('ORIGINAL_FUTURE400GB_RESERVE_NOT_RETAINED')
    result = copy.deepcopy(old)
    result.update(schema='WP5_G0_RECOVERY_READY_V13', status='READY_FOR_ONE_PHASE_FORMAL_SUBMISSION',
                  created_at_epoch=time.time(), production_contract=plan['production_contract'],
                  prepared_plan=ref(prepared), raw_policy=plan['raw_policy'],
                  queue_reconciliation_report=evidence['queue_reconciliation_report'],
                  queue_bootstrap_report=evidence['queue_bootstrap_report'],
                  recovery_authority=ref(a.recovery_authority), user_approval_decision=ref(DECISION),
                  user_reply_call_id=CALL_ID, submission_authority_pending=False,
                  stop_retained_for_normal_drain=(ROOT/'STOP_NEW_MOLECULES.json').is_file(),
                  stop_retained_pending_user_recovery_instruction=False,
                  actual_root_uid=1278, current_runtime=contract['current_runtime'])
    result['gates']['G3']={**ref(a.g3), 'status':'PASS'}
    result['gates']['G4']={**ref(g4_path), 'status':'PASS'}
    for name in ['G1','G2','G5','G6','REPRO50']:
        gate = result['gates'][name]
        actual = verified(gate)
        allowed = ('PASS','PASS_FULL_FIELD_EXTRACTION') if name=='G5' else ('PASS',)
        if actual.get('status') not in allowed:
            raise ValueError('INHERITED_ACTUAL_SCI_GATE_NOT_PASS: '+name)
    result['current_quota_validation']={
        'source_G3':ref(a.g3), 'materialized_permanent_refs':g3['materialized_permanent_snapshot'],
        'frozen_total_writeback_peak_bytes':peak, 'already_materialized_permanent_bytes':permanent,
        'remaining_writeback_peak_bytes':remaining, 'quota_remaining_bytes':quota['remaining_bytes'],
        'peak_headroom_bytes':headroom, 'required_peak_headroom_bytes':g3['required_headroom_bytes'],
        'future_float32_reserve_bytes':g3['future_training_reserve_bytes'], 'method':g3['method']}
    result['scientific_evidence_transfer']={
        'prior_science_bridge':old['scientific_evidence_transfer'], 'metadata_only_AST_bridge':ref(a.ast_bridge),
        'actual_production_shape_metadata_test':ref(a.pressure_report),
        'new_QM_or_scientific_G6_performed':False, 'final200_required':True}
    ast_proof, pressure = read(a.ast_bridge), read(a.pressure_report)
    if ast_proof.get('status')!='METADATA_ONLY_AST_BRIDGE_PASS' or pressure.get('status')!='PRODUCTION_SHAPE_METADATA_PASS':
        raise ValueError('ACTUAL_METADATA_BRIDGE_OR_PRESSURE_NOT_PASS')
    additions=[ref(prepared),plan['production_contract'],ref(a.recovery_authority),ref(DECISION),
               ref(a.g3),ref(g4_path),g4['report'],g4['spec'],contract['reproduction_package'],
               evidence['queue_reconciliation_report'],evidence['queue_bootstrap_report'],
               ref(a.ast_bridge),ref(a.pressure_report),g3['materialized_permanent_snapshot']]

    cleanup=verified(contract['cleanup_scope_validation'])
    runner_ref=contract['current_runtime']['wp5_runner_v13.py']
    if cleanup.get('status')!='CLEANUP_STATIC_SCOPE_FIXTURE_PASS' or cleanup.get('issues')!=[] or cleanup.get('QM_calls')!=0 or cleanup.get('production_queue_written') is not False or cleanup.get('effective_worker_count')!=16 or {k:cleanup.get('runner13',{}).get(k) for k in ('path','sha256')}!={k:runner_ref.get(k) for k in ('path','sha256')}:
        raise ValueError('ACTUAL_CLEANUP_SCOPE_FIXTURE_NOT_CLOSED')
    additions.append(contract['cleanup_scope_validation'])

    inventory=contract.get('source_chain_inventory')
    if inventory: additions.append(inventory)
    for path in a.extra_binding: additions.append(ref(path))
    by_path={item['path']:item for item in old['bindings']}
    by_path.update({item['path']:item for item in additions})
    result['bindings']=list(by_path.values())
    for item in result['bindings']: verified(item)
    result['final200_required']=True
    result['QM_started_by_assembler']=False
    result['queue_written_by_assembler']=False
    result['Slurm_submitted_by_assembler']=False
    result['prior_terminal_snapshot']=terminal
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true')
    p.add_argument('--recovery-authority',type=Path)
    p.add_argument('--g3',type=Path,help='Root specified actual freshly measured remaining-storage report')
    p.add_argument('--ast-bridge',type=Path,default=ROOT/'reports/wp5_runner_v13_cleanup_scope_ast_bridge_v1.json')
    p.add_argument('--pressure-report',type=Path,default=ROOT/'gates/metadata_queue_production_shape/production_shape_r12_v5_20261012_run6_fair_wait_600/report.json')
    p.add_argument('--extra-binding',type=Path,action='append',default=[])
    p.add_argument('--out',type=Path,default=ROOT/'gates/g0_ready_for_recovery_v13.json')
    a=p.parse_args()
    if a.check:
        ast.parse(Path(__file__).read_text());print('R12_G0_ASSEMBLER_AST_PASS_NO_ACTION');return
    if a.recovery_authority is None or a.g3 is None:
        p.error('--recovery-authority and --g3 actual paths are required')
    try:
        result=assemble(a)
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(json.dumps({'status':'WAITING_FOR_ACTUAL_R12_G0_EVIDENCE','reason':str(error),
                          'G0_READY_written':False,'QM_started':False,'Slurm_submitted':False}))
        raise SystemExit(2)
    atomic_new(a.out,result)
    print(json.dumps({'status':result['status'],'G0':ref(a.out),
                      'headroom_bytes':result['current_quota_validation']['peak_headroom_bytes'],
                      'STOP_retained':result['stop_retained_for_normal_drain']}))
if __name__=='__main__':main()
