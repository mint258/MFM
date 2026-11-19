"""Bind author NMR reference molecule IDs to the original Jonas molecular graphs."""
import argparse
from collections import Counter
import io
import json
from pathlib import Path
import pickle
import tarfile
from pandas.compat.pickle_compat import Unpickler
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem
from .admission import protect
from .domain import assess
from .build_csv_domain import SCHEMA


ALLOWED={('pandas.core.frame','DataFrame'),('pandas.core.internals','BlockManager'),
    ('pandas.core.internals.managers','BlockManager'),('pandas.core.indexes.range','RangeIndex'),
    ('pandas.core.indexes.base','_new_Index'),('pandas.core.indexes.base','Index'),
    ('pandas.core.indexes.numeric','Int64Index'),('numpy.core.multiarray','_reconstruct'),
    ('numpy._core.multiarray','_reconstruct'),
    ('numpy','ndarray'),('numpy','dtype'),('rdkit.Chem.rdchem','Mol'),
    ('pandas._libs.internals','_unpickle_block'),('builtins','slice')}


def restricted_graph_load(payload):
    class GraphContainersOnly(Unpickler):
        def find_class(self,module,name):
            if (module,name) not in ALLOWED:
                raise pickle.UnpicklingError('Unapproved original graph container: '+module+'.'+name)
            return super().find_class(module,name)
    return GraphContainersOnly(io.BytesIO(payload)).load()


def graph_lookup(data):
    result={}
    for split in ('train_df','test_df'):
        for mid,mol in data[split][['molecule_id','rdmol']].itertuples(index=False,name=None):
            key=int(mid)
            if key in result:
                previous,provenance=result[key]
                if Chem.MolToSmiles(previous,canonical=False,isomericSmiles=True,allHsExplicit=True)!=Chem.MolToSmiles(mol,canonical=False,isomericSmiles=True,allHsExplicit=True):
                    raise ValueError('One original Jonas molecule ID has inconsistent ordered graphs')
                provenance.append(split)
            else:result[key]=(mol,[split])
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--reference-manifest',type=Path,required=True)
    p.add_argument('--attempt',required=True);p.add_argument('--quota-snapshot',type=Path,required=True)
    a=p.parse_args();root=a.root
    def safe(needed):
        g=json.loads((root/'geometry/shared_v1/queue.manifest.json').read_text())
        reserve=1073741824+max(67108864,g['storage_forecast_bytes']-Path(g['queue']).stat().st_size)
        protect(root,needed,a.quota_snapshot,own_concurrent_bytes=reserve)
    safe(268435456)
    out=root/'domain/NMRShiftDB2'/a.attempt;out.mkdir(parents=True,exist_ok=False)
    reference=json.loads(a.reference_manifest.read_text())
    source=root/'raw/NMRShiftDB2_Jonas2019/13321_2019_374_MOESM2_ESM.gz'
    members={}
    with tarfile.open(source,'r:gz') as archive:
        for member in archive:
            if member.name.endswith('.pickle'):
                nucleus='13C' if '.13C.' in member.name else '1H'
                members[nucleus]=(member.name,graph_lookup(restricted_graph_load(archive.extractfile(member).read())))
    combined={}
    for nucleus,(member,graphs) in members.items():
        for mid,(mol,splits) in graphs.items():
            if mid in combined and Chem.MolToSmiles(combined[mid][0],canonical=False,isomericSmiles=True,allHsExplicit=True)!=Chem.MolToSmiles(mol,canonical=False,isomericSmiles=True,allHsExplicit=True):
                raise ValueError('Nucleus-specific original graph definitions differ for one molecule ID')
            combined.setdefault(mid,(mol,[]))[1].append({'member':member,'original_splits':splits})
    counts=[];pending=[]
    for ref in reference['records']:
        nucleus=ref['nucleus'];graphs=combined
        reasons=Counter();primary=Counter();before=eligible=missing=sequence_mismatch=0
        target=out/('carbon.parquet' if nucleus=='13C' else 'hydrogen.parquet')
        with pq.ParquetWriter(target,SCHEMA,compression='zstd') as writer:
            for batch in pq.ParquetFile(ref['reference']).iter_batches(batch_size=256,
                    columns=['molecule_id','source_row','atomic_numbers']):
                rows=[]
                for row in batch.to_pylist():
                    before+=1;ids=json.loads(row['molecule_id'])
                    if len(ids)!=1:raise ValueError('Reference does not declare one original molecule ID')
                    mid=int(ids[0]);rid='NMRShiftDB2:'+nucleus+':'+str(mid)+':row:'+str(row['source_row'])
                    if mid not in graphs:
                        missing+=1;pending.append({'record_id':rid,'reason':'ORIGINAL_GRAPH_ID_MISSING'});continue
                    mol,original_provenance=graphs[mid]
                    smiles=Chem.MolToSmiles(mol,canonical=False,isomericSmiles=True,allHsExplicit=True)
                    domain=assess(smiles)
                    source_order=[int(x) for x in __import__('ast').literal_eval(mol.GetProp('_smilesAtomOutputOrder'))]
                    atom_map=[source_order[i] for i in domain['model_atom_to_source']]
                    compatible=[at.GetAtomicNum() for at in mol.GetAtoms()]==row['atomic_numbers']
                    sequence_mismatch+=not compatible
                    eligible+=domain['domain_eligible'];reasons.update(domain['reasons'])
                    if domain['reasons']:primary[domain['reasons'][0]]+=1
                    rows.append({'dataset':'NMRShiftDB2_'+nucleus,'source_file':ref['reference'],
                        'source_row':row['source_row'],'record_id':rid,'original_smiles':smiles,
                        'model_smiles':domain['model_smiles'],'model_atom_to_source':atom_map,
                        'heavy_atoms':domain['heavy_atoms'],'charge':domain['charge'],'salt_removed':False,
                        'domain_eligible':domain['domain_eligible'],'retained':domain['retained'],
                        'blind_fallback_required':False,'exclusion_reasons':domain['reasons'],'official_split':None,
                        'original_fields_json':json.dumps({'original_molecule_id':mid,
                            'original_Jonas_provenance':original_provenance,'original_graph_molblock':Chem.MolToMolBlock(mol),
                            'model_atom_to_source_basis':'Original Jonas RDKit graph atom indices',
                            'reference_element_sequence_compatible':compatible,
                            'graph_to_reference_atom_binding':'PENDING_AUTHOR_INDEX_LINEAGE; no atom permutation inferred',
                            'reference_geometry_regenerated':False,'final_split_selected':False})})
                safe(268435456)
                if rows:writer.write_table(pa.Table.from_pylist(rows,schema=SCHEMA))
        counts.append({'nucleus':nucleus,'before':before,'graph_bound':before-missing,'domain_eligible':eligible,
            'retained':eligible,'graph_missing':missing,'reference_element_sequence_mismatches':sequence_mismatch,
            'reason_counts_nonexclusive':dict(reasons),'primary_reason_counts':dict(primary),'records':str(target)})
        print('NMR_GRAPH_DOMAIN_CLOSED',nucleus,counts[-1],flush=True)
    report={'dataset':'NMRShiftDB2','status':'DOMAIN_READY_ATOM_INDEX_LINEAGE_PENDING' if not pending else 'PARTIAL_GRAPH_BINDING',
        'counts':counts,'source_graph_archive':str(source),'reference_manifest':str(a.reference_manifest),
        'unresolved_records':pending,'domain_filter_complete':not pending,'reference_geometries_regenerated':False,
        'atom_level_P_D_ready':False,'split_decision':'PENDING_USER; source train/test retained as provenance only',
        'multiplicity_basis':'Closed-shell original RDKit graph, same frozen domain policy',
        'independent_numeric_readback':False,'reference_columns_read':['molecule_id','source_row','atomic_numbers']}
    safe(1048576);(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
