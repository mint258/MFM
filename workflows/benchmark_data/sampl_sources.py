"""Preserve SAMPL6/7 source identities and link existing pKahub domain records."""
import argparse
from collections import Counter,defaultdict
import csv
import json
from pathlib import Path
import time
import pyarrow as pa
import pyarrow.parquet as pq
from .pprime_tmpfs_queue import capacity

CHALLENGES={'SAMPL6','SAMPL7'}


def source_key(row):
    return (row.get('dataset','').strip(),row.get('rawdataID','').strip())


def build_overlay(original,unified,domain_by_row):
    indexed=defaultdict(list)
    for ordinal,row in unified:indexed[source_key(row)].append((ordinal,row))
    occurrences=Counter(source_key(row) for _,row in original)
    records=[]
    for ordinal,raw in original:
        if source_key(raw)[0] not in CHALLENGES:continue
        links=[]
        for source_row,row in indexed[source_key(raw)]:
            excluded=(row.get('exclude_flag') or '').strip().lower()=='exclude'
            domain=domain_by_row.get(source_row)
            links.append({'unified_source_row':source_row,'unified_global_molid':row.get('molid'),
                'unified_original_fields':row,'author_excluded':excluded,
                'domain_record_id':domain['record_id'] if domain else None,
                'domain_eligible':domain['domain_eligible'] if domain else None,
                'domain_model_smiles':domain['model_smiles'] if domain else None,
                'source_link_state':'AUTHOR_EXCLUDED' if excluded else 'CLOSED_DOMAIN_RECORD_LINKED' if domain else 'CURATED_DOMAIN_LINK_UNAVAILABLE'})
        state='NO_UNIFIED_SOURCE_ID_MATCH' if not links else 'SOURCE_ID_LINKED' if len(links)==1 else 'MULTIPLE_UNIFIED_SOURCE_ID_MATCHES_RETAINED'
        records.append({'source_challenge':source_key(raw)[0],'source_row':ordinal,'rawdataID':raw.get('rawdataID'),
            'challenge_compound_id':raw.get('molid'),'original_smiles':raw.get('reprSMILES_processed'),
            'original_InChIKey':raw.get('InChIKey'),'original_pKa_lexeme':raw.get('Exp_Macro_pKa_processed'),
            'original_fields_json':json.dumps(raw,ensure_ascii=False),'unified_links_json':json.dumps(links,ensure_ascii=False),
            'source_identity_occurrences':occurrences[source_key(raw)],'link_state':state,
            'benchmark_role':'NOT_FROZEN_PENDING_USER_TASK_DEFINITION','atomic_site_labels_inferred':False})
    return records


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path)
    p.add_argument('--domain-manifest',required=True,type=Path);p.add_argument('--attempt',required=True)
    p.add_argument('--quota-snapshot',required=True,type=Path);a=p.parse_args()
    def safe():
        waiting=False
        while True:
            try:capacity(a.root,a.quota_snapshot,1048576);return
            except (OSError,ValueError,KeyError,RuntimeError) as exc:
                if not waiting:print('SAMPL_SOURCE_DISK_WAIT',repr(exc),flush=True)
                waiting=True;time.sleep(2)
    safe();raw=a.root/'raw/pKahub';original_path=raw/'SAMPL_combined_final_processed.tsv'
    unified_path=raw/'combined_unified_dataset.tsv'
    with original_path.open(newline='') as stream:
        original=[(i,row) for i,row in enumerate(csv.DictReader(stream,delimiter='\t')) if source_key(row)[0] in CHALLENGES]
    wanted={source_key(row) for _,row in original}
    with unified_path.open(newline='') as stream:
        selected=[(i,row) for i,row in enumerate(csv.DictReader(stream,delimiter='\t')) if source_key(row) in wanted]
    manifest=json.loads(a.domain_manifest.read_text());needed=[i for i,_ in selected]
    domains=(pq.read_table(manifest['records'],columns=['record_id','source_row','domain_eligible','model_smiles'],
        filters=[('source_row','in',needed)]).to_pylist() if needed else [])
    byrow={row['source_row']:row for row in domains}
    if len(byrow)!=len(domains):raise ValueError('Closed pKahub source rows are not unique')
    records=build_overlay(original,selected,byrow)
    out=a.root/'provenance/SAMPL6_7'/a.attempt;safe();out.mkdir(parents=True,exist_ok=False)
    target=out/'source_links.parquet';pq.write_table(pa.Table.from_pylist(records),target,compression='zstd')
    counts=[]
    for challenge in sorted(CHALLENGES):
        rows=[r for r in records if r['source_challenge']==challenge]
        links=[x for r in rows for x in json.loads(r['unified_links_json'])]
        counts.append({'challenge':challenge,'original_rows_retained':len(rows),
            'original_unique_nonempty_challenge_compound_ids':len({r['challenge_compound_id'] for r in rows if r['challenge_compound_id']}),
            'link_states':dict(Counter(r['link_state'] for r in rows)),
            'author_excluded_unified_links':sum(x['author_excluded'] for x in links),
            'closed_domain_links':sum(x['domain_record_id'] is not None for x in links),
            'domain_eligible_links':sum(x['domain_eligible'] is True for x in links)})
    result={'status':'SOURCE_IDENTITIES_LINKED_BENCHMARK_ROLE_PENDING','records':str(target),'counts':counts,
        'original_source':str(original_path),'unified_source':str(unified_path),'domain_manifest':str(a.domain_manifest),
        'source_commit':'93958c195874f0a248b2448341cabd58b1f3c7a7',
        'source_record_join_key':['dataset','rawdataID'],'compound_identity':['source_challenge','challenge_compound_id'],
        'local_SM_ids_not_global_molids':True,'original_rows_deleted':False,'original_numeric_lexemes_modified':False,
        'author_excluded_original_rows_retained':True,'benchmark_split_frozen':False,'task_form_frozen':False,
        'experimental_macro_vs_micro_reclassified':False,'site_labels_inferred':False,
        'new_geometry_or_quantum_calls':0,'link_does_not_imply_geometry_or_labels_ready':True,
        'new_data_content_hashes':False,'independent_numeric_readback':False}
    safe();(out/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('SAMPL_SOURCE_LINKS_CLOSED',json.dumps(counts),str(out/'manifest.json'),flush=True)

if __name__=='__main__':main()