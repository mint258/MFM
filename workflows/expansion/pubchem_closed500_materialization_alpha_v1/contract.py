"""The fixed formally closed finite500 is input; no new epoch or science."""
import re
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
NAME='pubchem_closed500_materialization_alpha_v1';HERE=Q.ROOT/'code'/NAME;MODULE=NAME+'.run'
PROOF='ALPHA_CLOSED500_MATERIALIZATION_STARTUP_V1'
FILES=('__init__.py','contract.py','metadata.py','resource.py','gate.py','runtime.py','run.py','README.md')
KEYS=('accepted','chemReject','technicalUnresolved');N=124857440
COUNTS={'accepted':110046364,'chemReject':14764875,'technicalUnresolved':46201}
COVERAGE={'path':str(Q.ROOT/'control/pubchem_tail_363412_root_20261030_v2/original_finite500_all_source_rows_accounted_v1.json'),
 'bytes':554554,'sha256':'40fc128704a7a77a4322c5514f8c1afad78ccef19dcb74474d5cacb83ebfc1b5'}
INTENT=Q.ROOT/'control'/NAME/'original_closed500_materialization_intent.json'
def sources():return [Q.ref(HERE/n) for n in FILES]
def merge(*groups):
    d={}
    for group in groups:
        for r in group:
            if r['path'] in d:Q.need(d[r['path']]==r,'SOURCE_REFERENCE_CONFLICT')
            d[r['path']]=r
    return [d[k] for k in sorted(d)]
def locator(r):
    Q.need(set(r)=={'path','bytes','sha256'} and type(r['bytes'])is int and r['bytes']>0
      and re.fullmatch('[0-9a-f]{64}',r['sha256']) and Path(r['path']).is_relative_to(Q.ROOT/'artifacts'),'EXACT_DATA_LOCATOR_NOT_LOGIN_SOURCE')
    Q.literal(r['path']);return r
def header():
    c=Q.load_ref(COVERAGE)
    Q.need(c['schema']=='ROOT_PUBCHEM_ORIGINAL_FINITE500_ROW_COVERAGE_V1'
      and c['status']=='ALL500_SOURCE_ROWS_ACCOUNTED_NOT_POOL_OR_TRAIN_RELEASE'
      and c['source_rows']==N and c['descriptor_count']==500 and c['counts']==COUNTS
      and c['source_row_conservation'] is True and c['UNKNOWN_not_chemical_exclusion'] is True
      and c['decontamination_or_ranked_or_candidate_pool_release'] is False,'ACTUAL_CLOSED500_NO_RELEASE_INPUT')
    return c
def inputs():
    c=header();manifest=Q.load_ref(c['frozen_manifest_reference']);entries=c['source_descriptors'];flat=[];next_ordinal=1;paths=set()
    Q.need(len(entries)==len(manifest['shards'])==500,'EXACT500_METADATA_DESCRIPTORS')
    for i,e in enumerate(entries):
        member=manifest['shards'][i];Q.need(e['descriptor_index']==i and e['original_descriptor']==member
          and e['rows']==member['last_ordinal']-member['first_ordinal']+1
          and set(e['counts'])==set(KEYS) and sum(e['counts'].values())==e['rows'],'ORIGINAL_MEMBER_AND_ROW_MASS')
        bodies=e['scientific_body_locators']
        if type(bodies)is dict:
            Q.need(i not in (363,412),'LOGICAL_SPLIT_NOT_REPLACED_WITH_WHOLE_PART')
            fragments=[{'first_ordinal':member['first_ordinal'],'last_ordinal':member['last_ordinal'],
              'rows':e['rows'],'counts':e['counts'],'Parquet_reference':bodies['features'],
              'journal_reference':bodies['full_dispatch_and_result_journal']}]
        else:
            Q.need(i in (363,412) and len(bodies)==2 and e['closure_kind']=='TWO_FRAGMENT_TRUE_NEW_PARENT_C0','ONLY_EXACT_TWO_LOGICAL_SPLITS')
            logical=Q.load_ref(e['accepted_metadata_reference']);fragments=logical['fragments']
            Q.need(logical['logical_rows']==250000 and logical['counts']==e['counts'] and len(fragments)==2
              and logical['source_row_conservation'] is True,'ACTUAL_PREFIX_PLUS_TAIL_LOGICAL_METADATA')
            for f,b in zip(fragments,bodies):
                Q.need(f['Parquet_reference']==b['Parquet_reference'] and f['journal_reference']==b['journal_reference'],'SAME_EXACT_LOGICAL_FRAGMENTS')
        for j,f in enumerate(fragments):
            Q.need(f['first_ordinal']==next_ordinal and f['last_ordinal']>=next_ordinal
              and f['rows']==f['last_ordinal']-next_ordinal+1 and sum(f['counts'].values())==f['rows'],'NO_HOLES_OVERLAPS_OR_REPEATED_PREFIX')
            for r in (f['Parquet_reference'],f['journal_reference']):
                locator(r);Q.need(r['path'] not in paths,'NO_PHYSICAL_FRAGMENT_READ_TWICE');paths.add(r['path'])
            flat.append({'fragment_id':'%03d_%d'%(i,j),'descriptor_index':i,'first_ordinal':f['first_ordinal'],
              'last_ordinal':f['last_ordinal'],'rows':f['rows'],'counts':f['counts'],
              'Parquet_reference':f['Parquet_reference'],'journal_reference':f['journal_reference'],
              'accepted_metadata_reference':e['accepted_metadata_reference'],'actual_parent_job_id':e['actual_parent_job_id']})
            next_ordinal=f['last_ordinal']+1
    Q.need(len(flat)==502 and next_ordinal==N+1 and {k:sum(f['counts'][k] for f in flat) for k in KEYS}==COUNTS,'EXACT502_ALL124857440_THREE_STATES')
    closure=Q.load_ref(c['new_tail_actual_C0_closure_reference']);Q.need(closure['status']=='ACTUAL_NEW_PARENT_C0_TWO_ORIGINAL_DESCRIPTORS_CLOSED','REAL_TAIL_C0_NOT_FUTURE')
    producer=Q.load_ref(closure['producer_receipt_reference']);old_plan=Q.load_ref(producer['plan_reference'])
    return c,flat,old_plan
def validate(p):
    Q.need(p['schema']=='ALPHA_CLOSED500_MATERIALIZATION_PLAN_V1' and p['status']=='READY'
      and p['endpoint']==Q.ENDPOINT and p['uid']==1264 and p['mode']=='closed500_materialization'
      and type(p['cpus'])is int and p['cpus'] in (16,32) and p['node'] in Q.NODES
      and 3600<=p['wall_seconds']<=86400 and p['wall_seconds']%60==0
      and 8<<30<=p['output_cap_bytes']<=384<<30 and p['software_budget_bytes']==64<<30
      and p['rss_stop_bytes']==56<<30 and p['coverage_reference']==COVERAGE
      and p['intent_path']==str(INTENT) and p['new_source_references']==sources()
      and p['fragment_count']==502 and p['source_rows']==N and p['expected_counts']==COUNTS
      and p['no_chemistry_no_filter_no_release'] is True,'EXACT_ONE_CLOSED500_IO_PARENT')
    Q.need(p['python']==str(Q.ROOT/'chemprop_compatible_v2/bin/python')
      and p['execution_argv']==[p['python'],'-B','-m',MODULE,'--plan',p['plan_path'],'--startup-proof',p['startup_proof_path']]
      and Path(p['startup_proof_path']).parent==Path(p['plan_path']).parent
      and re.fullmatch('[A-Za-z0-9_]{1,80}',p['job_name']),'EXACT_SOURCE_ARGV')
    out=Q.literal(p['output_directory']);Q.need(out.is_relative_to(Q.ROOT/'artifacts'/NAME) and out!=Q.ROOT/'artifacts'/NAME,'FRESH_ISOLATED_OUTPUT_ROOT')
    for r in merge(p['source_references'],[COVERAGE,p['cost_gate_reference'],p['storage_scope_review_reference']]):Q.verify(r)
    return p
def review(p):
    r=Q.load_ref(p['root_review_reference']);candidate=Q.load_ref(p['candidate_reference'])
    Q.need(r['schema']=='ROOT_EXACT_CLOSED500_IO_REVIEW_V1' and r['status']=='APPROVED' and r['reviewer']=='root'
      and r['candidate_reference']==p['candidate_reference'] and r['original_SQL_minimum_CID_alias_semantics'] is True
      and r['no_chemistry_no_decontamination_no_release'] is True
      and p==dict(candidate,status='READY',candidate_reference=p['candidate_reference'],root_review_reference=p['root_review_reference']),'EXACT_ROOT_IO_PLAN_REVIEW')
    return r
