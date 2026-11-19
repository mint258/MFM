"""One producer pass for official TDC, Polaris Parquet and ASAP Zarr sources."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import time
from rdkit import RDLogger
import pyarrow as pa
import pyarrow.parquet as pq
from .acquire import guard,quota_headroom
from .build_csv_domain import SCHEMA
from .domain import assess
from .source_tables import source_rows


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--dataset',required=True)
    p.add_argument('--attempt',required=True)
    p.add_argument('--quota-snapshot',type=Path,required=True)
    a=p.parse_args()
    plan=json.loads(a.plan.read_text());source=plan['assets'][a.dataset]
    root=Path(plan['data_root']);out=root/'domain'/a.dataset/a.attempt
    if not (root/'acquisition'/(a.dataset+'.json')).is_file():
        raise ValueError('Source transport is not closed')
    peak=12*(source.get('existing_source_bytes',0)+sum(x['bytes'] for x in source['files']))+67108864
    def protect():
        q=json.loads(a.quota_snapshot.read_text())
        if q['uid']!=os.getuid() or q['generation']!='benchmarkB020261119' or q['returncode']!=0 or not 0<=time.time()-q['observed_epoch']<=90:
            raise RuntimeError('Missing/stale/mismatched quota observation')
        guard(root,peak,quota_headroom(q['raw'],os.getuid()),time.monotonic(),114569896448+1073741824)
    protect();out.mkdir(parents=True,exist_ok=False)
    counters={};buffer=[];RDLogger.DisableLog('rdApp.error')
    with pq.ParquetWriter(out/'all_rows.parquet',SCHEMA,compression='zstd') as writer:
        def flush():
            if buffer:
                protect();writer.write_table(pa.Table.from_pylist(buffer,schema=SCHEMA));buffer.clear()
        for file,index,raw,split in source_rows(plan,a.dataset):
            counts=counters.setdefault(file,{'source_file':file,'before':0,'domain_eligible':0,'retained':0,
                'blind_fallback_required':0,'salts_removed':0,'reason_counts_nonexclusive':Counter(),'primary_reason_counts':Counter()})
            value=assess(raw[source['smiles_column']],adme=a.dataset!='pKahub',blind=bool(source.get('blind_no_filter')))
            for key in ('domain_eligible','retained','blind_fallback_required'):
                counts[key]+=value[key]
            counts['before']+=1;counts['salts_removed']+=value['salt_removed']
            counts['reason_counts_nonexclusive'].update(value['reasons'])
            if value['reasons']:counts['primary_reason_counts'][value['reasons'][0]]+=1
            buffer.append({'dataset':a.dataset,'source_file':file,'source_row':index,
                'record_id':a.dataset+':'+file+':'+str(index),
                'original_smiles':value['original_smiles'],'model_smiles':value['model_smiles'],
                'model_atom_to_source':value['model_atom_to_source'],'heavy_atoms':value['heavy_atoms'],
                'charge':value['charge'],'salt_removed':value['salt_removed'],
                'domain_eligible':value['domain_eligible'],'retained':value['retained'],
                'blind_fallback_required':value['blind_fallback_required'],
                'exclusion_reasons':value['reasons'],'official_split':split,
                'original_fields_json':json.dumps(raw,ensure_ascii=False)})
            if len(buffer)>=4096:flush()
        flush()
    report={'status':'DOMAIN_COUNTS_COMPLETE','dataset':a.dataset,'counts':list(counters.values()),
        'records':str(out/'all_rows.parquet'),'source_release':source.get('source_release'),
        'rdkit':'2025.09.5','label_or_conformation_ready':False,'independent_readback':False,
        'split_source_files':[str(root/'raw'/a.dataset/x['name']) for x in source['files'] if x['name'].endswith('.json')],
        'raw_numeric_values':'Original typed values preserved in original_fields_json; no normalization',
        'source_curation':('Author exclude_flag=exclude rows omitted before domain denominator; original TSV and annotation summary retained'
            if a.dataset=='pKahub' else 'Official published artifact'),
        'endpoint_evaluation_exclusions':({'HLM':[519,524,547,553],'MLM':[515,518,521,524,525]}
            if a.dataset=='ASAP_Polaris2025' else None),
        'evaluation_exclusions_are_not_molecule_deletions':True}
    protect();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('DOMAIN_CLOSED',a.dataset,'before',sum(x['before'] for x in counters.values()),
        'eligible',sum(x['domain_eligible'] for x in counters.values()),'retained',sum(x['retained'] for x in counters.values()),flush=True)

if __name__=='__main__':main()
