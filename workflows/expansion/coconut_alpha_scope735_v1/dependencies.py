"""Declared reads from original292 compose/headers/build, never arbitrary provenance recursion."""
import hashlib
import json
from pathlib import Path
from workflows.expansion.alpha_runtime_v1 import common as Q
from workflows.expansion.coconut_alpha_cached735_v1 import support as S


def triple(ref):return {k:ref[k] for k in ('path','bytes','sha256')}


def key(ref):return json.dumps(triple(ref),sort_keys=True)


def refs_in(value,pointer='$'):
    if isinstance(value,dict):
        if {'path','bytes','sha256'}<=value.keys() and isinstance(value['path'],str):
            yield pointer,triple(value)
        else:
            for k,v in value.items():yield from refs_in(v,pointer+'.'+k)
    elif isinstance(value,list):
        for i,v in enumerate(value):yield from refs_in(v,pointer+'['+str(i)+']')


class Collector:
    """Metadata planner only. Actual unchanged Reader rehashes every body it uses."""
    def __init__(self,transport_ref):
        transport=Q.load(Q.verify(transport_ref))
        Q.need(transport['schema']=='PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1'
            and transport['status']=='VERIFIED_REPLICAS_CLOSED'
            and transport['destination']=={'endpoint':'218.192.171.238:22','uid':1264},
            'Actual511 source transport required')
        self.mapping={key(x['source_reference']):triple(x['replica_reference']) for x in transport['replicas']}
        self.required={};self.json_cache={};self.row_cache={};self.observed=[]
        self.deferred={};self.verified=set()

    def add(self,ref,usage):
        ref=triple(ref);k=key(ref)
        Q.need(ref['path'].startswith(('/gfshome/alpha/','/share/home/zixiao/')),
               'Required actual Main/Alpha input, no implicit foreign path')
        if k not in self.required:self.required[k]=dict(reference=ref,consumer_reads=[])
        if usage not in self.required[k]['consumer_reads']:self.required[k]['consumer_reads'].append(usage)
        physical=self.mapping.get(k)
        if physical is None:
            Q.need(ref['path'].startswith('/gfshome/alpha/'),'Required Main source lacks closed explicit replica '+ref['path'])
            physical=ref
        Q.need(all(ref[x]==physical[x] for x in ('bytes','sha256')),'Exact original/replica body identity')
        return k,physical

    def raw(self,ref,usage,cap):
        k,physical=self.add(ref,usage)
        try:raw=S.read(physical,cap)
        except BaseException as exc:
            p=Path(physical['path']);actual={'path':str(p)}
            if p.exists():
                actual['bytes']=p.stat().st_size
                # Failure witness is bounded; never hash an oversized changed body.
                if actual['bytes']<=cap:actual['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
            raise ValueError('REQUIRED_ALL11_INPUT_PIN_MISMATCH '+json.dumps(dict(
                consumer_read=usage,expected=physical,current=actual),sort_keys=True)) from exc
        self.verified.add(k);return raw

    def json(self,ref,usage):
        k,_=self.add(ref,usage)
        if k not in self.json_cache:
            value=json.loads(self.raw(ref,usage,8<<20));self.json_cache[k]=value
            for pointer,child in refs_in(value):
                self.observed.append(dict(parent_reference=triple(ref),pointer=pointer,reference=child))
        return self.json_cache[k]

    def rows(self,ref,usage):
        k,_=self.add(ref,usage)
        if k not in self.row_cache:
            raw=self.raw(ref,usage,32<<20);lines=raw.splitlines(keepends=True)
            Q.need((not raw or raw.endswith(b'\n')) and len(lines)==ref['rows'],
                   'Closed required metadata ledger EOF/row census')
            values=[json.loads(line) for line in lines];self.row_cache[k]=values
            for i,value in enumerate(values):
                for pointer,child in refs_in(value):
                    self.observed.append(dict(parent_reference=triple(ref),pointer='$row['+str(i)+']'+pointer[1:],reference=child))
        return self.row_cache[k]

    def verify(self,ref,usage):
        k,_=self.add(ref,usage)
        if k in self.verified:return
        # Metadata preparation verifies bounded text inputs. Complete raw/strict5/
        # DATA body reads remain mandatory in unchanged native Reader/build.
        if ref['bytes']<=8<<20 and Path(ref['path']).suffix in ('.json','.txt','.py','.jsonl'):
            self.raw(ref,usage,8<<20)
        else:self.deferred[k]=dict(reference=triple(ref),consumer_read=usage,
            whole_body_validation='REQUIRED_IN_ACTUAL_UNCHANGED_NATIVE_READER;_NOT_CLAIMED_BY_METADATA_BUILDER')

    def result(self):
        skipped=[];seen=set()
        for item in self.observed:
            k=key(item['reference']);identity=(key(item['parent_reference']),item['pointer'],k)
            if k not in self.required and identity not in seen:
                seen.add(identity)
                skipped.append(dict(item,reason='HISTORICAL_PROVENANCE_NOT_DEREFERENCED_BY_ORIGINAL292_COMPOSE_HEADERS_BUILD',
                                    dereferenced=False,original_literal_retained=True))
        return sorted((r['reference'] for r in self.required.values()),key=lambda r:(r['path'],r['sha256'])),dict(
            policy='ORIGINAL292_EXPLICIT_READER_CALL_GRAPH_V1',
            required_reads=list(self.required.values()),required_metadata_bodies_verified=len(self.verified),
            full_large_source_body_hash_claimed=False,
            mandatory_native_large_body_reads=list(self.deferred.values()),
            skipped_historical_reference_pointers=skipped,
            historical_references_are_not_data_references=True,
            unchanged_native_consumer_still_rejects_any_missing_or_mismatched_required_body=True)


def discover(c,ready_ref,mol_ref,coco_ref,manifest_ref=None):
    """Selectors mirror only actual Reader calls in original292; no science executes."""
    ready=c.json(ready_ref,'manifest.compose/headers.approvals:ready9')
    if manifest_ref:
        manifest=c.json(manifest_ref,'run:source_manifest')
        Q.need(manifest['prior_manifest_reference']==ready_ref
            and manifest['root_molnet21_acceptance_reference']==mol_ref
            and manifest['root_coconut735_acceptance_reference']==coco_ref,'Exact source manifest roots')
    # Original nine READY full sources: no Common population is substituted.
    for source in ready['sources']:
        if source['dataset'] not in ('coconut','moleculenet'):
            for ref in source['raw_artifacts']:c.verify(ref,'build.legacy_header:raw_artifact')
            c.json(source['coverage_evidence'],'build.legacy_header:coverage')
            c.verify(source['identities'],'build.insert_rows:complete_identity_rows')
    def account(ref):
        a=c.json(ref,'headers.parent:accounting')
        if a.get('raw_sacct_reference'):c.verify(a['raw_sacct_reference'],'headers.parent:raw_sacct')
    mol=c.json(mol_ref,'compose/headers.molnet:Root_acceptance')
    receipt=c.json(mol['receipt_reference'],'compose/headers.molnet:original_receipt')
    account(mol['accounting_reference'])
    proof=c.json(receipt['startup_proof_reference'],'headers.molnet:startup_proof')
    c.json(receipt['plan_reference'],'headers.molnet:original_plan')
    c.json(proof['request_reference'],'headers.molnet:original_request')
    result=receipt['result']
    c.json(result['report_reference'],'headers.molnet:whole_result_report')
    c.verify(result['policy_reference'],'headers.molnet:policy')
    domain=result['candidate_domain_authority']
    c.verify(domain['screen_source_reference'],'headers.domain:original_screen_AST')
    for ref in domain['closed_screen_authority_references']:c.verify(ref,'headers.domain:closed_screen_authority')
    c.json(result['base_coverage_reference'],'headers.molnet:base_coverage')
    for ref in result['raw_artifacts']:c.verify(ref,'build:MolNet_all_raw_artifacts')
    for field in ('base_strict5_reference','overlay_reference','lower_bound_reference'):
        c.verify(result[field],'build:MolNet_'+field)
    c.verify(result['physical_dispositions_reference'],'headers.molnet:all21_dispositions')
    coco=c.json(coco_ref,'compose/headers.coconut:Root_acceptance')
    closed=c.json(coco['coverage_reference'],'compose/headers.coconut:complete735_coverage')
    c.json(coco['veto_impact_reference'],'compose/headers.coconut:actual_accepted735_rule_impact')
    for ref in closed['raw_artifacts']:c.verify(ref,'build:COCONUT_all_raw_artifacts')
    for ref in closed['identity_parts']:c.verify(ref,'build:COCONUT_all_identity_parts')
    c.verify(closed['lower_bounds'],'build.constraints:COCONUT_actual_rule_file')
    c.json(closed['original735_receipt_reference'],'headers.original735:original_native735_receipt')
    c.verify(closed['original735_DATA_reference'],'headers.original735:all735_original_DATA')
    account(closed['original735_actual_accounting_reference'])
    ledger=c.rows(closed['physical_dispositions'],'headers.coconut:all735_physical_dispositions')
    scoped=False
    for row in ledger:
        for ref in row['evidence_references']:c.verify(ref,'headers.coconut:physical_disposition_evidence')
        scoped|=row['new_exclusion_status']=='APPROVED_SOURCE_SCOPE_DISPOSITION'
    if scoped:
        scope=c.json(closed['source_scope_authority_reference'],'headers.scope_authority:actual_scope')
        c.json(scope['actual_user_reply_reference'],'headers.scope_authority:actual_prior_user_reply')
        audit=c.json(scope['audit_receipt_reference'],'headers.scope_authority:structural_audit_receipt')
        account(scope['audit_actual_accounting_reference'])
        c.verify(audit['result']['DATA'],'headers.scope_authority:all735_structural_audit_DATA')
    return c.result()
