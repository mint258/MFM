"""Generate common ETKDG/UFF benchmark inputs; retain every declared member."""
from __future__ import annotations
import argparse,csv,hashlib,io,json,math,multiprocessing as mp,os,re,time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha

BENCH=Path('/share/home/zixiao/benchmark_dataset')
EXP=PROJECT/'data/OpenADMET_ExpansionRx_MLQSAR_paper_reproduction'
GRAPH_TASKS={'qm7':['target_atomization_energy'],'qm9':['A','B','C','mu','alpha','homo','lumo','gap','r2','zpve','U0','U','H','G','Cv'],
 'expansionrx':['LogD','LogS','Log_HLM_CLint','Log_MLM_CLint','Log_Caco_Papp_AB','Log_Caco_ER','Log_Mouse_PPB','Log_Mouse_BPB','Log_Mouse_MPB']}
ISOFORMS=['1A2','2A6','2B6','2C19','2C8','2C9','2D6','2E1','3A4']

def init_worker():
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1)

def finite_label(value):
    try:number=float(value)
    except (TypeError,ValueError):return None
    return number if math.isfinite(number) else None

def primary_field(frame):
    lines=frame.splitlines();values=[]
    for index,line in enumerate(lines):
        if re.fullmatch(rb'>[^\r\n]*<PRIMARY_SOM>[^\r\n]*',line):
            block=[]
            for item in lines[index+1:]:
                if not item.strip():break
                if item.startswith(b'>') or item==b'$$$$':raise ValueError('Malformed PRIMARY_SOM property')
                block.append(item)
            values.append(b'\n'.join(block).decode('ascii'))
    if len(values)>1:raise ValueError('Duplicate PRIMARY_SOM property')
    return values[0] if values else None

def generate(job):
    import numpy as np,torch
    from rdkit import Chem,rdBase
    from rdkit.Chem import AllChem,rdtrajectory
    from phychem_mfm.phase1.downstream_structures import read_cyp_mol_block,read_az_raw_smiles
    from phychem_mfm.phase1.generated_geometry import _graph,_specified_stereo
    from phychem_mfm.phase1.som_atom_mapping import build_cyp_author_atom_mapping
    from phychem_mfm.phase1.som_annotation import decode_cyp_primary_annotation
    from phychem_mfm.phase1.az_atom_mapping import build_az_author_atom_mapping
    from phychem_mfm.phase1.az_annotation import parse_az_exact_groups
    started=time.monotonic();dataset=job['dataset'];row=job['row']
    result={'dataset':dataset,'record_id':job['record_id'],'member_order':job['member_order'],'fold':int(row['fold']),
        'geometry_status':'UNPROCESSED','annotation_status':'UNKNOWN','coordinates':None,
        'atomic_numbers':None,'targets':None,'candidate_mask':None,'supervision_mask':None,
        'inchikey14':None,'seed':None,'uff_energy_kcal_mol':None,'uff_iterations':None,'uff_converged':False,
        'source_ref':job['source_ref'],'source_record_sha256':job['source_record_sha256'],'source_parent_sha256':job['source_parent_sha256'],
        'native_layout':job['native_layout'],'rdkit_version':rdBase.rdkitVersion,'error':None}
    try:
        if dataset=='cyp_isoform':
            structure=read_cyp_mol_block(job['mol_block']);mol=structure.mol
        elif dataset=='az_exactsom':
            structure=read_az_raw_smiles(job['raw_smiles']);mol=structure.mol
        else:
            mol=Chem.MolFromSmiles(row['SMILES']);assert mol is not None
            mol=Chem.AddHs(mol);structure=None
        n=mol.GetNumAtoms();numbers=[atom.GetAtomicNum() for atom in mol.GetAtoms()]
        assert 0<n<=256 and all(1<=z<=118 for z in numbers)
        result['atomic_numbers']=numbers
        with rdBase.BlockLogs():result['inchikey14']=Chem.MolToInchiKey(mol)[:14]
        if dataset in GRAPH_TASKS:
            labels=[finite_label(row.get(t)) for t in GRAPH_TASKS[dataset]]
            result.update(targets=labels,candidate_mask=[True]*len(labels),supervision_mask=[v is not None for v in labels],annotation_status='SOURCE_GRAPH_TARGETS')
        elif dataset=='cyp_isoform':
            author=next(Chem.ForwardSDMolSupplier(io.BytesIO(job['raw_frame']),sanitize=True),None)
            assert author is not None
            assert author.GetNumAtoms()==int(row['n_atoms']),'LEGACY_MEMBER_AUTHOR_ATOM_COUNT_MISMATCH'
            legacy=Chem.MolFromMolBlock(row['mol_block'],sanitize=True,removeHs=True)
            assert legacy is not None and Chem.MolToSmiles(legacy)==Chem.MolToSmiles(author),'MEMBER_RAW_SOURCE_GRAPH_MISMATCH'
            mapping=build_cyp_author_atom_mapping(mol,author,source_file=Path(job['source_ref']).name,
                source_file_sha256=job['source_parent_sha256'],source_record_1based=job['source_ordinal'],
                source_block_sha256=hashlib.sha256(job['mol_block'].encode()).hexdigest())
            labels=np.full((n,9),np.nan);candidate=np.zeros((n,9),bool);supervision=np.zeros((n,9),bool)
            iso=ISOFORMS.index(row['isoform']);primary=primary_field(job['raw_frame'])
            annotation=decode_cyp_primary_annotation(primary if primary is not None else '',mapping,isoform=row['isoform'],empty_policy='preserve_unknown')
            labels[:,iso]=[np.nan if value is None else value for value in annotation.labels]
            candidate[:,iso]=annotation.candidate_mask;supervision[:,iso]=annotation.supervision_mask
            result['annotation_status']=annotation.provenance['annotation_state'] if primary is not None else 'MISSING_PRIMARY_UNKNOWN'
            result.update(targets=[None if not np.isfinite(v) else float(v) for v in labels.ravel()],
                          candidate_mask=candidate.ravel().tolist(),supervision_mask=supervision.ravel().tolist())
        else:
            mapping=build_az_author_atom_mapping(mol,job['raw_smiles'],source_file=Path(job['source_ref']).name,
                source_file_sha256=job['source_parent_sha256'],source_record_1based=job['source_ordinal'],
                raw_frame_sha256=job['source_record_sha256'],source_smiles_sha256=hashlib.sha256(job['raw_smiles'].encode()).hexdigest())
            annotation=parse_az_exact_groups(job['groups'],job['flags'],n_author_atoms=len(mapping.author_to_native))
            labels=[None]*n;supervision=[False]*n
            if annotation.exact_author_ids:
                labels=[0.]*n;supervision=[True]*n
                for index in annotation.exact_author_ids:labels[mapping.author_to_native[index]]=1.
            result.update(targets=labels,candidate_mask=[True]*n,supervision_mask=supervision,
                annotation_status=annotation.annotation_state)
        original=mol.ToBinary(Chem.PropertyPickleOptions.AllProps)
        native_graph=_graph(mol);scratch=Chem.Mol(mol);scratch.RemoveAllConformers();scratch=Chem.AddHs(scratch)
        assert scratch.GetNumAtoms()<=512 and _graph(scratch,n)==native_graph
        assert len(Chem.GetMolFrags(scratch))==1,'UNSUPPORTED_DISCONNECTED_GEOMETRY'
        material=json.dumps({'recipe':'s_convergence_ETKDGv3_UFF_native_v1','graph':native_graph},sort_keys=True,separators=(',',':')).encode()
        seed=1+int(hashlib.sha256(material).hexdigest()[:8],16)%(2**31-2);result['seed']=seed
        parameters=AllChem.ETKDGv3();parameters.randomSeed=seed;parameters.numThreads=1
        parameters.maxIterations=200;parameters.timeout=2;parameters.enforceChirality=True
        with rdBase.BlockLogs():conf=AllChem.EmbedMolecule(scratch,parameters)
        if conf<0:result['geometry_status']='EMBED_FAILED';return result
        if not AllChem.UFFHasAllMoleculeParams(scratch):result['geometry_status']='UFF_UNSUPPORTED';return result
        with rdBase.BlockLogs():
            field=AllChem.UFFGetMoleculeForceField(scratch,vdwThresh=100.,confId=conf,ignoreInterfragInteractions=True)
            code,trajectory=field.MinimizeTrajectory(snapshotFreq=1,maxIts=500,forceTol=1e-4,energyTol=1e-6)
        result.update(uff_iterations=len(trajectory),uff_converged=code==0,uff_energy_kcal_mol=float(field.CalcEnergy()))
        if code:result['geometry_status']='UFF_NONCONVERGED';return result
        assert _graph(scratch,n)==native_graph
        _specified_stereo(scratch,scratch,n,conf)
        positions=np.array(scratch.GetConformer(conf).GetPositions()[:n],dtype=np.float64)
        assert positions.shape==(n,3) and np.all(np.isfinite(positions))
        assert mol.ToBinary(Chem.PropertyPickleOptions.AllProps)==original
        result.update(geometry_status='GEOMETRY_READY',coordinates=positions.ravel().tolist())
    except Exception as exc:
        result.update(geometry_status='SOURCE_OR_GEOMETRY_FLAGGED',error=repr(exc))
    finally:result['elapsed_seconds']=time.monotonic()-started
    return result

def declared_jobs(dataset):
    from phychem_mfm.phase1.az_annotation import GROUP_COLUMN,FLAG_COLUMN
    if dataset=='expansionrx':
        paths=[EXP/'log_train_data.csv',EXP/'official_test.csv'];rows=[]
        for path in paths:
            parent_sha=sha(path)
            with path.open(newline='') as stream:
                for ordinal,row in enumerate(csv.DictReader(stream),1):
                    rows.append({'row':row,'record_id':dataset+':'+path.name+':'+str(ordinal),
                        'source_ref':str(path),'source_parent_sha256':parent_sha})
        # A new scaffold assignment is required because the guide overrides the official split.
        from rdkit import Chem
        from rdkit.Chem.Scaffolds import MurckoScaffold
        groups={}
        for item in rows:
            mol=Chem.MolFromSmiles(item['row']['SMILES'])
            key=MurckoScaffold.MurckoScaffoldSmiles(mol=mol,includeChirality=False) if mol else 'INVALID:'+item['record_id']
            if not key and mol:key='ACYCLIC:'+Chem.MolToSmiles(MurckoScaffold.MakeScaffoldGeneric(mol))
            groups.setdefault(key,[]).append(item)
        sizes=[0]*10
        for key,members in sorted(groups.items(),key=lambda p:(-len(p[1]),hashlib.sha256(p[0].encode()).hexdigest())):
            fold=min(range(10),key=lambda t:(sizes[t],t));sizes[fold]+=len(members)
            for item in members:item['row']['fold']=str(fold)
        for item in rows:
            item.update(dataset=dataset,native_layout='declared SMILES with explicit H; graph targets only',
                source_record_sha256=hashlib.sha256(json.dumps(item['row'],sort_keys=True).encode()).hexdigest())
        return rows,paths
    path=BENCH/'scaffold_split'/dataset/'fold_assignments.csv';parent_sha=sha(path)
    with path.open(newline='') as stream:rows=list(csv.DictReader(stream))
    jobs=[];source_paths=[path];raw_sources={}
    if dataset=='cyp_isoform':
        for iso in ISOFORMS:
            raw=BENCH/'cyp_isoform/raw'/(iso+'.sdf');content=raw.read_bytes()
            frames=[];begin=0
            for match in re.finditer(rb'(?m)^\$\$\$\$(?:\r?\n|$)',content):
                frames.append(content[begin:match.end()]);begin=match.end()
            assert not content[begin:].strip(),'Unclosed original SDF source frame'
            raw_sources[iso]=(raw,sha(raw),frames);source_paths.append(raw)
    if dataset=='az_exactsom':
        raw=BENCH/'az_exactsom/raw/az_120_compounds.csv';source_paths.append(raw);raw_sha=sha(raw)
        with raw.open(newline='') as stream:az={r['Compound ID']:(ordinal,r) for ordinal,r in enumerate(csv.DictReader(stream),1)}
    for row in rows:
        job={'dataset':dataset,'row':row,'record_id':dataset+':'+row['sample_id'],
            'source_ref':str(path),'source_parent_sha256':parent_sha,
            'source_record_sha256':hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest(),
            'native_layout':'declared SMILES with explicit H; graph targets only'}
        if dataset=='cyp_isoform':
            raw,raw_sha,frames=raw_sources[row['isoform']];ordinal=int(row['sample_uid'].rsplit('::',1)[1])
            frame=frames[ordinal-1];end=frame.find(b'M  END');assert end>=0
            structural_end=frame.find(b'\n',end);block=frame[:structural_end+1].decode('utf-8')
            title=frame.splitlines()[0].decode().strip();compound=row['compound_id'].strip()
            aliases={('2C9',196,'pheanthrene','phenanthrene'),
                ('2C19',203,'tienilic_acid_derivative','tienilic_acid'),
                ('2C8',131,'tienilic_acid_derivative','tienilic_acid'),
                ('2C9',214,'tienilic_acid_derivative','tienilic_acid')}
            assert title==compound or (row['isoform'],ordinal,compound,title) in aliases
            job.update(source_ref=str(raw),source_parent_sha256=raw_sha,source_ordinal=ordinal,
                raw_frame=frame,mol_block=block,source_record_sha256=hashlib.sha256(frame).hexdigest(),native_layout='original source SDF atom rows; scratch-added H not returned')
        elif dataset=='az_exactsom':
            ordinal,raw_row=az[row['compound_id']]
            job.update(source_ref=str(raw),source_parent_sha256=raw_sha,source_ordinal=ordinal,
                raw_smiles=raw_row['SMILES'],groups=raw_row[GROUP_COLUMN],flags=raw_row[FLAG_COLUMN],
                source_record_sha256=hashlib.sha256(json.dumps(raw_row,sort_keys=True).encode()).hexdigest(),native_layout='original default raw SMILES parser atom rows')
        jobs.append(job)
    assert len({v['record_id'] for v in jobs})==len(jobs)
    return jobs,source_paths

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--dataset',choices=['qm7','qm9','cyp_isoform','az_exactsom','expansionrx'],required=True);ap.add_argument('--limit',type=int);args=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    import pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    jobs,paths=declared_jobs(args.dataset);refs=[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in paths]
    for ordinal,job in enumerate(jobs):job['member_order']=ordinal
    total=len(jobs)
    if args.limit:jobs=jobs[:args.limit]
    folder=ROOT/('probe_data_development_v2' if args.limit else 'probe_data_v2');folder.mkdir(exist_ok=True)
    output=folder/(args.dataset+'.parquet');assert not output.exists()
    fields={'dataset':pa.string(),'record_id':pa.string(),'member_order':pa.int32(),'fold':pa.int8(),'geometry_status':pa.string(),'annotation_status':pa.string(),
        'coordinates':pa.list_(pa.float64()),'atomic_numbers':pa.list_(pa.int16()),'targets':pa.list_(pa.float64()),
        'candidate_mask':pa.list_(pa.bool_()),'supervision_mask':pa.list_(pa.bool_()),'inchikey14':pa.string(),'seed':pa.int32(),
        'uff_energy_kcal_mol':pa.float64(),'uff_iterations':pa.int32(),'uff_converged':pa.bool_(),'source_ref':pa.string(),
        'source_record_sha256':pa.string(),'source_parent_sha256':pa.string(),'native_layout':pa.string(),'rdkit_version':pa.string(),
        'error':pa.string(),'elapsed_seconds':pa.float64()}
    writer=pq.ParquetWriter(str(output)+'.pending',pa.schema(list(fields.items())),compression='zstd')
    statuses=Counter();count=0;buffer=[];workers=int(os.environ['SLURM_CPUS_PER_TASK'])-1
    with ProcessPoolExecutor(workers,mp_context=mp.get_context('spawn'),initializer=init_worker) as pool:
        iterator=iter(jobs);active={}
        def fill():
            while len(active)<2*workers:
                job=next(iterator,None)
                if job is None:return
                active[pool.submit(generate,job)]=job['record_id']
        fill()
        while active:
            done,_=wait(active,return_when=FIRST_COMPLETED)
            for future in done:
                expected=active.pop(future);row=future.result();assert row['record_id']==expected
                buffer.append(row);statuses[row['geometry_status']]+=1;count+=1
            if len(buffer)>=256:
                writer.write_table(pa.Table.from_pylist(buffer,schema=writer.schema));buffer=[]
            fill()
        if buffer:writer.write_table(pa.Table.from_pylist(buffer,schema=writer.schema))
    writer.close();assert count==len(jobs)
    Path(str(output)+'.pending').replace(output)
    for ref in refs:assert sha(ref['path'])==ref['sha256']
    result={'status':'BOUNDED_DEVELOPMENT_ONLY' if args.limit else 'DATASET_MEMBERS_AND_COMMON_UFF_GEOMETRY_CLOSED',
        'dataset':args.dataset,'job_id':os.environ['SLURM_JOB_ID'],'declared_members':total,'processed_members':count,
        'geometry_status_counts':dict(statuses),'output':{'path':str(output),'sha256':sha(output),'rows':count},
        'sources':refs,'generator_sha256':sha(__file__),'no_original_source_files_written':True,'new_lmdb_created':False,
        'native_QM_layout':'declared frozen SMILES plus explicit H; no atom-level XYZ correspondence claimed; graph readouts only',
        'recipe':{'embedding':'ETKDGv3','max_iterations':200,'embedding_timeout_seconds':2,'candidate_count':1,
            'optimizer':'UFF','max_uff_iterations':500,'vdw_threshold_A':100.,'fallback':False,'seed_rule':'ordered native graph SHA256, deterministic'},
        'folds':'retain original four benchmark scaffold assignments; ExpansionRx new10 scaffold folds under guide override'}
    save(folder/(args.dataset+'_receipt.json'),result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
