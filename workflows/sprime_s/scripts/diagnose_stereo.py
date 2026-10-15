"""Bounded diagnosis of pilot stereo flags using original native records."""
import concurrent.futures as cf,json,multiprocessing as mp,os
from pathlib import Path
from prepare import ROOT,save
from sprime_pilot_v2 import read,graph,worker_init,field,plain

def diagnose(task):
    from rdkit import Chem
    meta,rows=task
    lowest=min(rows,key=lambda r:(float(r['energy_raw']) if r['energy_raw'] is not None else float('inf'),r['record_id']))
    raw=read(lowest);mol,z,xyz=graph(raw);smiles=str(field(raw,'smiles'))
    template=Chem.AddHs(Chem.MolFromSmiles(smiles));Chem.AssignStereochemistry(template,cleanIt=True,force=True)
    match=mol.GetSubstructMatch(template,useChirality=False)
    Chem.AssignStereochemistryFrom3D(mol,confId=0,replaceExistingTags=True)
    before=Chem.MolToSmiles(Chem.RemoveHs(Chem.Mol(mol)),isomericSmiles=True)
    copied=[]
    if match:
        for atom in template.GetAtoms():
            if atom.GetChiralTag()==Chem.ChiralType.CHI_UNSPECIFIED:continue
            target=mol.GetAtomWithIdx(match[atom.GetIdx()])
            query_order=[match[a.GetIdx()] for a in atom.GetNeighbors()]
            target_order=[a.GetIdx() for a in target.GetNeighbors()]
            permutation=[target_order.index(i) for i in query_order]
            inversions=sum(permutation[i]>permutation[j] for i in range(len(permutation)) for j in range(i+1,len(permutation)))
            target.SetChiralTag(atom.GetChiralTag())
            if inversions%2:target.InvertChirality()
            copied.append({'index':target.GetIdx(),'query_neighbors':query_order,'target_neighbors':target_order,'inversions':inversions,'query_CIP':atom.GetProp('_CIPCode') if atom.HasProp('_CIPCode') else None})
    Chem.AssignStereochemistry(mol,cleanIt=False,force=True)
    potential=[{'type':str(x.type),'centered_on':x.centeredOn,'specified':str(x.specified),'descriptor':str(x.descriptor),'controlling_atoms':list(x.controllingAtoms)} for x in Chem.FindPotentialStereo(mol)]
    return {'molecule_id':meta['molecule_id'],'pilot_status':meta['status'],'source_smiles':smiles,'geometry_signature':before,'parity_copied_signature':Chem.MolToSmiles(Chem.RemoveHs(Chem.Mol(mol)),isomericSmiles=True),'template_chirality_match_after_parity':bool(mol.GetSubstructMatch(template,useChirality=True)),'copied':copied,'potential_stereo':potential}

def main():
    assert os.environ.get('SLURM_JOB_ID')
    import pyarrow.parquet as pq
    m=pq.read_table(ROOT/'pilot/molecules_group1.parquet').to_pylist()
    m=[r for r in m if r['status'] in {'SMILES_STEREO_UNRESOLVED','PM7_STEREO_UNRESOLVED'}][:32]
    columns=['molecule_id','record_id','source_path','real_index','record_payload_sha256','total_atoms','energy_raw']
    rows=pq.read_table(ROOT/'prepared/pilot_records.parquet',columns=columns,filters=[('file_group','=',1)]).to_pylist()
    indexed={r['molecule_id']:[] for r in m}
    for r in rows:
        if r['molecule_id'] in indexed:indexed[r['molecule_id']].append(r)
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=worker_init) as pool:
        results=list(pool.map(diagnose,[(meta,indexed[meta['molecule_id']]) for meta in m]))
    save(ROOT/'reports/stereo_diagnosis.json',results)
    print(json.dumps({'cases':len(results),'parity_chirality_matches':sum(r['template_chirality_match_after_parity'] for r in results)}))

if __name__=='__main__':main()
