"""G3: all-pilot12-type dictionary zstd/SQLite, family float64 and staged-wire benchmark.

Only Root submits, on nodes14..19, >=16 effective workers. Original raw/LMDB
are read-only. No LMDB is created. Legacy missing input/AUX/sidefiles are
explicit: input is reconstructed, absent raw is never counted as measured0.
"""
from __future__ import annotations
import argparse,ast
from collections import Counter,defaultdict
import concurrent.futures,hashlib,importlib,json,math,multiprocessing,os
from pathlib import Path
import pickle,shutil,socket,struct,subprocess,sys,tarfile,tempfile,time
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
SCREEN=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
DEPS=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2')
sys.path[:0]=[str(DEPS/'deps'),str(DEPS/'scripts/deps')]
import wp5_archive as A
CONFIG=LEGACY_CONFIG=GEOMETRY=PANEL=ENTRIES=PQMOD=None
def sha(path):return A.file_sha(path)
def read(path):return json.loads(Path(path).read_text())
def save(path,value):
    p=Path(path);q=p.with_name(p.name+'.pending')
    q.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n');q.replace(p)
def own(path):
    p=Path(path).absolute()
    if not p.is_relative_to(ROOT):raise ValueError('Only own WP5 output')
    return p

def initialize(config_path,legacy_path,geometry_path,panel_path,registry_path,barrier):
    global CONFIG,LEGACY_CONFIG,GEOMETRY,PANEL,ENTRIES,PQMOD
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
    import pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    CONFIG=read(config_path);LEGACY_CONFIG=read(legacy_path);tasks={v['name'] for v in CONFIG['tasks']}
    if tasks!=set(A.CALC_TYPES):raise ValueError('Exact noPOLAR/noESP/noHess12-task config required')
    if any('POLAR' in v.get('keywords','').upper() for v in CONFIG['tasks']):raise ValueError('POLAR keyword in formal config')
    GEOMETRY={r['record_id']:r for r in pq.read_table(geometry_path,use_threads=False).to_pylist()}
    PANEL={r['record_id']:r for r in pq.read_table(panel_path,use_threads=False).to_pylist()}
    import wp5_parquet as p
    PQMOD=p;ENTRIES=p.registry(registry_path)
    # Reuse precisely the C4 checked source reader and D20/3D rules.
    sys.path.insert(0,str(SCREEN/'scripts'))
    import c_engineering_storage as cs
    cs.SOURCES=read(DEPS/'plan.json')['sources']
    cs.WIRE.metadata()
    import torch
    torch.set_num_threads(1)
    barrier.wait(timeout=240)

def input_files(task,row):
    import numpy as np
    legacy=LEGACY_CONFIG;task=next(t for t in legacy['tasks'] if t['name']==task['name'])
    geometry=GEOMETRY[row['record_id']];coords=np.asarray(geometry['positions_A'],dtype=np.float64)
    symbols=geometry['elements']
    seed=1+int(hashlib.sha256((str(legacy['seed'])+'|'+row['record_id']).encode()).hexdigest()[:16],16)%2147483646
    if task.get('perturbed'):coords=coords+np.random.default_rng(seed).normal(0,legacy['perturb_sigma_A'],coords.shape)
    xyz=str(len(symbols))+'\nWP4 native geometry; coordinates Angstrom; '+row['record_id']+'\n'
    xyz+='\n'.join(f'{s} {x:.12f} {y:.12f} {z:.12f}' for s,(x,y,z) in zip(symbols,coords))+'\n'
    values={'input.xyz':xyz.encode()}
    if task['family']=='mopac':
        keywords=task['keywords']+' THREADS=1'
        text=keywords+'\n'+row['record_id']+'\nStored native PM7 coordinates; single point, no optimization\n'
        text+='\n'.join(f'{s} {x:.12f} 1 {y:.12f} 1 {z:.12f} 1' for s,(x,y,z) in zip(symbols,coords))+'\n'
        values['input.mop']=text.encode();argv=[legacy['mopac_executable'],'input.mop']
    else:
        keywords=task['args'];values['native.inp']=task.get('xcontrol','$write\n json=true\n$end\n').encode()
        argv=[legacy['xtb_executable'],'input.xyz','--input','native.inp','--norestart','--parallel','1',*task['args']]
    # Versions/complete flags always persist, including xTB's command-line flags.
    values['input_recipe.json']=A.canonical({'input_origin':'RECONSTRUCTED_INPUT_NOT_HISTORICAL_ORIGINAL',
        'task':task,'argv':argv,'seed_rule':legacy['seed'],'perturb_seed':seed if task.get('perturbed') else None,
        'perturb_sigma_A':legacy['perturb_sigma_A'] if task.get('perturbed') else None,
        'input_generator':'Exact frozen original pilot rendering including historical B POLAR; reconstructed, not originally archived'})
    return [{'name':k,'data':v,'byte_count':len(v),'sha256':A.digest(v),'role':'input'} for k,v in values.items()],keywords

def load_source(source):
    import pyarrow.parquet as pq
    receipt=read(source['receipt']);ref=receipt['parquet']
    if Path(ref['path']).stat().st_size!=ref['bytes'] or sha(ref['path'])!=ref['sha256']:raise ValueError('Pilot Parquet binding differs')
    rows=[]
    for batch in pq.ParquetFile(ref['path']).iter_batches(batch_size=16,columns=['record_id','task','status','details_json'],use_threads=False):
        for r in batch.to_pylist():
            if r['task'] in A.CALC_TYPES:
                detail=json.loads(r['details_json'])
                rows.append({'record_id':r['record_id'],'calc_type':r['task'],'detail':detail})
    keys={(r['record_id'],r['calc_type']) for r in rows}
    expected={(record_id,t) for record_id in source['record_ids'] for t in A.CALC_TYPES}
    if keys!=expected or len(rows)!=len(expected):raise ValueError('MANIFEST_COUNT_MISMATCH_PILOT12')
    archive=receipt.get('archive')
    prefixes={}
    for r in rows:
        ref=r['detail'].get('archive')
        if ref:prefixes[ref['member_prefix']]=r
        r['output_files']=[]
    if archive:
        path=Path(archive['path'])
        if path.stat().st_size!=archive['bytes'] or sha(path)!=archive['sha256']:raise ValueError('Pilot archive binding differs')
        proc=subprocess.Popen([CONFIG['zstd_executable'],'-d','-c',str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.DEVNULL)
        try:
            with tarfile.open(fileobj=proc.stdout,mode='r|') as handle:
                for member in handle:
                    if not member.isfile():continue
                    parts=member.name.split('/');prefix='/'.join(parts[:2])
                    if prefix not in prefixes:continue
                    name='/'.join(parts[2:]);A.safe_name(name)
                    data=handle.extractfile(member).read()
                    prefixes[prefix]['output_files'].append({'name':name,'data':data,'byte_count':len(data),'sha256':A.digest(data),'role':'output'})
        finally:
            while proc.stdout.read(1<<20):pass
            proc.stdout.close();error=proc.stderr.read();code=proc.wait()
        if code:raise RuntimeError('Pilot archive decoder failed: '+error.decode(errors='replace')[-500:])
    for r in rows:
        expected_files={v['name']:v for v in r['detail'].get('archived_files',[])}
        actual={v['name']:v for v in r['output_files']}
        if set(actual)!=set(expected_files):raise ValueError('Pilot archived-file names differ')
        for name,v in actual.items():
            expected=expected_files[name]
            if v['sha256']!=expected['sha256'] or v['byte_count']!=expected['bytes']:raise ValueError('Pilot raw original file SHA differs')
    return receipt,rows

def scope_status(detail,task):
    status=detail['status']
    # Preserve source status; remove only a failure caused exclusively by POLAR.
    missing=detail.get('missing_properties') or detail.get('missing_required_values') or []
    if task=='pm7_B' and status=='PROPERTY_FAILED' and detail.get('B_base_success') and missing and all('polar' in v.lower() for v in missing):
        return 'SUCCESS','ONLY_REMOVED_POLAR_PROPERTY_FAILURE'
    return status,None

def raw_record(source,receipt,value):
    row=PANEL[value['record_id']];task=next(v for v in CONFIG['tasks'] if v['name']==value['calc_type'])
    files,keywords=input_files(task,row);detail=value['detail'];scope,reason=scope_status(detail,value['calc_type'])
    return {'record_id':value['record_id'],'molecule_id':source['molecule_id'],'calc_type':value['calc_type'],
        'source_payload_sha256':row['record_payload_sha256'],'size_stratum':source['size_stratum'],
        'source_status':detail['status'],'scope_status':scope,'scope_status_reason':reason,
        'is_minimum':value['record_id']==receipt['minimum_original_energy_record_id'],
        'input_origin':'RECONSTRUCTED_INPUT','original_input_SHA_available':False,'original_input_sha256':None,
        'keywords':keywords,'software':detail.get('software_version_lines',[]),
        'source_reference':{'source_Parquet':receipt['parquet'],'source_archive':receipt.get('archive'),
            'retired_per_call_archive_sha256':(detail.get('archive') or {}).get('retired_partial_archive_sha256')},
        'files':files+value['output_files']}

def bounded_samples(data,n=4096):
    if len(data)<=n:return [data] if data else []
    return [data[:n],data[max(0,len(data)//2-n//2):len(data)//2+n//2],data[-n:]]

def train_reader(item):
    rank,sources,sample_root=item
    root=Path(sample_root)/f'worker_{rank:02d}';root.mkdir(parents=True)
    handles={t:(root/(t+'.samples')).open('wb') for t in A.CALC_TYPES};counts=Counter();bytes_=Counter();source_rows=0
    try:
        for source in sources:
            _,rows=load_source(source);source_rows+=len(rows)
            for r in rows:
                for f in r['output_files']:
                    for sample in bounded_samples(f['data']):
                        handles[r['calc_type']].write(struct.pack('<I',len(sample)));handles[r['calc_type']].write(sample)
                        counts[r['calc_type']]+=1;bytes_[r['calc_type']]+=len(sample)
    finally:
        for h in handles.values():h.close()
    return {'worker_pid':os.getpid(),'source_rows':source_rows,'samples':dict(counts),'bytes':dict(bytes_),
        'paths':{t:str(root/(t+'.samples')) for t in A.CALC_TYPES}}

def train_dictionary(item):
    task,paths,output=item;samples=[]
    for path in paths:
        with Path(path).open('rb') as handle:
            while True:
                size=handle.read(4)
                if not size:break
                if len(size)!=4:raise ValueError('Training sample framing incomplete')
                n=struct.unpack('<I',size)[0];sample=handle.read(n)
                if len(sample)!=n:raise ValueError('Training sample payload incomplete')
                samples.append(sample)
    codec=A.Zstd();dictionary=codec.train(samples);target=Path(output)/(task+'.dict')
    if target.exists():raise FileExistsError(target)
    target.write_bytes(dictionary)
    entry={'calc_type':task,'path':str(target),'bytes':len(dictionary),'sha256':A.digest(dictionary),'dict_id':A.digest(dictionary),
        'native_dict_id':codec.lib.ZSTD_getDictID_fromDict(__import__('ctypes').c_char_p(dictionary),len(dictionary)),
        'sample_count':len(samples),'sample_bytes':sum(map(len,samples)),'training_scope':'All pilot12 requested types; bounded start/middle/end segments of every stored real raw file',
        'zstd_version':codec.version,'worker_pid':os.getpid()}
    codec.close();return entry

class Families:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True);self.writers={};self.buffers=defaultdict(list);self.keys={};self.groups=defaultdict(list);self.paths={}
        self.schemas={**{f:PQMOD.SCHEMA for f in set(PQMOD.FAMILIES.values())},
            'basic_geometry':PQMOD.BASE_SCHEMA,'D20':PQMOD.D20_SCHEMA,'D3':PQMOD.D3_SCHEMA,'QC':PQMOD.QC_SCHEMA}
    def add(self,family,key,row):
        if self.buffers[family] and self.keys[family]!=key:self.flush(family)
        self.keys[family]=key;self.buffers[family].append(row)
        if len(self.buffers[family])>=64:self.flush(family)
    def flush(self,family):
        if not self.buffers[family]:return
        import pyarrow as pa,pyarrow.parquet as pq
        if family not in self.writers:
            path=self.root/(family+'.parquet');self.paths[family]=path
            self.writers[family]=pq.ParquetWriter(path,self.schemas[family],compression='zstd',compression_level=3)
        table=pa.Table.from_pylist(self.buffers[family],schema=self.schemas[family])
        self.writers[family].write_table(table,row_group_size=len(self.buffers[family]))
        self.groups[family].append({'size_stratum':self.keys[family],'rows':len(self.buffers[family])});self.buffers[family]=[]
    def close(self):
        import pyarrow.parquet as pq
        for family in list(self.buffers):self.flush(family)
        for writer in self.writers.values():writer.close()
        result=[]
        for family,path in self.paths.items():
            meta=pq.ParquetFile(path).metadata;compressed=[]
            for i in range(meta.num_row_groups):
                group=meta.row_group(i);compressed.append(sum(group.column(j).total_compressed_size for j in range(group.num_columns)))
            extra=path.stat().st_size-sum(compressed);rows=sum(v['rows'] for v in self.groups[family])
            by=defaultdict(lambda:{'rows':0,'bytes':0})
            for group,amount in zip(self.groups[family],compressed):
                by[group['size_stratum']]['rows']+=group['rows'];by[group['size_stratum']]['bytes']+=amount+extra*group['rows']/rows
            result.append({'family':family,'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'rows':rows,'strata':dict(by)})
        return result

def base_rows(record_id,details,rank):
    import c_engineering_storage as cs
    row=PANEL[record_id];raw,_=cs.raw_source(row);corrected,issues=cs.WIRE.corrected_base(raw,row)
    g=GEOMETRY[record_id];field=cs.WIRE.field
    d=field(corrected,'D_native_3D');d20=field(corrected,'rdkit_graph_desc').reshape(-1).tolist()
    mask=field(corrected,'rdkit_graph_desc_mask').reshape(-1).tolist()
    common={'record_id':record_id,'molecule_id':row['molecule_id'],'file_group':row['file_group'],
        'attempt_id':0,'job_id':int(os.environ['SLURM_JOB_ID']),'task_id':'G3_LEGACY_PROFILE'}
    b=details['pm7_B'];values=b.get('values',{});old=b.get('stored_HOF_kcal_mol');new=values.get('heat_of_formation_kcal_mol')
    geom={**common,'source_path':row.get('source_path',g.get('source_path')),'real_index':row['real_index'],
        'source_payload_sha256':row['record_payload_sha256'],'new_role':row.get('new_role',str(row.get('split','')).upper()),'member_routine':row.get('member_routine'),
        'conformer_id':row.get('conformer_id'),'atomic_numbers':g['atomic_numbers'],'positions_A':g['positions_A'],
        'bond_pairs':g['bond_pairs_zero_based'],'bond_order_codes':g.get('bond_order_codes'),
        'native_atom_order_sha256':g.get('native_atom_order_sha256'),'stored_bond_graph_sha256':g.get('stored_bond_graph_sha256'),
        'old_stored_PM7_HOF_kcal_mol':old,'new_PM7_HOF_kcal_mol':new,'new_PM7_HOF_valid':b.get('B_base_success',b['status']=='SUCCESS'),
        'Q02_delta_HOF_kcal_mol':b.get('Q02_delta_HOF_kcal_mol'),'geometry_status':'SUCCESS',
        'source_native_geometry_sha256':g.get('native_coordinates_sha256')}
    d2={**common,'schema_ref':'C4_VERIFIED_D20_HBA_RULES','descriptor_names':list(cs.WIRE.D20),
        'values_float64':[float(v) for v in d20],'valid_mask':[bool(v) for v in mask],
        'status':'SUCCESS' if not issues else 'PROPERTY_FAILED','issues':issues}
    d3={**common,'schema_ref':'C4_VERIFIED_NATIVE_D3_RULES','PMI1':d.get('PMI1'),'PMI2':d.get('PMI2'),'PMI3':d.get('PMI3'),
        'PBF_A':d.get('PBF'),'volume_A3':d.get('volume_A3'),'SASA_total_A2':d.get('SASA_total_A2'),
        'SASA_atom_A2':PQMOD.native(d.get('SASA_atom_A2')),'status':'SUCCESS' if not issues else 'PROPERTY_FAILED','issues':issues}
    statuses=[{'calc_type':t,'status':scope_status(v,t)[0],'source_status':v['status'],'failure_code':v.get('failure_code'),
        'elapsed_seconds':v.get('elapsed_seconds'),'predicted_seconds':None} for t,v in details.items()]
    qc={**common,'Q01_gradient_norm_kcal_mol_A':b.get('Q01_gradient_norm_kcal_mol_A'),
        'Q02_delta_HOF_kcal_mol':b.get('Q02_delta_HOF_kcal_mol'),
        'cation_S2_minus_0p75':(details['pm7_cation'].get('values',{}).get('s2')-0.75) if details['pm7_cation'].get('values',{}).get('s2') is not None else None,
        'anion_S2_minus_0p75':(details['pm7_anion'].get('values',{}).get('s2')-0.75) if details['pm7_anion'].get('values',{}).get('s2') is not None else None,
        'population_QC_json':json.dumps({k:v for k,v in row.items() if k.startswith('QC_') or k in ('T01','T01_original','B01','H01_abs_energy_per_atom','S01','S01_backbone','S02_delta_energy_kcal_mol','I01_relaxed_to_T01','quality_codes')},separators=(',',':')),
        'task_statuses':statuses,'record_status':'ALL_REQUESTED_OUTCOMES_RECORDED'}
    return {'basic_geometry':geom,'D20':d2,'D3':d3,'QC':qc},issues

def benchmark_reader(item):
    import pyarrow.parquet as pq
    rank,sources,out,dictionary_manifest,config_path=item
    root=Path(out)/f'worker_{rank:02d}';root.mkdir(parents=True)
    writers={p:A.ArchiveWriter(root/(p+'.sqlite'),dictionary_manifest,config_path,policy=p) for p in ('ALL','SELECTIVE')}
    families=Families(root/'family_parquet');metrics=[];stage_metrics=[];issues=[];aux_ratios=[]
    original_keys=[]
    for source in sorted(sources,key=lambda v:(v['size_stratum'],v['molecule_id'])):
        receipt,values=load_source(source);by=defaultdict(dict);staged=[];family_data=defaultdict(list)
        for v in values:by[v['record_id']][v['calc_type']]=v['detail']
        for record_id,details in by.items():
            base,problems=base_rows(record_id,details,rank)
            if problems:issues.append({'record_id':record_id,'D_issues':problems})
            for family,row in base.items():families.add(family,source['size_stratum'],row);family_data[family].append(row)
        raw_records=[raw_record(source,receipt,v) for v in values]
        for v,r in zip(values,raw_records):
            detail=v['detail'];scoped={**detail,'source_status':r['source_status'],'scope_status':r['scope_status'],
                'qm_cpu_seconds':detail.get('qm_child_cpu_seconds')}
            row=PQMOD.task_row(r['record_id'],source['molecule_id'],r['calc_type'],scoped,ENTRIES,detail.get('natoms') or len(GEOMETRY[r['record_id']]['atomic_numbers']))
            row.update(attempt_id=0,job_id=int(os.environ['SLURM_JOB_ID']),task_id='G3_LEGACY_PROFILE',lane=rank)
            families.add(PQMOD.FAMILIES[r['calc_type']],source['size_stratum'],row);family_data[PQMOD.FAMILIES[r['calc_type']]].append(row)
            staged.append({'record_id':r['record_id'],'calc_type':r['calc_type'],'detail':scoped})
        import pyarrow as pa
        normalized={f:pa.Table.from_pylist(rows,schema=families.schemas[f]).to_pylist() for f,rows in family_data.items()}
        payload={'record_results':staged,'family_rows':normalized}
        for policy,writer in writers.items():
            with writer.molecule(source['molecule_id']):
                for value,r in zip(values,raw_records):
                    result=writer.put_record(r);detail=value['detail'];aux_size=detail.get('aux_bytes')
                    actual_aux=sum(f['byte_count'] for f in value['output_files'] if f['name'].endswith('.aux'))
                    if actual_aux:
                        aux_data=[f for f in value['output_files'] if f['name'].endswith('.aux')]
                        blob,_=A.bundle(aux_data);compressed=writer.zstd.compress(blob,writer.dicts[r['calc_type']]['data'])
                        if policy=='ALL':aux_ratios.append({'calc_type':r['calc_type'],'size_stratum':source['size_stratum'],'raw_aux_bytes':actual_aux,
                            'dict_aux_bundle_bytes':len(compressed),'ratio':len(compressed)/actual_aux})
                    raw_total=detail.get('raw_total_bytes');known_output=sum(f['byte_count'] for f in value['output_files'])
                    inputs=sum(f['byte_count'] for f in r['files'] if f['role']=='input' and f['name']!='input_recipe.json')
                    missing_aux=max(0,aux_size-actual_aux) if aux_size is not None else None
                    residual=max(0,raw_total-known_output-inputs-(missing_aux or 0)) if raw_total is not None else None
                    metrics.append({**result,'policy':policy,'record_id':r['record_id'],'molecule_id':source['molecule_id'],
                        'calc_type':r['calc_type'],'size_stratum':source['size_stratum'],'is_minimum':r['is_minimum'],
                        'source_status':r['source_status'],'scope_status':r['scope_status'],
                        'missing_aux_raw_bytes':missing_aux,'unclassified_unstored_scratch_bytes':residual})
                measured=writer.stage_molecule(source['molecule_id'],payload,len(source['record_ids']))
                stage_metrics.append({**measured,'policy':policy,'size_stratum':source['size_stratum']})
        original_keys.extend((r['record_id'],r['calc_type']) for r in raw_records)
    refs=families.close()
    # Verify each original raw member in each policy; stream temporary wires.
    # Family readback runs once, with only one molecule payload in memory.
    def staged_payload(reader,molecule_id):
        q=reader.db.execute('SELECT record_count,wire_sha256,uncompressed_bytes,dict_id,wire_frame FROM parsed_molecules WHERE molecule_id=?',(molecule_id,)).fetchone()
        if q is None:raise ValueError('Family readback lacks whole-molecule staging')
        d=reader.dicts['pm7_B']
        if q[3]!=d['dict_id']:raise ValueError('Readback staging dictionary ID differs')
        wire=reader.zstd.decompress(q[4],d['data'],q[2])
        if A.digest(wire)!=q[1]:raise ValueError('Readback staging wire SHA differs')
        return pickle.loads(wire)
    reader=A.ArchiveReader(writers['ALL'].path,dictionary_manifest);verified_family_rows=0
    try:
        for ref in refs:
            cached_molecule=None;expected={}
            for batch in pq.ParquetFile(ref['path']).iter_batches(batch_size=32,use_threads=False):
                for row in batch.to_pylist():
                    molecule=row['molecule_id']
                    if molecule!=cached_molecule:
                        payload=staged_payload(reader,molecule);cached_molecule=molecule
                        expected={(r['record_id'],r.get('calc_type')):r for r in payload['family_rows'][ref['family']]}
                    key=(row['record_id'],row.get('calc_type'))
                    if key not in expected:raise ValueError('Family row key differs from whole-molecule wire')
                    PQMOD.exact(expected[key],row);verified_family_rows+=1
    finally:reader.close()
    if verified_family_rows!=sum(ref['rows'] for ref in refs):raise ValueError('Typed family row roundtrip count differs')
    for policy,writer in writers.items():
        reader=A.ArchiveReader(writer.path,dictionary_manifest)
        try:
            for record_id,task in original_keys:reader.get(record_id,task)
            staged_count=sum(r['record_count'] for r in reader.iter_staged())
            if staged_count!=sum(len(v['record_ids']) for v in sources):raise ValueError('Staged record count differs')
        finally:reader.close()
        before=writer.path.stat().st_size
        retired=writer.retire_staged_after_verified_parquet(refs,vacuum=True,preverified=True)
        after=writer.path.stat().st_size
        stage_metrics.append({'policy':policy,'worker':rank,'container_before_retire_bytes':before,'container_after_retire_bytes':after,
            'vacuum_extra_reserve_bytes':retired['vacuum_parallel_extra_reserve_per_lane_bytes']})
        writer.close()
    return {'worker_pid':os.getpid(),'verified_typed_family_rows':verified_family_rows,'metrics':metrics,'staged':stage_metrics,'family_files':refs,'aux_ratios':aux_ratios,'issues':issues,
        'archives':{p:{'path':str(root/(p+'.sqlite')),'bytes':(root/(p+'.sqlite')).stat().st_size,'sha256':sha(root/(p+'.sqlite'))} for p in writers}}

def discover(root,panel_path):
    import pyarrow.parquet as pq
    panel=pq.read_table(panel_path,use_threads=False).to_pylist();by=defaultdict(list)
    for row in panel:by[row['molecule_id']].append(row)
    sources=[];seen=set()
    for path in sorted(Path(root).rglob('receipt.json')):
        receipt=read(path)
        if receipt.get('status')!='COMPLETE_WITH_RECORDED_OUTCOMES':continue
        molecule=receipt['molecule_id']
        if molecule not in by:continue
        if molecule in seen:raise ValueError('MANIFEST_COUNT_MISMATCH_DUPLICATE_MOLECULE')
        seen.add(molecule);keys={r['size_stratum'] for r in by[molecule]}
        if len(keys)!=1 or receipt['records']!=len(by[molecule]):raise ValueError('MANIFEST_COUNT_MISMATCH_PILOT_MOLECULE')
        sources.append({'receipt':str(path),'receipt_sha256':sha(path),'molecule_id':molecule,'size_stratum':next(iter(keys)),
            'record_ids':[r['record_id'] for r in by[molecule]]})
    if seen!=set(by) or len(panel)!=10020 or len(seen)!=1441:raise ValueError('MANIFEST_COUNT_MISMATCH_PILOT10020_1441')
    return panel,sources


def formal_sample_context(panel_path,formal_index,output,workers):
    import duckdb,pyarrow.parquet as pq
    db=duckdb.connect();db.execute(f'SET threads={workers}');db.execute("SET memory_limit='8GB'")
    try:
        table=db.execute('SELECT f.* FROM read_parquet(?) f JOIN read_parquet(?) p USING(record_id)',
            [str(formal_index),str(panel_path)]).fetch_arrow_table()
    finally:db.close()
    rows=table.to_pylist();original={r['record_id']:r for r in pq.read_table(panel_path,use_threads=False).to_pylist()}
    if len(rows)!=10020 or {r['record_id'] for r in rows}!=set(original):raise ValueError('MANIFEST_COUNT_MISMATCH_FORMAL_SAMPLE_CONTEXT')
    for r in rows:
        old=original[r['record_id']]
        if (r['molecule_id'],r['record_payload_sha256'],r['real_index'],r['shard_id'])!=(old['molecule_id'],old['record_payload_sha256'],old['real_index'],old['shard_id']):
            raise ValueError('Original/source pointer changed in formal context')
    pq.write_table(table,output,compression='zstd',compression_level=3)
    return {r['record_id']:r for r in rows}

def projection(benchmark,population_path,quota_path,temporary_path):
    result={'status':'PENDING_FORMAL_POPULATION_TEMPORARY_MODEL_AND_RAW_SCOPE_COVERAGE','policy_selected':None}
    if not population_path or not Path(population_path).is_file():return result
    population=read(population_path);strata=population.get('strata',population.get('formal',{}).get('strata'))
    if not strata:raise ValueError('Formal7 stratum population JSON required')
    records=sum(v['records'] for v in strata);molecules=sum(v['molecules'] for v in strata)
    if (records,molecules)!=(11231854,1220466):raise ValueError('MANIFEST_COUNT_MISMATCH_FORMAL_POPULATION')
    results=benchmark['workers'];metrics=[v for w in results for v in w['metrics']];families=[v for w in results for v in w['family_files']]
    group_samples=benchmark['sample_strata'];family_bytes=0;family_detail=[]
    for pop in strata:
        key=pop['size_stratum'];count=group_samples[key]['records']
        for family in {v['family'] for v in families}:
            amount=sum(v['strata'].get(key,{}).get('bytes',0) for v in families if v['family']==family)
            estimate=amount/count*pop['records'];family_bytes+=estimate
            family_detail.append({'family':family,'size_stratum':key,'sample_bytes':amount,'estimated_permanent_bytes':estimate})
    ratios=[v for w in results for v in w['aux_ratios']];archives={};components=[]
    for policy in ('ALL','SELECTIVE'):
        selected=[v for v in metrics if v['policy']==policy]
        actual_container=sum(w['archives'][policy]['bytes'] for w in results)
        actual_frames=sum(v['input_frame_bytes']+v['raw_frame_bytes']+v['metadata_frame_bytes'] for v in selected)
        overhead_per_row=(actual_container-actual_frames)/len(selected)
        estimate=0;unknown=[]
        for pop in strata:
            key=pop['size_stratum'];ns=group_samples[key]['records'];nm=group_samples[key]['molecules']
            for task in A.CALC_TYPES:
                rows=[r for r in selected if r['size_stratum']==key and r['calc_type']==task]
                normal=sum(r['input_frame_bytes']+r['metadata_frame_bytes']+overhead_per_row for r in rows)*pop['records']/ns
                if policy=='ALL':out=sum(r['raw_frame_bytes'] for r in rows)*pop['records']/ns
                else:
                    out=sum(r['raw_frame_bytes'] for r in rows if r['retention_reason']=='SUCCESS_MOLECULAR_MINIMUM')*pop['molecules']/nm
                    out+=sum(r['raw_frame_bytes'] for r in rows if r['retention_reason']!='SUCCESS_MOLECULAR_MINIMUM')*pop['records']/ns
                aux_sample=[r for r in ratios if r['calc_type']==task and r['size_stratum']==key]
                global_aux=[r for r in ratios if r['calc_type']==task]
                aux_ratio=max((r['ratio'] for r in aux_sample or global_aux),default=None)
                missing_aux=0;aux_metadata=0
                for row in rows:
                    if row['missing_aux_raw_bytes'] is None:unknown.append({'calc_type':task,'size_stratum':key,'reason':'Aux size unavailable'})
                    elif row['output_retained'] and row['missing_aux_raw_bytes']:
                        weight=pop['molecules']/nm if row['retention_reason']=='SUCCESS_MOLECULAR_MINIMUM' else pop['records']/ns
                        if aux_ratio is None:unknown.append({'calc_type':task,'size_stratum':key,'reason':'No real AUX dict-compression sample'})
                        else:
                            missing_aux+=row['missing_aux_raw_bytes']*aux_ratio*weight
                            aux_metadata+=1024*weight # explicit uncompressed metadata/header reserve per unavailable real AUX
                part=normal+out+missing_aux+aux_metadata;estimate+=part
                components.append({'policy':policy,'calc_type':task,'size_stratum':key,'input_metadata_SQLite_bytes':normal,
                    'legacy_measured_outputs_bytes':out,'missing_AUX_calibrated_bytes':missing_aux,
                    'missing_AUX_metadata_upper_reserve_bytes':aux_metadata,'AUX_calibration_n':len(aux_sample),
                    'AUX_global_task_fallback':not aux_sample and bool(global_aux),'AUX_upper_ratio':aux_ratio})
        archives[policy]={'estimated_archive_bytes_known_plus_AUX_upper':estimate,'unknown_AUX_measurements':unknown,
            'SQLite_overhead_measured_bytes_per_row':overhead_per_row,
            'unclassified_scratch_bytes_are_NOT_assumed_zero':True}
    # Additional scientific JSON/FOD/gradient/D4 raw were not routinely in old archives.
    # Their sizes/overlap with excluded binary caches must be supplied by actualG6.
    context=read(temporary_path) if temporary_path and Path(temporary_path).is_file() else None
    quota=read(quota_path) if quota_path and Path(quota_path).is_file() else None
    free=(quota or {}).get('quota_parsed',{}).get('remaining_bytes')
    if free is None:free=(quota or {}).get('remaining_bytes')
    result.update(formal_records=records,formal_molecules=molecules,permanent_family_parquet_float64_bytes=family_bytes,
        permanent_family_components=family_detail,archive_components=components,archive_models=archives,
        future_float32_export_reserve_bytes=400_000_000_000,quota_remaining_bytes=free,
        dictionary_manifest_reference=benchmark['dictionary_manifest'],
        limits='Actual legacy raw+reconstructed input; retained AUX learned from real1% samples. Unstored side outputs need actualG6 file-scope measurements. No old600GB training-wire or second fullP payload added.')
    if context is None or free is None:return result
    needed=('base_temporary_reserve_bytes','simultaneous_staging_bytes','simultaneous_consolidation_extra_bytes','pending_parquet_duplicate_bytes','remaining_tests_not_in_quota_bytes','unarchived_scientific_outputs_by_policy')
    if any(k not in context for k in needed):result['missing_temporary_fields']=[k for k in needed if k not in context];return result
    if not context.get('raw_scope_coverage_complete'):
        result['status']='PENDING_G6_SCIENTIFIC_RAW_SCOPE_COVERAGE';return result
    temp=sum(context[k] for k in needed[:-1])
    extra=context['unarchived_scientific_outputs_by_policy'];plans=[]
    shared=Path(benchmark['dictionary_manifest']['path']).parent
    shared_bytes=sum(p.stat().st_size for p in shared.iterdir() if p.is_file())
    for policy in ('ALL','SELECTIVE'):
        model=archives[policy]
        if model['unknown_AUX_measurements']:continue
        peak=family_bytes+model['estimated_archive_bytes_known_plus_AUX_upper']+extra[policy]+shared_bytes+400_000_000_000+temp
        plans.append({'policy':policy,'projected_writeback_peak_bytes':peak,'headroom_bytes':free-peak,'headroom_GB_decimal':(free-peak)/1e9})
    result['plans']=plans;result['temporary_context']=context
    candidates={p['policy']:p for p in plans}
    if candidates.get('ALL',{}).get('headroom_bytes',-1)>=200_000_000_000:choice='ALL'
    elif candidates.get('SELECTIVE',{}).get('headroom_bytes',-1)>=200_000_000_000:choice='SELECTIVE'
    else:choice=None
    result.update(policy_selected=choice,status='G3_PASS' if choice else 'G3_STOP_BOTH_POLICIES_BELOW200GB_OR_INCOMPLETE')
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    parser.add_argument('--workers',type=int,default=16);parser.add_argument('--pilot-root',default=str(OLD/'wp4_native_full_v4'))
    parser.add_argument('--panel',default=str(OLD/'wp4_native_panel/pilot_panel.parquet'))
    parser.add_argument('--formal-index',default=str(ROOT/'population/formal_record_index.parquet'))
    parser.add_argument('--geometry',default=str(SCREEN/'c_engineering/xyz/analysis_geometry.parquet'))
    parser.add_argument('--registry',default=str(SCREEN/'reports/label_registry_v2.json'))
    parser.add_argument('--config');parser.add_argument('--legacy-config',default=str(OLD/'scripts/wp4_native_v4_config.json'));parser.add_argument('--population');parser.add_argument('--quota',default=str(ROOT/'gates/g1_g2_initial.json'))
    parser.add_argument('--temporary-model');parser.add_argument('--output');parser.add_argument('--scratch-base',default='/tmp')
    parser.add_argument('--finalize',help='Existing G3 benchmark JSON; metadata projection only, no raw/science rerun')
    args=parser.parse_args()
    if args.check:
        for p in (Path(__file__),Path(A.__file__)):ast.parse(p.read_text())
        print(json.dumps({'status':'AST_PASS','LMDB_created':False,'QM_started':False}));return 0
    if args.finalize:
        benchmark=read(args.finalize);model=projection(benchmark,args.population,args.quota,args.temporary_model)
        target=own(args.output or str(Path(args.finalize).parent/'projection.json'));save(target,model)
        print(json.dumps({'status':model['status'],'policy_selected':model['policy_selected']}));return 0
    if args.workers<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<args.workers:raise ValueError('>=16 allocated actual workers required')
    if socket.gethostname().split('.')[0] not in {f'compute-0-{n}' for n in range(14,20)}:raise ValueError('WP5 only compute14..19')
    job=os.environ['SLURM_JOB_ID'];out=own(args.output or str(ROOT/'gates/g3'/f'job_{job}'))
    if out.exists():raise FileExistsError('Fresh own G3 output required')
    out.mkdir(parents=True);dictionary_root=own(ROOT/'dictionaries'/f'job_{job}');dictionary_root.mkdir()
    config=read(args.config) if args.config else read(SCREEN/'scripts/c_engineering_native_nopolar_config.json')
    config['tasks']=[t for t in config['tasks'] if t['name'] in A.CALC_TYPES];config.pop('hessian_task',None)
    if len(config['tasks'])!=12:raise ValueError('NoPOLAR/ESP/Hess frozen12 config required')
    config_path=out/'formal_input_recipe_snapshot.json';save(config_path,config)
    legacy_path=out/'historical_reconstructed_input_recipe_snapshot.json';save(legacy_path,read(args.legacy_config))
    panel,sources=discover(args.pilot_root,args.panel);sample_strata={}
    context_path=out/'formal_pilot_source_context.parquet'
    formal_context=formal_sample_context(args.panel,args.formal_index,context_path,args.workers)
    for source in sources:
        maxima={formal_context[rid]['molecule_max_heavy_atoms'] for rid in source['record_ids']}
        if len(maxima)!=1:raise ValueError('Formal sample molecule max-heavy varies between rows')
        n=next(iter(maxima));source['legacy_size_stratum']=source['size_stratum']
        source['size_stratum']=next(key for cutoff,key in ((10,'0_10'),(20,'11_20'),(30,'21_30'),(50,'31_50'),(75,'51_75'),(100,'76_100'),(float('inf'),'above_100')) if n<=cutoff)
    for key in {s['size_stratum'] for s in sources}:
        subset=[s for s in sources if s['size_stratum']==key]
        sample_strata[key]={'records':sum(len(s['record_ids']) for s in subset),'molecules':len(subset)}
    chunks=[sources[i::args.workers] for i in range(args.workers)]
    local=Path(tempfile.mkdtemp(prefix=f'wp5_g3_{os.getuid()}_{job}_',dir=args.scratch_base));start=time.monotonic()
    context=multiprocessing.get_context('spawn');barrier=context.Barrier(args.workers)
    initargs=(str(config_path),str(legacy_path),args.geometry,str(context_path),args.registry,barrier)
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,initializer=initialize,initargs=initargs) as pool:
        trained_sources=list(pool.map(train_reader,[(i,v,str(local)) for i,v in enumerate(chunks)],chunksize=1))
        readers=sorted({v['worker_pid'] for v in trained_sources})
        if len(readers)<16 or sum(v['source_rows'] for v in trained_sources)!=120240:raise ValueError('Actual16 pilot readers/count closure failed')
        training_jobs=[(t,[v['paths'][t] for v in trained_sources],str(dictionary_root)) for t in A.CALC_TYPES]
        dictionaries=list(pool.map(train_dictionary,training_jobs,chunksize=1))
        manifest=dictionary_root/'dictionary_manifest.json'
        save(manifest,{'scope':'WP5_FROZEN12_DICTS_FROM_ALL_PILOT_RAW','source_records':10020,'source_molecules':1441,
            'source_requested_calc_rows':120240,'source_readers':readers,'source_config_sha256':sha(legacy_path),'formal_config_sha256':sha(config_path),
            'dictionaries':dictionaries,'source_corpus_bindings':sources})
        workers=list(pool.map(benchmark_reader,[(i,v,str(out),str(manifest),str(config_path)) for i,v in enumerate(chunks)],chunksize=1))
    pids=sorted({v['worker_pid'] for v in workers})
    if len(pids)<16:raise ValueError('Fewer than16 actual archive/family benchmark workers')
    consolidated={}
    for policy in ('ALL','SELECTIVE'):
        consolidated[policy]=A.consolidate_archives([v['archives'][policy]['path'] for v in workers],out/(policy+'_consolidated.sqlite'),manifest,config_path,policy=policy)
    report={'status':'G3_ALL_PILOT12_ARCHIVE_AND_FAMILY_BENCHMARK_CLOSED','records':10020,'molecules':1441,'calc_rows':120240,
        'actual_reader_pids':readers,'actual_benchmark_worker_pids':pids,'dictionary_manifest':{'path':str(manifest),'sha256':sha(manifest)},
        'sample_strata':sample_strata,'workers':workers,'consolidated':consolidated,'seconds':time.monotonic()-start,
        'source_input_origin':'RECONSTRUCTED_INPUT_NOT_HISTORICAL_ORIGINAL','historical_input_recipe':{'path':str(legacy_path),'sha256':sha(legacy_path)},
        'formal_inputs_size_model':'Historical exact input recipe is a conservative proxy; PM7 B keeps historical POLAR only in reconstructed legacy input, not formal compute/parquet','scientific_raw_scope_complete':False,
        'scope_limit':'Old archives lacked most AUX and xTB side files; counted/calibrated explicitly before final policy selection.',
        'formal_sample_context':{'path':str(context_path),'sha256':sha(context_path),'records':10020},
        'family_float64_bit_and_row_roundtrip':'PASS','verified_family_rows':sum(v['verified_typed_family_rows'] for v in workers),
        'schema_source':{'path':str(ROOT/'scripts/wp5_parquet.py'),'sha256':sha(ROOT/'scripts/wp5_parquet.py')},
        'archive_source_sha256':sha(A.__file__),'script_sha256':sha(__file__),'LMDB_created':False,
        'original_LMDB_readonly_for_D20_D3':True,'QM_started':False,'source_files_deleted':False}
    path=out/'benchmark.json';save(path,report)
    save(out/'projection.json',projection(report,args.population,args.quota,args.temporary_model))
    # Only exact owned local training-segment files are temporary; no shared/history removal.
    if local.name.startswith(f'wp5_g3_{os.getuid()}_{job}_') and local.parent==Path(args.scratch_base).absolute():shutil.rmtree(local)
    print(json.dumps({'status':report['status'],'path':str(path),'workers':len(pids),'calc_rows':120240}));return 0
if __name__=='__main__':raise SystemExit(main())
