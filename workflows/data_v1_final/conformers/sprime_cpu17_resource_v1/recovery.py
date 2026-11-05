"""Actual95 late close + one explicit96 replacement; all old costs retained."""
from pathlib import Path
from workflows.data_v1_final.execution.sprime_wave2_controller_v3 import controller as V
from workflows.data_v1_final.execution.sprime_wave2_controller_v2 import repair as RP
from . import recovery as K
from . import contract as F

FIELDS=('stage_spec_reference','request_reference','submission_reference','activation_reference','registry_reference')


def exact(reference):
    F.need(V.pin(reference['path'])==reference,'ACTUAL_IMMUTABLE_RECOVERY_SMALL_PIN');return V.load(reference['path'])


def registration(record,bid=None,stage=None):
    extra=set(record)-set(FIELDS)
    F.need(set(FIELDS)<=set(record) and (not extra or extra=={'batch_id','stage'}
      and bid is not None and stage is not None and record['batch_id']==bid and record['stage']==stage),
      'EXACT_FIVE_REFS_OR_MATCHED_COMPLETE_HISTORICAL_ADOPTION_KEYS')
    for key in FIELDS:exact(record[key])
    return dict(record)


def parent(reference,jid,c0=True):
    row=F.accounting(reference,[jid])[str(jid)]
    F.need(int(row['alloc_cpus'])==16,'ACTUAL16CPU_RECOVERY_ACCOUNTING')
    if c0:F.need(row['state']=='COMPLETED' and row['exit_code']=='0:0','ACTUAL_C0_REQUIRED_BEFORE_CONTROLLER_RECOVERY')
    return row


def complete(report,bid,jid,plan,prepared):
    F.need(report['schema']=='SPRIME_FORMAL_CPU_CLOSED_BATCH_V3' and report['status']=='ACTUAL_TERMINAL_BATCH_CLASSIFIED'
      and report['batch_id']==bid and report['actual_parent_job_id']==str(jid) and report['plan']==plan
      and report['prepared']==prepared and report['valid_packets']==report['consumed_outcomes']==500
      and report['execution_unresolved']==report['unstarted_count']==0
      and report['errors']==report['consumed_elsewhere']==[],'COMPLETE_ACTUAL500_NO_UNKNOWN_NO_UNSTARTED_CLOSURE_REQUIRED')


class Recovery:
    def __init__(self,reference,review,prior):
        self.reference=reference;self.value=value=exact(reference)
        F.need(value['schema']=='ROOT_MAIN17_SPRIME96_ACTUAL_CONTINUATION_ADOPTION_V1'
          and value['status']=='APPROVED_ACTUAL95_AND96_REPLACEMENT_ONLY' and value['reviewer']=='root'
          and value['uid']==1278 and value['endpoint']=='202.38.247.57:22'
          and value['original_HOLD_reference']==review['resume_from_state_reference']
          and value['all_manual_known_registrations_included'] is True
          and value['all_original94_closed_remain_unchanged'] is True
          and value['old_failed96_and_zero_close_history_and_cost_retained'] is True
          and value['automatic_retry'] is False,'ROOT_EXPLICIT_ACTUAL_ONLY_REPAIR_ADOPTION')
        self.hold=hold=exact(value['original_HOLD_reference'])
        F.need(hold['status']=='HOLD_ROOT_REVIEW_REQUIRED_NO_NEW_DISPATCH'
          and hold['review_reference']==review['supersedes_review_reference']
          and hold['manifest_reference']==V.MANIFEST and hold['plan_reference']==V.PLAN,
          'EXACT_PRIOR_HOLD_REVIEW_AND_ORIGINAL179_LINEAGE')
        self.entries={}
        for bid,stages in hold['stages'].items():
            for stage,row in stages.items():
                F.need(not row.get('ambiguous'),'OLD_AMBIGUOUS_REGISTRATION_MUST_NOT_BE_DISCARDED')
                if row.get('actual_registered_references'):
                    self.entries[(bid,stage)]=registration(row['actual_registered_references'],bid,stage)
        for i in range(1,95):
            row=hold['stages']['batch-%05d'%i]['close']
            F.need(V.C.c0(row),'FIRST94_MUST_ALREADY_HAVE_ACTUAL_C0_CLOSE')
        old=hold['stages'][K.BID]
        F.need(old['run']['job_id']==K.FAILED_RUN and old['run']['state']=='FAILED'
          and old['close']['job_id']==K.OLD_CLOSE and V.C.c0(old['close']),'OLD96_FAILURE_AND_ZERO_CLOSE_RETAINED')
        old_report=exact(old['close']['report_reference']);old_header=exact(old_report['prepared'])
        K.zero_consumption(old_report,old_header,V.PLAN)
        self.failed_accounting_reference=old_report['accounting']
        self.failed=parent(old_report['accounting'],K.FAILED_RUN,c0=False)
        F.need(self.failed['state']=='FAILED' and self.failed['exit_code']=='1:0','OLD_FAILED96_COST_IS_NOT_C0')
        parent(value['original96_close_accounting_reference'],K.OLD_CLOSE)
        bundle_ref=value['continuation_bundle_reference'];self.bundle=bundle=exact(bundle_ref)
        F.need(bundle['schema']=='MAIN17_ORIGINAL_REMAINING_METADATA_BUNDLE_V1'
          and bundle['origin_plan_reference']==V.PLAN and bundle['origin_prepared_reference']==old_report['prepared']
          and bundle['old_tasks_reference_unchanged']==old_header['tasks'],'ACTUAL_EXACT_ORIGINAL500_CONTINUATION_BUNDLE')
        decision=exact(bundle['decision_reference']);wave=exact(bundle['replacement_wave_review_reference'])
        F.need(decision['original_HOLD_reference']==value['original_HOLD_reference']
          and decision['original_closed_reference']==old['close']['report_reference'],'SAME_INDEPENDENT96_ROOT_DECISION')
        base=exact(V.PLAN);self.plan_reference=bundle['plan_reference'];self.prepared_reference=bundle['prepared_reference']
        F.need(exact(self.plan_reference)==K.derive_plan(base,V.PLAN,bundle['replacement_wave_review_reference'],wave,bundle['decision_reference'])
          and exact(self.prepared_reference)==K.derive_prepared(old_header,old_report['prepared'],self.plan_reference,bundle['decision_reference']),
          'EXACT_REVIEWED_PLAN_HEADER_INVERSE_DELTA_NO_TASK_OR_RUNTIME_REWRITE')
        F.approve_wave(base['draft'],F.read(base['draft']),bundle['replacement_wave_review_reference'],old_header['config'])
        self.slot=bundle['slot'];F.need(self.slot==wave['jobs'][0],'ONLY_REVIEWED_REPLACEMENT96_SLOT')
        self.report_reference=value['replacement96_closed_reference'];self.report=report=exact(self.report_reference)
        new_run=registration(value['replacement96_run_registration']);new_close=registration(value['replacement96_close_registration'])
        request=exact(new_run['request_reference']);sub=exact(new_run['submission_reference']);jid=str(sub['job_id'])
        F.need(jid not in {K.FAILED_RUN,K.OLD_CLOSE,K.PREPARE} and sub['request']==request
          and sub['request_reference']==new_run['request_reference'] and request['job_name']==self.slot['job_name'],
          'DISTINCT_ACTUAL_NEW96_PARENT_WITH_EXACT_SLOT_BINDING')
        parent(value['replacement96_run_accounting_reference'],jid);parent(report['accounting'],jid)
        complete(report,K.BID,jid,self.plan_reference,self.prepared_reference)
        close_sub=exact(new_close['submission_reference']);self.parent=parent(value['replacement96_close_accounting_reference'],close_sub['job_id'])
        close_request=exact(new_close['request_reference']);argv=close_request['execution_argv']
        F.need(argv[-2:]==['--output',str(Path(self.report_reference['path']).parent)],'NEW96_CLOSE_OUTPUT_PIN_BINDING')
        self.close_output=str(Path(self.report_reference['path']).parent)
        late=registration(value['late95_close_registration']);late_report=exact(value['late95_closed_reference'])
        old95=hold['stages']['batch-00095']['run'];F.need(old95['job_id']=='4521916','EXACT_ACTUAL95_ORIGINAL_RUN')
        run95=exact(old95['actual_registered_references']['request_reference']);argv95=run95['execution_argv']
        prepared95=V.pin(argv95[argv95.index('--prepared')+1])
        parent(late_report['accounting'],'4521916');complete(late_report,'batch-00095','4521916',V.PLAN,prepared95)
        parent(value['late95_close_accounting_reference'],exact(late['submission_reference'])['job_id'])
        late_request=exact(late['request_reference']);self.late95_primary=Path(late_request['execution_argv'][2])
        F.need(self.late95_primary in {V.G.CLOSER/'run.py',V.REPO/'workflows/data_v1_final/conformers/formal_cpu_auto_close_index_v2/run.py'}
          and V.pin(self.late95_primary) in late_request['source_references'],'FROZEN_ORIGINAL95_CLOSER_PRIMARY_ONLY')
        self.late95_report_reference=value['late95_closed_reference']
        F.need(late_request['execution_argv'][-2:]==['--output',str(Path(self.late95_report_reference['path']).parent)],'ACTUAL_LATE95_OUTPUT_BINDING')
        self.entries[('batch-00095','close')]=late;self.entries[(K.BID,'run')]=new_run;self.entries[(K.BID,'close')]=new_close
        # Legacy33 metadata replacement remains part of the original frozen
        # controller authority; no historical close path is silently reverted.
        self.legacy=RP.Repair(prior['repair_map_reference'],prior)


class ClosurePaths:
    def __init__(self,recovery):
        self.recovery=recovery;self.reference=recovery.reference;self.failed=recovery.failed;self.parent=recovery.parent
    def primary(self,bid):
        if bid==K.BID:return F.HERE/'close.py'
        if bid=='batch-00095':return self.recovery.late95_primary
        return self.recovery.legacy.primary(bid)
    def output(self,bid):
        if bid==K.BID:return Path(self.recovery.close_output)
        if bid=='batch-00095':return Path(self.recovery.late95_report_reference['path']).parent
        return self.recovery.legacy.output(bid)
    def report_path(self,bid):
        if bid==K.BID:return Path(self.recovery.report_reference['path'])
        if bid=='batch-00095':return Path(self.recovery.late95_report_reference['path'])
        return self.recovery.legacy.report_path(bid)

# Explicit resource-only derivation; old failed96 checks remain original.
from workflows.data_v1_final.execution.sprime_wave2_recovery96_v1 import contract as OLD_K
import copy
BID=OLD_K.BID;FAILED_RUN=OLD_K.FAILED_RUN;OLD_CLOSE=OLD_K.OLD_CLOSE;PREPARE=OLD_K.PREPARE
zero_consumption=OLD_K.zero_consumption


def replacement_slot(old,review):
    F.need(len(review['jobs'])==1 and review['maximum_concurrent_jobs']==1,'ONE_EXPLICIT96_RESOURCE_SLOT')
    new=review['jobs'][0];F.need(old['batch_id']==new['batch_id']==BID,'ONLY_OLD96')
    allowed={'node','job_name','output_root'}
    F.need(set(old)==set(new) and all(old[k]==new[k] for k in old if k not in allowed),'ONLY_EXPLICIT_NODE_NAME_OUTPUT_DELTA')
    F.future_slot(new)
    F.need(new['job_name']!=old['job_name'] and new['output_root']!=old['output_root'],'NEW96_NAME_AND_OUTPUT')
    return copy.deepcopy(new)


def derive_plan(original,original_reference,review_reference,review,decision_reference):
    F.need(len(original['jobs'])==179 and original['runtime']['job_id']=='4521486'
      and original['imports320_durably_verified'] is True,'ORIGINAL179_CPU_FREEZE_HISTORY')
    ids=[x['batch_id'] for x in review['jobs']]
    F.need(ids==[BID] or ids==list(F.FUTURE),'ONLY_SINGLE96_OR_REMAINING83_PLAN')
    old={x['batch_id']:x for x in original['jobs']}
    for slot in review['jobs']:
        F.future_slot(slot);previous=old[slot['batch_id']]
        F.need(set(slot)==set(previous) and all(slot[k]==previous[k] for k in slot if k not in {'node','job_name','output_root'}),
          'ONLY_FIXED17_RESOURCE_SLOT_DELTA_NO_TASK_REWRITE')
    result=copy.deepcopy(original)
    result.update(jobs=copy.deepcopy(review['jobs']),root_review=review_reference,maximum_concurrent_jobs=review['maximum_concurrent_jobs'],
      requested_allocation_core_seconds_ceiling=16*28800*len(ids),
      resource_node17_derivation={'origin_plan_reference':original_reference,'root_decision_reference':decision_reference,
        'new_CPU_freeze_claimed':False,'original_runtime4521486_retained':True,'tasks_changed':False})
    reverse=copy.deepcopy(result);reverse.pop('resource_node17_derivation')
    for k in ('jobs','root_review','maximum_concurrent_jobs','requested_allocation_core_seconds_ceiling'):
        if k in original:reverse[k]=copy.deepcopy(original[k])
        else:reverse.pop(k,None)
    F.need(F.canonical(reverse)==F.canonical(original),'INVERSE_PLAN_BYTES_RESTORE_ALL_OLD_METADATA')
    return result


def derive_prepared(original,original_reference,plan_reference,decision_reference):
    F.need(original['runtime']['job_id']==PREPARE and original['molecules']==500 and original['batch']['batch_id']==BID,'ORIGINAL96_PREPARE_ONLY')
    result=copy.deepcopy(original);result.update(plan=plan_reference,resource_node17_derivation={
      'origin_prepared_reference':original_reference,'root_decision_reference':decision_reference,'new_CPU_prepare_claimed':False,
      'old_runtime4521921_CPU13_retained':True,'task_bytes_changed':False})
    reverse=copy.deepcopy(result);reverse.pop('resource_node17_derivation');reverse['plan']=original['plan']
    F.need(F.canonical(reverse)==F.canonical(original) and result['tasks']==original['tasks'],'INVERSE_HEADER_AND_IDENTICAL_TASK_REFERENCE')
    return result
