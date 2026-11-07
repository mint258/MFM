"""Collect explicit input bindings from closed metadata and Root's transported bodies.

This writes input fields only. Root supplies actual runtime/startup/source pins and
submits the independently reviewed job. No large body is hashed by this helper.
"""
import argparse
import json
from pathlib import Path
from workflows.expansion.coconut_alpha_cached735_v1 import support as S
from .reads import key,triple
from .parse import need


def collect(bundle_reference,review_reference,index_reference,budget_reference,official_transport):
    bundle=S.load(bundle_reference);review=S.load(review_reference);consumed=S.load(review['source_replica_readback'])
    b=bundle['original_alpha_bound_source_segments'];bindings={}
    def add(src,dst=None):
        src=triple(src);dst=triple(dst or src)
        need(src['bytes']==dst['bytes'] and src['sha256']==dst['sha256'],'IDENTICAL_BODY_NOT_PATH_SUBSTITUTION')
        old=bindings.get(key(src));need(not old or old['replica_reference']==dst,'NO_AMBIGUOUS_SOURCE_BINDING')
        if src['path'].startswith('/share/home/zixiao/'):endpoint,uid='202.38.247.57:22',1278
        elif src['path'].startswith('/gfshome/alpha/'):endpoint,uid='218.192.171.238:22',1264
        else:endpoint,uid='WINDOWS_LOCAL_CACHE',None
        bindings[key(src)]=dict(source_reference=src,replica_reference=dst,origin_endpoint=endpoint,origin_uid=uid)
    def inherited(dst):
        found=[x for x in consumed['files'] if triple(x['replica_reference'])==triple(dst)]
        need(len(found)==1 and found[0]['whole_SHA256_verified'] is True,'EXACT_PRIOR187_SOURCE_REPLICA_AUTHORITY')
        add(found[0]['source_reference'],dst)
    for ref in [bundle_reference,review_reference,index_reference,budget_reference,review['index_receipt'],
                review['actual_accounting_reference'],review['source_replica_readback'],review['closed_database'],
                b['profile_receipt_reference'],b['full_inventory_receipt_reference']]:add(ref)
    rule=next(x['current_actual_reference'] for x in bundle['actual_index1885187_prior_whole_body_authorities']
              if x['current_actual_reference']['sha256']=='462256a904210e4dd5185af88c1f15578e164d3a6483226dc4aa7f90d4d4956c')
    inherited(rule);inherited(b['original_1slg_union']['current_replica_reference'])
    loc=b['source_oldcase18']['binding']['original_source_locator']['source_reference']
    matches=[x for x in consumed['files'] if triple(x['source_reference'])==triple(loc)]
    need(len(matches)==1,'ORIGINAL_1PTS_HOLD_LOCATOR_PRESENT_IN187_COMPLETE_SOURCE_READS')
    add(loc,matches[0]['replica_reference'])
    add(b['source_old_policy_original_reference'],b['source_old_policy_actual_replica_reference'])
    inherited(b['existing_accepted_strict5_rows'][0]['current_replica_reference'])
    for item in b['original_1slg_source_metadata_segments']+b['original_1slg_raw_record_segments']+[b['original_1slg_native_result']]:
        add(item['original_whole_reference'],item.get('current_replica_reference',item['original_whole_reference']))
    official={}
    for name,entry in official_transport.items():
        captured=bundle['official_public_source_cache'][name]
        need(entry['source_reference']==captured['local_cache_reference'] and entry['url']==captured['url'],
             'ROOT_TRANSPORT_EXPLICIT_CAPTURE_IDENTITY_AND_URL')
        add(entry['source_reference'],entry['replica_reference']);official[name]=entry
    return dict(schema='MOLNET_CASE18_NATIVE_EVIDENCE_INPUT_FIELDS_V1',
        proposed_bundle_reference=bundle_reference,old_index_root_acceptance_reference=review_reference,
        original1PTS_index_reference=index_reference,reviewed_storage_budget_reference=budget_reference,
        original_alpha_code_root='/gfshome/alpha/codex_data_v1_20261026/code',
        input_bindings=list(bindings.values()),official_body_bindings=official,
        runtime_and_proof_and_code_references_pending_root=True,no_job_submitted=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','index-root-acceptance','original-index','future-budget-review','official-transport','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();value=collect(S.pin(a.bundle),S.pin(a.index_root_acceptance),S.pin(a.original_index),
                                  S.pin(a.future_budget_review),json.loads(a.official_transport.read_bytes()))
    S.save(a.output,value)


if __name__=='__main__':main()
