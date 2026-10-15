"""Read-only neutral-geometry analysis. No LMDB is created or modified."""
from __future__ import annotations
import argparse, hashlib, json, math, multiprocessing as mp, os, pickle
import signal, socket, sys, time
from collections import Counter
from pathlib import Path
from multiprocessing.connection import wait

ROOT = Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
AUDIT = Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2')
WHITELIST = {1,5,6,7,8,9,14,15,16,17,34,35,53}

class SourceBindingError(RuntimeError):
    pass

def save_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    os.replace(tmp, path)

def analyze(row, handles, sources):
    import lmdb, numpy as np
    from rdkit import Chem
    from rdkit.Chem import rdDetermineBonds
    result = {'record_id':row['record_id'], 'molecule_id':row['molecule_id'],
              'geometry_X01':False, 'X05':None, 'C02':False, 'C03':False,
              'I01':False, 'T01':False, 'G01':False, 'G02':False, 'G03':False,
              'B01':False, 'reidentified_smiles':None, 'reidentified_inchikey':None,
              'reidentified_connectivity_key':None, 'connectivity_mismatch':False,
              'stereo_only_key_mismatch':False, 'error':None, 'geometry_seconds':None}
    start = time.monotonic()
    sid = int(row['shard_id']); real = int(row.get('real_index', row.get('source_record_index',0)))
    if sid not in handles:
        handles[sid] = lmdb.open(sources[sid]['path'], subdir=False, readonly=True,
            lock=False, create=False, readahead=False, meminit=False, max_readers=512)
    with handles[sid].begin(buffers=False) as tx:
        payload = tx.get(f'{real:09d}'.encode())
    if payload is None:
        raise SourceBindingError('Missing source record')
    if row.get('record_payload_sha256') and hashlib.sha256(payload).hexdigest() != row['record_payload_sha256']:
        raise SourceBindingError('Source record differs from reusable inventory')
    raw = pickle.loads(payload)
    z = raw.x.detach().cpu().numpy().reshape(-1).astype(int) + 1
    xyz = raw.pos.detach().cpu().numpy().astype(float)
    result['X05'] = bool(int(z.sum()) % 2)
    if xyz.shape != (len(z),3) or not np.isfinite(xyz).all():
        raise ValueError('Nonfinite or malformed coordinates')
    source_mol = Chem.MolFromSmiles(row['smiles'])
    source_h = Chem.AddHs(source_mol) if source_mol is not None else None
    aligned_source = source_h is not None and source_h.GetNumAtoms()==len(z) and all(
        source_h.GetAtomWithIdx(i).GetAtomicNum()==int(zi) for i,zi in enumerate(z))
    rw = Chem.RWMol()
    for i,zi in enumerate(z):
        atom=Chem.Atom(int(zi))
        if aligned_source:atom.SetIsotope(source_h.GetAtomWithIdx(i).GetIsotope())
        rw.AddAtom(atom)
    mol = rw.GetMol(); conf = Chem.Conformer(len(z)); conf.Set3D(True)
    for i, p in enumerate(xyz): conf.SetAtomPosition(i, tuple(map(float,p)))
    mol.AddConformer(conf)
    rdDetermineBonds.DetermineConnectivity(mol, useHueckel=False, charge=0, useVdw=False)
    result['geometry_X01'] = len(Chem.GetMolFrags(mol)) > 1
    dist = np.linalg.norm(xyz[:,None,:]-xyz[None,:,:], axis=2)
    u = np.triu_indices(len(z),1); ds = dist[u]
    result['G01'] = bool(ds.size and (ds < .5).any())
    adj = np.zeros((len(z),len(z)), dtype=bool)
    for b in mol.GetBonds():
        i,j=b.GetBeginAtomIdx(),b.GetEndAtomIdx(); adj[i,j]=adj[j,i]=True
    # Reuse the measured distances against the stored, ordered graph. For the
    # few unassigned old-QA records without cached distances, measure them here.
    if aligned_source:
        source_adj=np.zeros_like(adj)
        pairs=[]
        for bond in source_h.GetBonds():
            i,j=bond.GetBeginAtomIdx(),bond.GetEndAtomIdx();source_adj[i,j]=source_adj[j,i]=True;pairs.append((i,j))
        result['G02']=bool(ds.size and (ds[~source_adj[u]] < .9).any())
        radii=np.array([Chem.GetPeriodicTable().GetRcovalent(int(zi)) for zi in z])
        ratios=np.array([dist[i,j]/(radii[i]+radii[j]) for i,j in pairs])
        bad=(ratios < .75)|(ratios > 1.3)
        result['G03']=bool(len(bad)>=5 and bad.mean()>.25)
        result['B01']=bool(bad.any())
    else:
        result['G02']=bool(row['G02']) if row.get('G02') is not None else False
        result['G03']=bool(row.get('order_suspected_from_bond_lengths') or row.get('G03',False))
        result['B01']=bool((row.get('bond_length_outlier_count') or 0)>0 or row.get('B01',False))
        if source_mol is not None:
            result['C03']=True;result['error']='Stored graph does not align with source atomic sequence; nonbond/order measurements unavailable'
    if result['geometry_X01'] or result['X05']:
        result['geometry_seconds'] = time.monotonic()-start
        return result
    # A total charge of zero permits internal formal-charge separation.
    try:
        rdDetermineBonds.DetermineBondOrders(mol, charge=0, allowChargedFragments=True,
            embedChiral=True, useAtomMap=False)
        Chem.SanitizeMol(mol)
    except Exception as exc:
        result['C02'] = True; result['C03'] = True
        result['error'] = type(exc).__name__ + ': ' + str(exc)[:1000]
        result['geometry_seconds'] = time.monotonic()-start
        return result
    result['C02'] = Chem.GetFormalCharge(mol) != 0 or any(a.GetNumRadicalElectrons() for a in mol.GetAtoms())
    mol_no_h = Chem.RemoveHs(mol)
    result['reidentified_smiles'] = Chem.MolToSmiles(mol_no_h, isomericSmiles=True)
    result['reidentified_inchikey'] = Chem.MolToInchiKey(mol_no_h) or None
    got = result['reidentified_inchikey']; stored = row.get('inchikey') or row.get('stored_inchikey')
    if not stored:
        src_mol = Chem.MolFromSmiles(row['smiles'])
        stored = Chem.MolToInchiKey(src_mol) if src_mol else None
    if not got or not stored:
        result['C03'] = True; result['error'] = 'Missing generated or source InChIKey'
    else:
        result['reidentified_connectivity_key'] = got[:14]
        result['I01'] = got != stored
        result['connectivity_mismatch'] = got[:14] != stored[:14]
        result['stereo_only_key_mismatch'] = got != stored and got[:14] == stored[:14]
        # Only stereo explicitly specified in the stored SMILES can contradict
        # a geometry. A previously unspecified center remains unspecified input.
        if aligned_source:
            Chem.AssignStereochemistry(source_h, cleanIt=True, force=True)
            Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
            for i,atom in enumerate(source_h.GetAtoms()):
                if atom.HasProp('_CIPCode'):
                    inferred=mol.GetAtomWithIdx(i)
                    if not inferred.HasProp('_CIPCode') or inferred.GetProp('_CIPCode')!=atom.GetProp('_CIPCode'):
                        result['T01']=True
            for bond in source_h.GetBonds():
                stereo=str(bond.GetStereo())
                if stereo in ('STEREOE','STEREOZ','STEREOCIS','STEREOTRANS'):
                    inferred=mol.GetBondBetweenAtoms(bond.GetBeginAtomIdx(),bond.GetEndAtomIdx())
                    if inferred is None or str(inferred.GetStereo())!=stereo:result['T01']=True
    result['geometry_seconds'] = time.monotonic()-start
    return result

def worker(conn, sources):
    import torch
    from rdkit import RDLogger
    torch.set_num_threads(1); RDLogger.DisableLog('rdApp.*')
    handles = {}
    try:
        while True:
            row = conn.recv()
            if row is None: break
            try:
                result = analyze(row, handles, sources)
            except SourceBindingError as exc:
                conn.send({'fatal_source_change':str(exc),'record_id':row['record_id']})
                break
            except Exception as exc:
                result = {'record_id':row['record_id'], 'molecule_id':row['molecule_id'],
                    'C02':False,'C03':True,'I01':False,'error':type(exc).__name__+': '+str(exc)[:1000]}
            conn.send(result)
    finally:
        for env in handles.values(): env.close()
        conn.close()

def main():
    import pyarrow as pa, pyarrow.parquet as pq, pyarrow.dataset as ds
    parser=argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--workers', type=int, default=16)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--shards', help='Comma-separated source shard IDs for disjoint parallel jobs')
    args=parser.parse_args()
    allocated=int(os.environ.get('SLURM_CPUS_PER_TASK','0'))
    if not os.environ.get('SLURM_JOB_ID') or allocated<16 or not 16<=args.workers<=allocated:
        raise RuntimeError('Requires Slurm allocation >=16 CPUs and workers within allocation')
    plan=json.loads((AUDIT/'plan.json').read_text()); sources=plan['sources']
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    output=out/'geometry_annotations.parquet'
    if output.exists(): raise RuntimeError('Existing final output; use a new output directory')
    fields=[('record_id',pa.string()),('molecule_id',pa.string()),
        ('geometry_X01',pa.bool_()),('X05',pa.bool_()),('C02',pa.bool_()),('C03',pa.bool_()),
        ('I01',pa.bool_()),('T01',pa.bool_()),('G01',pa.bool_()),('G02',pa.bool_()),
        ('G03',pa.bool_()),('B01',pa.bool_()),('reidentified_smiles',pa.string()),
        ('reidentified_inchikey',pa.string()),('reidentified_connectivity_key',pa.string()),
        ('connectivity_mismatch',pa.bool_()),('stereo_only_key_mismatch',pa.bool_()),
        ('error',pa.string()),('geometry_seconds',pa.float64())]
    schema=pa.schema(fields)
    writer=pq.ParquetWriter(output.with_suffix('.parquet.partial'),schema,compression='zstd')
    ctx=mp.get_context('spawn'); slots=[]
    def start_slot():
        parent,child=ctx.Pipe(); proc=ctx.Process(target=worker,args=(child,sources));proc.start();child.close()
        return {'conn':parent,'proc':proc,'row':None,'started':0}
    for _ in range(args.workers): slots.append(start_slot())
    selected_shards={int(x) for x in args.shards.split(',')} if args.shards else None
    dataset=ds.dataset(args.input,format='parquet')
    needed=['record_id','molecule_id','shard_id','real_index','record_payload_sha256',
      'smiles','inchikey','stored_inchikey','X01','X02','X03','X04','X05',
      'G01','G02','G03','B01','order_suspected_from_bond_lengths','bond_length_outlier_count']
    input_columns=[name for name in needed if name in dataset.schema.names]
    for mandatory in ['record_id','molecule_id','shard_id','real_index','smiles']:
        if mandatory not in input_columns:raise RuntimeError('Missing input field '+mandatory)
    predicate=ds.field('shard_id').isin(sorted(selected_shards)) if selected_shards is not None else None
    scanner=dataset.scanner(columns=input_columns,filter=predicate,batch_size=4096)
    def rows():
        n=0
        for batch in scanner.to_batches():
            for row in batch.to_pylist():
                if selected_shards is not None and int(row['shard_id']) not in selected_shards:continue
                if any(row.get(code) is True for code in ['X01','X02','X03','X04','X05']):continue
                if args.limit and n >= args.limit: return
                n+=1; yield row
    iterator=iter(rows()); exhausted=False; results=[]; counts=Counter(); done=0; start=time.monotonic()
    try:
        while True:
            for slot in slots:
                if slot['row'] is None and not exhausted:
                    try: row=next(iterator)
                    except StopIteration: exhausted=True;break
                    slot['row']=row;slot['started']=time.monotonic();slot['conn'].send(row)
            active=[s for s in slots if s['row'] is not None]
            if exhausted and not active: break
            ready=wait([s['conn'] for s in active],timeout=.1)
            for slot in active:
                result=None
                if slot['conn'] in ready:
                    try: result=slot['conn'].recv()
                    except (EOFError,OSError): result=None
                timeout=time.monotonic()-slot['started'] > args.timeout + (90 if done<args.workers else 0)
                if result is None and (timeout or not slot['proc'].is_alive()):
                    row=slot['row']
                    if slot['proc'].is_alive(): slot['proc'].terminate()
                    slot['proc'].join(5)
                    if slot['proc'].is_alive():slot['proc'].kill();slot['proc'].join(5)
                    slot['conn'].close()
                    result={'record_id':row['record_id'],'molecule_id':row['molecule_id'],
                            'C03':True,'C02':False,'I01':False,'error':'geometry_timeout' if timeout else 'worker_exit'}
                    replacement=start_slot();slot.clear();slot.update(replacement)
                if result is not None:
                    if result.get('fatal_source_change'):
                        save_json(out/'source_input_failure.json',result)
                        raise SourceBindingError(str(result))
                    results.append(result); done+=1
                    for key,value in result.items():
                        if value is True:counts[key]+=1
                    slot['row']=None
                if len(results)>=4096:
                    writer.write_table(pa.Table.from_pylist(results,schema=schema));results.clear()
                    elapsed=time.monotonic()-start
                    save_json(out/'progress.json',{'completed':done,'seconds':elapsed,'records_per_second':done/elapsed,'counts':dict(counts)})
        if results:writer.write_table(pa.Table.from_pylist(results,schema=schema));results.clear()
        writer.close();os.replace(output.with_suffix('.parquet.partial'),output)
        save_json(out/'summary.json',{'status':'COMPLETE','rows':done,'seconds':time.monotonic()-start,
            'counts':dict(counts),'workers':args.workers,'timeout_seconds':args.timeout,
            'hostname':socket.gethostname(),'job_id':os.environ.get('SLURM_JOB_ID'),
            'input':args.input,'output':str(output),'selected_shards':sorted(selected_shards) if selected_shards else None,
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'source_lmdb_readonly':True,'lmdb_created_or_written':False,
            'I01_comparison':'full InChIKey, stereo-only overlap reported separately',
            'method':'DetermineConnectivity and DetermineBondOrders (rdDetermineBonds), charge=0, internal charged fragments allowed'})
    finally:
        try:writer.close()
        except Exception:pass
        for slot in slots:
            if slot['proc'].is_alive():
                try:slot['conn'].send(None)
                except (OSError,BrokenPipeError):pass
            slot['proc'].join(10)
            if slot['proc'].is_alive():slot['proc'].terminate();slot['proc'].join(5)
            slot['conn'].close()

if __name__ == '__main__':main()
