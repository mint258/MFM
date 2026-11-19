"""Export original NMR2018 atom labels and author splits for shared UFF preparation."""
import argparse
import ast
from collections import Counter
import json
import math
from pathlib import Path
import tarfile
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem
from .build_csv_domain import SCHEMA as DOMAIN_SCHEMA
from .domain import assess
from .nmr_graph_source import restricted_graph_load
from .pprime_tmpfs_queue import capacity

SCHEMA=pa.schema(list(DOMAIN_SCHEMA)+[
    ('original_molecule_id',pa.int64()),('source_frame_index',pa.string()),
    ('source_atomic_numbers',pa.list_(pa.int16())),
    ('target_source_atom_ids',pa.list_(pa.int32())),
    ('target_group_indices',pa.list_(pa.int16())),
    ('target_values_ppm',pa.list_(pa.float64())),
    ('target_valid',pa.list_(pa.bool_()))])

def labels(mol,groups,nucleus):
    expected={'13C':6,'1H':1}[nucleus]
    if not isinstance(groups,(list,tuple)):
        raise ValueError('Original value must preserve its spectrum-group list')
    ids=[];indices=[];values=[];valid=[]
    for group_index,group in enumerate(groups):
        if not isinstance(group,dict):
            raise ValueError('Original spectrum group is not an atom-value dictionary')
        for raw_id,value in group.items():
            atom_id=int(raw_id)
            if atom_id!=raw_id or not 0<=atom_id<mol.GetNumAtoms():
                raise ValueError('Original target atom identity is invalid')
            if mol.GetAtomWithIdx(atom_id).GetAtomicNum()!=expected:
                raise ValueError('Original target atom does not match the nucleus')
            numeric=float(value)
            ids.append(atom_id);indices.append(group_index)
            values.append(numeric);valid.append(math.isfinite(numeric))
    return dict(target_source_atom_ids=ids,target_group_indices=indices,
                target_values_ppm=values,target_valid=valid)

def source_record(nucleus,split,pos,index,row,member,source):
    mol=row['rdmol']
    smiles=Chem.MolToSmiles(mol,canonical=False,isomericSmiles=True,allHsExplicit=True)
    order=ast.literal_eval(mol.GetProp('_smilesAtomOutputOrder'))
    domain=assess(smiles)
    atom_map=[order[i] for i in domain['model_atom_to_source']]
    mid=int(row['molecule_id'])
    return dict(dataset='NMRShiftDB2_'+nucleus,source_file=str(source),source_row=pos,
        record_id='NMRShiftDB2:2018:'+nucleus+':'+split+':row:'+str(pos),
        original_smiles=smiles,model_smiles=domain['model_smiles'],
        model_atom_to_source=atom_map,heavy_atoms=domain['heavy_atoms'],charge=domain['charge'],
        salt_removed=False,domain_eligible=domain['domain_eligible'],retained=domain['retained'],
        blind_fallback_required=False,exclusion_reasons=domain['reasons'],official_split=split,
        original_fields_json=json.dumps(dict(original_molecule_id=mid,archive_member=member,
            source_frame_index=str(index),spectra_ids=list(map(int,row['spectra_ids'])),
            original_graph_molblock=Chem.MolToMolBlock(mol),
            target_atom_basis='Original author RDKit graph atom indices; explicit H retained',
            target_units='ppm',split_reconstructed=False,
            downstream_geometry='Shared Sprime UFF only; author embedded coordinates are provenance')),
        original_molecule_id=mid,source_frame_index=str(index),
        source_atomic_numbers=[a.GetAtomicNum() for a in mol.GetAtoms()],
        **labels(mol,row['value'],nucleus))

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--attempt',required=True)
    p.add_argument('--quota-snapshot',type=Path,required=True)
    a=p.parse_args()
    def safe():capacity(a.root,a.quota_snapshot,needed=536870912)
    safe();out=a.root/'directive19/NMR2018'/a.attempt
    out.mkdir(parents=True,exist_ok=False)
    source=a.root/'raw/NMRShiftDB2_Jonas2019/13321_2019_374_MOESM2_ESM.gz'
    counts=[];seen=set();split_counts=[]
    pa.set_cpu_count(1)
    with pq.ParquetWriter(out/'all_rows.parquet',SCHEMA,compression='zstd') as writer:
        with tarfile.open(source,'r:gz') as archive:
            for member in archive:
                if not member.name.endswith('.pickle'):continue
                nucleus='13C' if '.13C.' in member.name else '1H' if '.1H.' in member.name else None
                if nucleus is None or nucleus in seen:raise ValueError('Unexpected author graph member')
                seen.add(nucleus)
                data=restricted_graph_load(archive.extractfile(member).read())
                total=Counter();reasons=Counter();primary=Counter()
                for split in ('train','test'):
                    frame=data[split+'_df'];unique=set();local=Counter();buffer=[]
                    for pos,(index,row) in enumerate(frame.iterrows()):
                        record=source_record(nucleus,split,pos,index,row,member.name,source)
                        unique.add(record['original_molecule_id'])
                        local['source_rows']+=1
                        local['domain_eligible']+=record['domain_eligible']
                        local['atom_targets']+=len(record['target_values_ppm'])
                        local['finite_atom_targets']+=sum(record['target_valid'])
                        reasons.update(record['exclusion_reasons'])
                        if record['exclusion_reasons']:primary[record['exclusion_reasons'][0]]+=1
                        buffer.append(record)
                        if len(buffer)>=256:
                            safe();writer.write_table(pa.Table.from_pylist(buffer,schema=SCHEMA));buffer=[]
                    if buffer:
                        safe();writer.write_table(pa.Table.from_pylist(buffer,schema=SCHEMA))
                    split_counts.append(dict(nucleus=nucleus,official_split=split,
                        unique_molecule_ids=len(unique),**local))
                    total.update(local)
                    print('NMR2018_TARGET_SPLIT_CLOSED',nucleus,split,dict(local),flush=True)
                counts.append(dict(nucleus=nucleus,before=total['source_rows'],
                    domain_eligible=total['domain_eligible'],retained=total['domain_eligible'],
                    atom_targets=total['atom_targets'],finite_atom_targets=total['finite_atom_targets'],
                    reason_counts_nonexclusive=dict(reasons),primary_reason_counts=dict(primary)))
                del data
    if seen!={'13C','1H'}:raise ValueError('Both author nuclei required')
    result=dict(status='ORIGINAL_NMR2018_TARGETS_AND_DOMAIN_READY_UFF_PENDING',
        dataset='NMRShiftDB2',source=str(source),records=str(out/'all_rows.parquet'),
        counts=counts,source_split_counts=split_counts,domain_filter_complete=True,
        original_author_split_preserved=True,reconstructed_split=False,
        source_rows_reassigned=False,source_atom_indices_preserved=True,
        source_duplicate_spectra_rows_preserved=True,target_values_exported=True,
        target_units='ppm',geometry_source='UFF_Sprime_REQUIRED_NOT_YET_GENERATED',
        author_coordinates_used_for_downstream=False,UFF_geometry_ready=False,
        published_test_unique_molecule_count_reconciliation='PENDING; spectra rows and unique IDs reported separately',
        previous_split_membership_manifest=str(a.root/'directive19/NMR2018/job_4536853/manifest.json'),
        independent_numeric_readback=False,new_data_content_hashes=False)
    safe();(out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print('NMR2018_TARGETS_CLOSED',out/'manifest.json',flush=True)

if __name__=='__main__':main()
