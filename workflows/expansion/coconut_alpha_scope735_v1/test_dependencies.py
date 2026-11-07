"""Required-reader traversal versus historical incorrect literals; no scientific inputs."""
import copy
import hashlib
import json
import unittest
from .dependencies import Collector,discover,key


class FakeCollector(Collector):
    def __init__(self,bodies):
        self.bodies=bodies;self.mapping={};self.required={};self.json_cache={};self.row_cache={}
        self.observed=[];self.deferred={};self.verified=set();self.calls=[]
    def raw(self,ref,usage,cap):
        k,_=self.add(ref,usage);self.calls.append(ref['path']);raw=self.bodies[ref['path']]
        if len(raw)>cap or len(raw)!=ref['bytes'] or hashlib.sha256(raw).hexdigest()!=ref['sha256']:
            raise ValueError('REQUIRED_ALL11_INPUT_PIN_MISMATCH '+ref['path'])
        self.verified.add(k);return raw


def fixture():
    bodies={}
    def add(name,value=None,raw=None,rows=None):
        if raw is None:raw=(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
        path='/gfshome/alpha/fixture/'+name;bodies[path]=raw
        r=dict(path=path,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if rows is not None:r['rows']=rows
        return r
    text=add('actual.sacct.txt',raw=b'actual accounting text\n')
    account=add('account.json',dict(raw_sacct_reference=text))
    rawsource=add('raw.bin',raw=b'RAW')
    identities=add('identities.jsonl',raw=b'{}\n',rows=1)
    sourcecov=add('source_coverage.json',{})
    ready=add('ready9.json',dict(sources=[dict(dataset='v1',raw_artifacts=[rawsource],
                     coverage_evidence=sourcecov,identities=identities)]))
    request=add('request.json',{})
    proof=add('proof.json',dict(request_reference=request))
    oldplan=add('plan.json',{})
    policy=add('policy.json',{})
    screen=add('screen.py',raw=b'WHITELIST = {6}\n')
    report=add('report.json',{})
    empty=add('rules.jsonl',raw=b'',rows=0)
    domain=dict(screen_source_reference=screen,closed_screen_authority_references=[account])
    result=dict(report_reference=report,policy_reference=policy,candidate_domain_authority=domain,
        base_coverage_reference=sourcecov,raw_artifacts=[rawsource],base_strict5_reference=identities,
        overlay_reference=identities,lower_bound_reference=empty,physical_dispositions_reference=identities)
    molreceipt=add('mol_receipt.json',dict(startup_proof_reference=proof,plan_reference=oldplan,result=result))
    mol=add('mol_acceptance.json',dict(receipt_reference=molreceipt,accounting_reference=account))
    incorrect=add('historical_incorrect_literal.json',{})
    incorrect['sha256']='0'*64
    native=add('original735_receipt.json',dict(plan=incorrect,explanation='Historical plan is not read by headers.original735'))
    originaldata=add('original735.DATA.jsonl',raw=b'{}\n',rows=1)
    auditdata=add('audit735.DATA.jsonl',raw=b'{}\n',rows=1)
    audit=add('audit_receipt.json',dict(result=dict(DATA=auditdata)))
    reply=add('actual_reply.json',dict(role='user',text='Fixture only, no actual approval'))
    scope=add('scope.json',dict(actual_user_reply_reference=reply,audit_receipt_reference=audit,
                              audit_actual_accounting_reference=account))
    ledger=add('ledger.jsonl',raw=(json.dumps(dict(evidence_references=[report],
        new_exclusion_status='APPROVED_SOURCE_SCOPE_DISPOSITION'))+'\n').encode(),rows=1)
    coverage=add('coverage.json',dict(raw_artifacts=[rawsource],identity_parts=[identities],lower_bounds=empty,
        original735_receipt_reference=native,original735_DATA_reference=originaldata,
        original735_actual_accounting_reference=account,physical_dispositions=ledger,source_scope_authority_reference=scope))
    impact=add('impact.json',{})
    cocovalue=dict(coverage_reference=coverage,veto_impact_reference=impact)
    coco=add('coco_acceptance.json',cocovalue)
    return bodies,(ready,mol,coco),incorrect,cocovalue,add


class Source(unittest.TestCase):
    def test_actual_required_routes_reject_stale_pins_but_never_follow_historical_literal(self):
        bodies,roots,incorrect,coco,add=fixture();c=FakeCollector(bodies)
        declared,report=discover(c,*roots)
        self.assertNotIn(incorrect['path'],c.calls)
        self.assertNotIn(key(incorrect),{key(r) for r in declared})
        skipped=report['skipped_historical_reference_pointers']
        self.assertTrue(any(r['pointer']=='$.plan' and r['reference']==incorrect and not r['dereferenced'] for r in skipped))
        self.assertTrue(any(r['consumer_reads']==['headers.scope_authority:all735_structural_audit_DATA']
                            for r in report['required_reads'] if r['reference']['path'].endswith('audit735.DATA.jsonl')))
        # The same stale body in an actual required field must fail. There is no
        # "ignore mismatched refs" fallback and no promotion to an alternate pin.
        modified=copy.deepcopy(coco);modified['veto_impact_reference']=incorrect
        badroot=add('coco_required_bad.json',modified)
        with self.assertRaisesRegex(ValueError,'REQUIRED_ALL11_INPUT_PIN_MISMATCH'):
            discover(FakeCollector(bodies),roots[0],roots[1],badroot)


if __name__=='__main__':unittest.main()
