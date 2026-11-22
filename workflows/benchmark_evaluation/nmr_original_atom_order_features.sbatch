sbatch --parsable <<'NMRFEATURESREPAIR'
#!/bin/bash
#SBATCH --job-name=B1-NMR-original-atom-order-repair
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=04:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_NMR_native_atom_order_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'

import json,math,os,tarfile,unittest
from pathlib import Path
from collections import Counter
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem,DataStructs,rdBase,RDLogger
from rdkit.Chem import Descriptors,rdFingerprintGenerator
from workflows.benchmark_data.admission import protect
from workflows.benchmark_data.domain import assess
from workflows.benchmark_data.nmr_graph_source import restricted_graph_load
RDLogger.DisableLog('rdApp.error')
GENERATOR=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048,includeChirality=False)
DESCRIPTORS=list(Descriptors._descList)
ELEMENTS=(1,6,8,7,15,16,9,17)
HYBRIDS=(Chem.HybridizationType.S,Chem.HybridizationType.SP,Chem.HybridizationType.SP2,Chem.HybridizationType.SP3,Chem.HybridizationType.SP3D,Chem.HybridizationType.SP3D2)
ATOM_NAMES=['atomic_number']+['element_'+str(z) for z in ELEMENTS]+['total_valence']+['valence_'+str(v) for v in range(1,7)]+['aromatic']+['hybridization_'+str(v) for v in HYBRIDS]+['formal_charge_'+str(v) for v in (-1,0,1)]+['default_valence_'+str(v) for v in range(1,7)]+['in_ring_'+str(v) for v in range(3,8)]
def initialize_native_graph(mol):
    # Old RDKit pickles omit computed ring/property caches; initialize caches only.
    mol.UpdatePropertyCache(strict=False)
    Chem.GetSymmSSSR(mol)
    return mol
def atom_features(atom):
    z=atom.GetAtomicNum();valence=atom.GetTotalValence();hybrid=atom.GetHybridization();charge=atom.GetFormalCharge();default=Chem.GetPeriodicTable().GetDefaultValence(z)
    return [float(z)]+[float(z==v) for v in ELEMENTS]+[float(valence)]+[float(valence==v) for v in range(1,7)]+[float(atom.GetIsAromatic())]+[float(hybrid==v) for v in HYBRIDS]+[float(charge==v) for v in (-1,0,1)]+[float(default==v) for v in range(1,7)]+[float(atom.IsInRingSize(v)) for v in range(3,8)]
def targets(value,mol,nucleus):
    if not isinstance(value,list) or len(value)!=1 or not isinstance(value[0],dict):raise ValueError('Unexpected original single-nucleus label container')
    expected=6 if nucleus=='13C' else 1
    result=[];missing=0
    for original_index,value in sorted(value[0].items()):
        index=int(original_index)
        if index!=original_index or not 0<=index<mol.GetNumAtoms():raise ValueError('Original atom label index is not bound to its native graph')
        if mol.GetAtomWithIdx(index).GetAtomicNum()!=expected:raise ValueError('Original atom/nucleus label mismatch')
        try:y=float(value)
        except (ValueError,TypeError):missing+=1;continue
        if not math.isfinite(y):missing+=1;continue
        result.append((index,y))
    return result,missing
def descriptors(mol):
    output=[]
    for _,function in DESCRIPTORS:
        try:value=float(function(mol))
        except Exception:value=float('nan')
        output.append(value if math.isfinite(value) else float('nan'))
    return output
class AtomBindingTests(unittest.TestCase):
    def test_equal_SMILES_cannot_alias_different_original_atom_orders(self):
        first=Chem.AddHs(Chem.MolFromSmiles('CCCCO'))
        order=list(range(first.GetNumAtoms()));order[3],order[4]=order[4],order[3]
        second=Chem.RenumberAtoms(first,order)
        first_text=Chem.MolToSmiles(first,canonical=False,isomericSmiles=True,allHsExplicit=True)
        second_text=Chem.MolToSmiles(second,canonical=False,isomericSmiles=True,allHsExplicit=True)
        self.assertEqual(first_text,second_text)
        self.assertNotEqual(first.ToBinary(),second.ToBinary())
        self.assertNotEqual(first.GetAtomWithIdx(3).GetAtomicNum(),second.GetAtomWithIdx(3).GetAtomicNum())
        exact={first.ToBinary():[a.GetAtomicNum() for a in first.GetAtoms()],
               second.ToBinary():[a.GetAtomicNum() for a in second.GetAtoms()]}
        self.assertEqual(len(exact),2)
        self.assertEqual(exact[second.ToBinary()][3],second.GetAtomWithIdx(3).GetAtomicNum())

    def test_old_graph_ring_cache_initialization_preserves_native_indices(self):
        mol=Chem.MolFromSmiles('C1CCCCC1',sanitize=False)
        before=[(a.GetIdx(),a.GetAtomicNum(),a.GetFormalCharge()) for a in mol.GetAtoms()]
        edges=[(b.GetBeginAtomIdx(),b.GetEndAtomIdx(),str(b.GetBondType())) for b in mol.GetBonds()]
        initialize_native_graph(mol)
        self.assertEqual(before,[(a.GetIdx(),a.GetAtomicNum(),a.GetFormalCharge()) for a in mol.GetAtoms()])
        self.assertEqual(edges,[(b.GetBeginAtomIdx(),b.GetEndAtomIdx(),str(b.GetBondType())) for b in mol.GetBonds()])
        self.assertEqual(len(DataStructs.BitVectToBinaryText(GENERATOR.GetFingerprint(mol,fromAtoms=[0]))),256)
    def test_atom_feature_definition_matches_published_37_columns(self):
        mol=Chem.AddHs(Chem.MolFromSmiles('CCO'))
        self.assertEqual(len(ATOM_NAMES),37)
        self.assertTrue(all(len(atom_features(atom))==37 for atom in mol.GetAtoms()))
    def test_hydrogen_indices_are_native_explicit_hydrogens(self):
        mol=Chem.AddHs(Chem.MolFromSmiles('CCO'));index=next(a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum()==1)
        self.assertEqual(targets([{index:1.25}],mol,'1H')[0],[(index,1.25)])
    def test_wrong_nucleus_or_index_is_not_guessed(self):
        mol=Chem.AddHs(Chem.MolFromSmiles('CCO'))
        with self.assertRaises(ValueError):targets([{0:1.}],mol,'1H')
        with self.assertRaises(ValueError):targets([{999:1.}],mol,'13C')
    def test_missing_atomic_labels_are_not_zero_filled(self):
        mol=Chem.AddHs(Chem.MolFromSmiles('CCO'))
        self.assertEqual(targets([{0:float('nan'),1:2.}],mol,'13C'),([(1,2.)],1))
    def test_atom_centered_ECFP4_is_2048_bits(self):
        mol=Chem.AddHs(Chem.MolFromSmiles('CCO'))
        packed=DataStructs.BitVectToBinaryText(GENERATOR.GetFingerprint(mol,fromAtoms=[0]))
        self.assertEqual(len(packed),256)
    def test_multiple_label_channels_are_not_merged(self):
        with self.assertRaises(ValueError):targets([{},{}],Chem.MolFromSmiles('CCC'),'13C')
tests=unittest.defaultTestLoader.loadTestsFromTestCase(AtomBindingTests)
if not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,2*1024**3,quota,own_concurrent_bytes=24*1024**3)
safe();out=b1/'B1_NMR_features_native_order'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
proof_path=b1/'endpoint_catalog/job_4536889/manifest.json';proof=json.loads(proof_path.read_text());assert proof['deferred_registry_full_inventory_verified']
split_path=b1/'nmr_split/job_4536856/split_metadata.json';split_metadata=json.loads(split_path.read_text())
source=root/'raw/NMRShiftDB2_Jonas2019/13321_2019_374_MOESM2_ESM.gz'
atom_schema=pa.struct([('original_atom_index',pa.int32()),('y',pa.float64()),('ecfp4_2048_packed',pa.binary()),('rdkit_atom37',pa.list_(pa.float64()))])
schema=pa.schema([('dataset',pa.string()),('nucleus',pa.string()),('source_member',pa.string()),('official_split',pa.string()),('source_position',pa.int64()),('original_molecule_id',pa.int64()),('record_id',pa.string()),('full_inchikey',pa.string()),('original_mol_binary',pa.binary()),('original_smiles',pa.string()),('model_smiles',pa.string()),('retained',pa.bool_()),('domain_eligible',pa.bool_()),('exclusion_reasons',pa.list_(pa.string())),('rdkit_2d',pa.list_(pa.float64())),('atoms',pa.list_(atom_schema))])
cache={};reports=[]
with tarfile.open(source,'r:gz') as archive:
    for member in archive:
        if not member.name.endswith('.pickle'):continue
        nucleus='13C' if '.13C.' in member.name else '1H'
        if not split_metadata['nuclei'][nucleus]['published_test_entry_count_matches']:raise ValueError('Original published split has not passed the single required count check')
        data=restricted_graph_load(archive.extractfile(member).read());counts=Counter();target=out/(nucleus+'.parquet')
        with pq.ParquetWriter(target,schema,compression='zstd') as writer:
            buffer=[]
            for split_name in ('train_df','test_df'):
                split='train' if split_name=='train_df' else 'test'
                for position,(mid,mol,value) in enumerate(data[split_name][['molecule_id','rdmol','value']].itertuples(index=False,name=None)):
                    initialize_native_graph(mol)
                    counts[split+'_original_spectrum_rows']+=1
                    labels,missing=targets(value,mol,nucleus);counts['missing_atomic_labels']+=missing
                    original_smiles=Chem.MolToSmiles(mol,canonical=False,isomericSmiles=True,allHsExplicit=True)
                    native_binary=mol.ToBinary();cache_key=native_binary
                    if cache_key not in cache:
                        domain=assess(original_smiles)
                        key=Chem.MolToInchiKey(mol)
                        atom_values={index:{'ecfp4_2048_packed':DataStructs.BitVectToBinaryText(GENERATOR.GetFingerprint(mol,fromAtoms=[index])),'rdkit_atom37':atom_features(mol.GetAtomWithIdx(index))} for index in range(mol.GetNumAtoms())}
                        cache[cache_key]=(domain,key,descriptors(mol),atom_values)
                    domain,key,rdkit2d,atom_values=cache[cache_key];binary=native_binary
                    if not key:raise ValueError('Original NMR graph lacks a full molecular InChIKey')
                    counts[split+'_labeled_atom_points']+=len(labels)
                    counts[split+('_retained_atom_points' if domain['domain_eligible'] else '_excluded_atom_points')]+=len(labels)
                    atoms=[dict(original_atom_index=index,y=y,**atom_values[index]) for index,y in labels]
                    buffer.append({'dataset':'NMRShiftDB2_'+nucleus,'nucleus':nucleus,'source_member':member.name,'official_split':split,'source_position':position,'original_molecule_id':int(mid),'record_id':'NMR2018:'+nucleus+':'+split+':row:'+str(position),'full_inchikey':key,'original_mol_binary':binary,'original_smiles':original_smiles,'model_smiles':domain['model_smiles'],'retained':domain['retained'],'domain_eligible':domain['domain_eligible'],'exclusion_reasons':domain['reasons'],'rdkit_2d':rdkit2d,'atoms':atoms})
                    if len(buffer)>=256:
                        safe();writer.write_table(pa.Table.from_pylist(buffer,schema=schema));buffer.clear()
                print('NMR_ORIGINAL_ATOM_FEATURE_SPLIT_WRITTEN',nucleus,split,counts[split+'_original_spectrum_rows'],'spectrum_rows',flush=True)
            if buffer:safe();writer.write_table(pa.Table.from_pylist(buffer,schema=schema))
        reports.append({'nucleus':nucleus,'records':str(target),'counts':dict(counts)})
        print('NMR_ORIGINAL_ATOM_FEATURE_SOURCE_CLOSED',nucleus,json.dumps(dict(counts)),flush=True)
report={'status':'ORIGINAL_NMR2018_ATOM_FEATURES_CLOSED','job':os.environ['SLURM_JOB_ID'],'repairs_failed_feature_producer_job':4536984,'actual_consumer_error_job':4537205,'cache_key':'Exact original native Mol binary; never SMILES for atom-indexed features','graph_cache_repair':'UpdatePropertyCache(strict=False) and GetSymmSSSR only; no atom or bond permutation, no geometry generation','source_entry':str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),'source_archive':str(source),'full_inventory_scope_proof':str(proof_path),'original_split_metadata':str(split_path),'source_groups':reports,'unit_tests':tests.countTestCases(),'rdkit_version':rdBase.rdkitVersion,'rdkit_2d_names':[name for name,_ in DESCRIPTORS],'rdkit_atom37_names':ATOM_NAMES,'atom_feature_reference':'Jonas & Kuhn 2019 Table 1; original native graph atom order and explicit hydrogens','RF_atom_features':'Atom-centered Morgan radius2 2048bit fromAtoms=[original_atom_index], includeChirality=False, native explicit-H graph','LightGBM_atom_features':'Original-graph RDKit2D globals concatenated with published 37 RDKit atom features','Chemprop_graph_interface':'Use original_mol_binary and original_atom_index; no SMILES reparsing or atom-index permutation','original_experimental_values_modified':False,'spectra_not_averaged_or_deduplicated':True,'new_geometries_generated':False,'model_fits_run':False,'B1_task_screen_produced':False,'independent_numeric_readback':False,'C1_atomic_Pprime_native_feature_binding_still_required':True}
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('NMR_ORIGINAL_ATOM_FEATURE_MANIFEST',out/'manifest.json',flush=True)

PY
NMRFEATURESREPAIR
