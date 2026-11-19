"""Recover PPE graphs from original systematic names, keeping unresolved names explicit."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import select
import subprocess
import unicodedata
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem
from .admission import protect
from .domain import assess
from .build_csv_domain import SCHEMA
from .ppe_reference import target_rows,numeric


def normalize_name(name):
    text=unicodedata.normalize('NFKC',name)
    return ' '.join(''.join('-' if unicodedata.category(c)=='Pd' else c for c in text).split())


def name_key(name):
    text=normalize_name(name)
    # Case of isolated stereodescriptors remains significant: R and r are not
    # interchangeable. Capitalization within ordinary chemical words is not.
    stereo=tuple(re.findall(r'(?<![A-Za-z])(?:\d+)?[RrSsDdLlEeZz](?![A-Za-z])',text))
    return text.casefold(),stereo


def formula_matches(smiles,numbers):
    mol=Chem.MolFromSmiles(smiles)
    if mol is None:return False
    return Counter(a.GetAtomicNum() for a in Chem.AddHs(mol).GetAtoms())==Counter(numbers)


class Opsin:
    def __init__(self,java,jar):
        self.process=subprocess.Popen([str(java),'-XX:ActiveProcessorCount=1','-XX:+UseSerialGC',
            '-Xmx512m','-jar',str(jar),'-osmi','-n','/dev/stdin'],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)

    def parse(self,name):
        if '\n' in name or '\t' in name:raise ValueError('One original PPE name per OPSIN input row')
        self.process.stdin.write(name+'\n');self.process.stdin.flush()
        line=self.process.stdout.readline()
        if not line:raise RuntimeError('OPSIN exited before its corresponding output row')
        smiles,returned=line.rstrip('\r\n').split('\t',1)
        if returned!=name:raise ValueError('OPSIN input/output name correspondence differs')
        messages=[]
        # CLI emits each record's warning before flushing that record's stdout.
        # Drain stderr now, before submitting the next record, to retain status.
        while select.select([self.process.stderr],[],[],0)[0]:
            data=os.read(self.process.stderr.fileno(),65536)
            if not data:break
            messages.append(data.decode('utf-8',errors='replace'))
        return smiles,''.join(messages).strip()

    def close(self):
        self.process.stdin.close()
        code=self.process.wait(timeout=30)
        self.process.stdout.close();self.process.stderr.close()
        if code:raise RuntimeError('OPSIN exit code '+str(code))


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--reference-manifest',type=Path,required=True);p.add_argument('--attempt',required=True)
    p.add_argument('--quota-snapshot',type=Path,required=True)
    a=p.parse_args();root=a.root
    def safe(needed):
        g=json.loads((root/'geometry/shared_v1/queue.manifest.json').read_text())
        reserve=1073741824+max(67108864,g['storage_forecast_bytes']-Path(g['queue']).stat().st_size)
        protect(root,needed,a.quota_snapshot,own_concurrent_bytes=reserve)
    safe(67108864)
    out=root/'domain/PPE1694'/a.attempt;out.mkdir(parents=True,exist_ok=False)
    reference=json.loads(a.reference_manifest.read_text())
    with (root/'raw/PPE1694/SI_review_23_12_2020.txt').open() as f:methods,targets=target_rows(iter(f))
    java=next((root/'runtime_ppe_jre').glob('*/bin/java'))
    parser=Opsin(java,root/'raw/runtime_ppe_opsin/opsin-cli-2.9.0-jar-with-dependencies.jar')
    rows=[];target_output=[];pending=[];reasons=Counter();primary=Counter();eligible=matched=0
    try:
        for batch in pq.ParquetFile(reference['reference']).iter_batches(columns=[
                'record_id','source_frame','system_name','atomic_numbers','known_domain_rejection_reasons']):
            for row in batch.to_pylist():
                index=row['source_frame']+1;target=targets[index]
                bound=name_key(target['name'])==name_key(row['system_name']);matched+=bound
                values={k:numeric(v) for k,v in target['lexemes'].items()} if bound else {}
                expt=values.get('Expt');pm7=values.get('PM7')
                target_output.append({'record_id':row['record_id'],'source_target_row_id':index,
                    'geometry_name':row['system_name'],'target_name':target['name'],'target_name_bound':bound,
                    'binding_rule':'Same author ordinal plus Unicode-dash/ordinary-word capitalization equality; stereo case retained',
                    'original_lexemes_json':json.dumps(target['lexemes']),
                    'experimental_DeltaHf_kcal_mol':expt,'published_PM7_DeltaHf_kcal_mol':pm7,
                    'residual_experimental_minus_published_PM7_kcal_mol':expt-pm7 if expt is not None and pm7 is not None else None})
                known=row['known_domain_rejection_reasons'];smiles=None;message='';state='KNOWN_REJECTED'
                if not known:
                    smiles,message=parser.parse(normalize_name(row['system_name']))
                    if not smiles or message:
                        state='NAME_PARSE_UNRESOLVED';domain=None
                    elif not formula_matches(smiles,row['atomic_numbers']):
                        state='NAME_GRAPH_REFERENCE_FORMULA_MISMATCH';domain=None
                    else:domain=assess(smiles);state='GRAPH_DOMAIN_CLASSIFIED'
                else:domain=None
                if domain is not None:
                    rs=domain['reasons'];ok=domain['domain_eligible'];model=domain['model_smiles']
                    mapping=domain['model_atom_to_source'];heavy=domain['heavy_atoms'];charge=domain['charge']
                else:
                    rs=known;ok=False;model=None;mapping=[];heavy=sum(n!=1 for n in row['atomic_numbers']);charge=None
                    if not known:pending.append({'record_id':row['record_id'],'name':row['system_name'],
                        'status':state,'OPSIN_smiles':smiles,'OPSIN_message':message})
                eligible+=ok;reasons.update(rs)
                if rs:primary[rs[0]]+=1
                rows.append({'dataset':'PPE1694','source_file':reference['reference'],'source_row':row['source_frame'],
                    'record_id':row['record_id'],'original_smiles':smiles,'model_smiles':model,
                    'model_atom_to_source':mapping,'heavy_atoms':heavy,'charge':charge,'salt_removed':False,
                    'domain_eligible':ok,'retained':ok,'blind_fallback_required':False,'exclusion_reasons':rs,
                    'official_split':None,'original_fields_json':json.dumps({'source_IUPAC_name':row['system_name'],
                        'OPSIN_version':'2.9.0','OPSIN_message':message,'graph_metadata_state':state,
                        'model_atom_to_source_basis':'OPSIN SMILES parser graph indices, NOT XYZ indices',
                        'graph_to_reference_atom_binding':'PENDING; no atom permutation inferred',
                        'reference_geometry_regenerated':False,'target_name_bound':bound})})
                if len(rows)%128==0:safe(67108864)
    finally:parser.close()
    safe(67108864)
    pq.write_table(pa.Table.from_pylist(rows,schema=SCHEMA),out/'all_rows.parquet',compression='zstd')
    pq.write_table(pa.Table.from_pylist(target_output),out/'target_name_overlay.parquet',compression='zstd')
    report={'status':'DOMAIN_PARTIAL_NAME_GRAPH_UNRESOLVED' if pending else 'DOMAIN_READY_REFERENCE_ATOM_BINDING_PENDING',
        'dataset':'PPE1694','records':str(out/'all_rows.parquet'),'target_name_overlay':str(out/'target_name_overlay.parquet'),
        'counts':[{'before':len(rows),'domain_eligible':eligible,'retained':eligible,
            'reason_counts_nonexclusive':dict(reasons),'primary_reason_counts':dict(primary),
            'graph_metadata_pending':len(pending)}],'unresolved_name_graphs':pending,'domain_filter_complete':not pending,
        'name_matched_targets':matched,'unmatched_target_rows':[r for r in target_output if not r['target_name_bound']],
        'target_values_modified':False,'methods':methods,'reference_manifest':str(a.reference_manifest),
        'OPSIN_version':'2.9.0','OPSIN_options':'Default strict parsing; no radicals or uninterpretable stereo options',
        'reference_coordinates_read_again':False,'reference_geometries_regenerated':False,
        'independent_numeric_readback':False,'atom_level_P_D_ready':False}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PPE_NAME_GRAPH_DOMAIN_CLOSED',len(rows),eligible,'unresolved',len(pending),'targets_bound',matched,flush=True)

if __name__=='__main__':main()
