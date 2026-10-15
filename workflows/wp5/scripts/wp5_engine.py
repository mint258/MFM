#!/usr/bin/env python3
"""WP5 whole-molecule engine, read-only source and twelve independent tasks.

The pinned v4 invoke lifecycle is reused without editing its frozen file. All
per-call files are captured before verified local scratch cleanup. The caller
owns lane containers, complete-molecule transactions and checkpoint commits.
"""
from __future__ import annotations
import argparse, ast, atexit, hashlib, importlib.util, json, math, os, pickle
from pathlib import Path
import re, stat, sys, tempfile, threading, time
sys.dont_write_bytecode=True
HERE=Path(__file__).absolute().parent
DEFAULT_PROTOCOL=HERE.parent/'configs/protocol.json'
TASK_NAMES=('pm7_B','pm7_water','pm7_octanol','pm7_cation','pm7_anion','xtb_singlepoint','xtb_vipea','xtb_vfukui','xtb_ALPB_water','xtb_ALPB_octanol','xtb_fod','xtb_perturbed_gradient')
CONFIG=NATIVE=PARSER=WIRE=REGISTRY=None
DESCRIPTOR_FN=None
WORK=None
CAPTURED=None
CAPTURE_ERROR=None

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def stable_sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def pinned_module(name,entry):
    path=Path(entry['path'])
    if sha(path)!=entry['sha256']:raise ValueError('FROZEN_SOURCE_CHANGED:'+name)
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def load_protocol(protocol=None):
    config=json.loads(Path(protocol or DEFAULT_PROTOCOL).read_text()) if not isinstance(protocol,dict) else dict(protocol)
    if tuple(task['name'] for task in config['tasks'])!=TASK_NAMES:raise ValueError('WP5_TWELVE_TASK_ORDER_MISMATCH')
    for task in config['tasks']:
        if task['family']=='mopac' and ('1SCF' not in task['keywords'] or 'POLAR' in task['keywords'] or 'ESP' in task['keywords']):raise ValueError('WP5_MOPAC_KEYWORD_SCOPE')
        if task['family']=='xtb' and any(word in task['args'] for word in ('--opt','--ohess','--hess')):raise ValueError('WP5_GEOMETRY_OPTIMIZATION_FORBIDDEN')
    return config

def source_list(plan):
    if isinstance(plan,(str,Path)):plan=json.loads(Path(plan).read_text())
    if isinstance(plan,list):return plan
    if 'sources' in plan:return plan['sources']
    found={int(shard['shard_id']):shard for manifest in plan.get('manifests',{}).values() for shard in manifest.get('shards',[])}
    return [found[index] for index in sorted(found)]

def initialize_worker(source_plan,protocol=None,node_scratch_root='/tmp',registry_sha=None,stop_event=None,deadline=None,descriptor_fn=None):
    global CONFIG,NATIVE,PARSER,WIRE,REGISTRY,DESCRIPTOR_FN,WORK
    CONFIG=load_protocol(protocol);deps=CONFIG['frozen_dependencies']
    scratch=Path(node_scratch_root).absolute()
    if str(scratch).startswith(('/share/','/home/')) or not scratch.is_dir():raise ValueError('NODE_LOCAL_SCRATCH_REQUIRED')
    CONFIG['scratch_base']=str(scratch)
    NATIVE=pinned_module('wp5_frozen_native_lifecycle',deps['native_lifecycle'])
    os.environ.update(NATIVE.THREAD_ENV);os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch,pyarrow as pa
    torch.set_num_threads(1);pa.set_cpu_count(1);pa.set_io_thread_count(1)
    if not os.environ.get('SLURM_JOB_ID'):raise ValueError('QM_ENGINE_REQUIRES_SLURM_JOB')
    spec=importlib.util.spec_from_file_location('wp5_active_parser',HERE/'wp5_parser.py');PARSER=importlib.util.module_from_spec(spec);spec.loader.exec_module(PARSER)
    NATIVE.MULLIKEN=pinned_module('wp5_frozen_mulliken',deps['mulliken'])
    WIRE=pinned_module('wp5_frozen_D20_D3',deps['D20_D3']);WIRE.metadata()
    registry=CONFIG['registry']
    if sha(registry['path'])!=registry['sha256'] or (registry_sha and registry_sha!=registry['sha256']):raise ValueError('REGISTRY_SHA_DIFFERS')
    REGISTRY=json.loads(Path(registry['path']).read_text())['entries']
    sources=source_list(source_plan)
    if len(sources)!=11 or {int(item['shard_id']) for item in sources}!=set(range(11)):raise ValueError('ORIGINAL_ELEVEN_LMDB_SOURCES_REQUIRED')
    NATIVE.SOURCES={int(item['shard_id']):item for item in sources};NATIVE.CONFIG=CONFIG;NATIVE.PARSER=PARSER
    NATIVE.DEADLINE=float(deadline or time.time()+47*3600);NATIVE.STOP_EVENT=stop_event or threading.Event()
    WORK=Path(tempfile.mkdtemp(prefix=f'wp5engine_{os.getuid()}_{os.environ["SLURM_JOB_ID"]}_{os.getpid()}_',dir=scratch))
    NATIVE.OUTPUT=WORK
    # Preserve the exact reader while retaining its already-decoded payload for
    # D20/D3. This is an explicit derivation, not a change to historical source.
    source=Path(deps['native_lifecycle']['path']).read_text()
    section=source[source.index('def read_native(row):'):source.index('\ndef cleanup_scratch(path):')]
    old='return {"symbols":symbols,'
    if section.count(old)!=1:raise ValueError('PINNED_READER_RETURN_DERIVATION_MISMATCH')
    exec(compile(section.replace(old,'return {"_source_raw":raw,"symbols":symbols,'),'<WP5_pinned_reader_add_decoded_payload>','exec'),NATIVE.__dict__)
    NATIVE.output_archive=_capture_archive
    original_cleanup=NATIVE.cleanup_scratch
    def capture_before_cleanup(path):
        global CAPTURE_ERROR
        if CAPTURED is None:
            try:_capture_files(Path(path))
            except Exception as exc:CAPTURE_ERROR=exc
        return original_cleanup(path)
    NATIVE.cleanup_scratch=capture_before_cleanup
    DESCRIPTOR_FN=descriptor_fn or default_descriptors
    atexit.register(NATIVE.close_handles)
    atexit.register(_cleanup_work)

def _cleanup_work():
    if WORK and WORK.exists():
        import shutil
        if WORK.parent!=Path(CONFIG['scratch_base']) or not WORK.name.startswith(f'wp5engine_{os.getuid()}_'):return
        if any(item.lstat().st_uid!=os.getuid() or not (stat.S_ISREG(item.lstat().st_mode) or stat.S_ISDIR(item.lstat().st_mode)) for item in [WORK,*WORK.rglob('*')]):return
        shutil.rmtree(WORK)

def close_worker():
    """Explicit multiprocessing finally hook; do not rely on atexit/os._exit."""
    before=str(WORK) if WORK else None
    if NATIVE is not None:NATIVE.close_handles()
    _cleanup_work()
    return {'worker_pid':os.getpid(),'local_work_root':before,'work_root_removed':not WORK or not WORK.exists(),'LMDB_handles_closed':not NATIVE or not NATIVE.HANDLES}
def _capture_files(directory):
    global CAPTURED
    files=[]
    for path in sorted(directory.iterdir()):
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid():raise ValueError('RAW_CAPTURE_NONREGULAR_OR_OWNER:'+path.name)
        data=path.read_bytes()
        files.append({'name':path.name,'byte_count':len(data),'sha256':hashlib.sha256(data).hexdigest(),'data':data,'role':'input' if path.name in ('input.xyz','input.mop','native.inp') else 'output'})
    CAPTURED=files
    return files

def _capture_archive(paths,target,member_prefix):
    global CAPTURE_ERROR
    try:
        if not paths:raise ValueError('RAW_CAPTURE_WITHOUT_SOURCE_DIRECTORY')
        files=_capture_files(Path(paths[0]).parent)
        # Extend the audited invoke's bookkeeping to every actual file; no tar
        # is written and no per-call shared path is created.
        paths[:]=[Path(paths[0]).parent/item['name'] for item in files]
        return {'storage':'WP5_LANE_CONTAINER_HOOK','bytes':sum(item['byte_count'] for item in files),'sha256':stable_sha([(item['name'],item['sha256']) for item in files])}
    except Exception as exc:CAPTURE_ERROR=exc;raise

def perturb_seed(record_id,config):return 1+int(hashlib.sha256((str(config['seed'])+'|'+record_id).encode()).hexdigest()[:16],16)%2147483646

def render_inputs(task,native,row,protocol=None):
    """Pure exact pilot-format input bytes; caller labels reconstruction origin."""
    import numpy as np
    config=protocol or CONFIG or load_protocol()
    if isinstance(task,str):task=next(item for item in config['tasks'] if item['name']==task)
    symbols=native['symbols'];coords=np.asarray(native['coords'],dtype=np.float64)
    seed=perturb_seed(row['record_id'],config)
    if task.get('perturbed'):coords=coords+np.random.default_rng(seed).normal(0,config['perturb_sigma_A'],coords.shape)
    text=str(len(symbols))+'\nWP4 native geometry; coordinates Angstrom; '+row['record_id']+'\n'
    text+='\n'.join(f'{s} {x:.12f} {y:.12f} {z:.12f}' for s,(x,y,z) in zip(symbols,coords))+'\n'
    result={'input.xyz':text.encode()}
    if task['family']=='mopac':
        mop=task['keywords']+' THREADS=1\n'+row['record_id']+'\nStored native PM7 coordinates; single point, no optimization\n'
        mop+='\n'.join(f'{s} {x:.12f} 1 {y:.12f} 1 {z:.12f} 1' for s,(x,y,z) in zip(symbols,coords))+'\n'
        result['input.mop']=mop.encode()
    else:result['native.inp']=task.get('xcontrol','$write\n json=true\n$end\n').encode()
    return result

def validate_atomic_arrays(detail,z_or_natoms):
    """Requested-scope shape, finiteness and actual index/order constraints."""
    import numpy as np
    n=int(z_or_natoms) if isinstance(z_or_natoms,int) else len(z_or_natoms)
    values=detail.get('values',detail);issues=[]
    def issue(key,reason):issues.append(key+':'+reason)
    one={'net_charges_e','mulliken_charges_e','esp_charges_e','atomic_shell_population_e','charges_e','D4_atomic_C6_au','D4_atomic_alpha_bohr3','FOD_atom_e'}
    for key in one:
        value=values.get(key)
        if value is not None and value!=[] and len(value)!=n:issue(key,'ATOM_COUNT')
    for key in ('forces_eV_A','positions_A','fukui'):
        value=values.get(key)
        if value is not None and value!=[] and np.asarray(value).shape!=(n,3):issue(key,'EXPECTED_N_BY_3')
    for key in ('gradient_Eh_bohr','gradient_kcal_mol_A'):
        value=values.get(key)
        if value is not None and value!=[] and np.asarray(value).shape not in ((3*n,),(n,3)):issue(key,'EXPECTED_3N_OR_N_BY_3')
    symbols=values.get('elements')
    if symbols:
        if len(symbols)!=n:issue('elements','ATOM_COUNT')
        elif not isinstance(z_or_natoms,int):
            from rdkit import Chem
            expected=[Chem.GetPeriodicTable().GetElementSymbol(int(z)) for z in z_or_natoms]
            if symbols!=expected:issue('elements','NATIVE_ATOM_ORDER')
    def walk(value,path):
        if isinstance(value,float) and not math.isfinite(value):issue(path,'NONFINITE')
        elif isinstance(value,dict):
            for key,item in value.items():walk(item,path+'.'+key)
        elif isinstance(value,(list,tuple)):
            for index,item in enumerate(value):walk(item,path+'['+str(index)+']')
    walk(values,'values')
    for key in ('bond_orders','enpart_pairs_eV','mulliken_overlap_population_pairs','wiberg_pairs'):
        for pair in values.get(key) or []:
            for index_key in ('i','j','atom_i','atom_j'):
                if index_key in pair and (type(pair[index_key]) is not int or not 0<=pair[index_key]<n):issue(key,'PAIR_INDEX_RANGE')
    for pair in values.get('sigma_pi_entries') or []:
        if any(type(pair.get(key)) is not int or not 0<=pair[key]<n for key in ('atom_i','atom_j')):issue('sigma_pi_entries','ATOM_INDEX_RANGE')
    for key in ('super_heavy_atom_rows','enpart_one_center_eV'):
        for item in values.get(key) or []:
            if not isinstance(item,dict) or type(item.get('atom_index')) is not int or not 0<=item['atom_index']<n:issue(key,'SPARSE_ATOM_INDEX_RANGE')
    return sorted(set(issues))

def source_bond_graph(raw,native):
    import numpy as np
    indices=NATIVE.raw_field(raw,'rdkit_bond_index');orders=NATIVE.raw_field(raw,'rdkit_bond_order')
    null={'bond_pairs':None,'bond_pairs_zero_based':None,'bond_order_codes':None,'stored_bond_graph_sha256':None}
    if indices is None or orders is None:return {**null,'bond_graph_issues':['SOURCE_BONDGRAPH_MISSING']}
    edges=np.asarray(NATIVE.plain(indices));codes=np.asarray(NATIVE.plain(orders)).reshape(-1)
    n=len(native['z'])
    if edges.ndim!=2 or edges.shape[0]!=2 or edges.shape[1]!=len(codes) or not np.isfinite(edges).all() or not np.equal(edges,np.floor(edges)).all() or not ((edges>=0)&(edges<n)).all() or not np.isfinite(codes).all() or not np.equal(codes,np.floor(codes)).all() or not ((codes>=1)&(codes<=5)).all():
        return {**null,'bond_graph_issues':['SOURCE_BONDGRAPH_INVALID']}
    graph={}
    for pair,code in zip(edges.T,codes):
        pair=tuple(sorted(map(int,pair)));code=int(code)
        if pair[0]==pair[1] or (pair in graph and graph[pair]!=code):return {**null,'bond_graph_issues':['SOURCE_BONDGRAPH_SELF_OR_CONFLICTING_DUPLICATE']}
        graph[pair]=code
    pairs=sorted(graph)
    return {'bond_pairs':[list(pair) for pair in pairs],'bond_pairs_zero_based':[list(pair) for pair in pairs],'bond_order_codes':[graph[pair] for pair in pairs],
            'stored_bond_graph_sha256':hashlib.sha256(edges.astype('<i8').tobytes()+codes.astype('<i8').tobytes()).hexdigest(),'bond_graph_issues':[]}
def default_descriptors(row,raw,native):
    import numpy as np
    corrected,issues=WIRE.corrected_base(raw,row)
    values=np.asarray(NATIVE.plain(WIRE.field(corrected,'rdkit_graph_desc')),dtype=np.float64).reshape(-1)
    mask_raw=WIRE.field(corrected,'rdkit_graph_desc_mask')
    mask=np.asarray(NATIVE.plain(mask_raw)).reshape(-1) if mask_raw is not None else np.isfinite(values)
    if len(mask)!=20:raise ValueError('D20_MASK_SHAPE')
    d20=[float(value) if bool(mask[index]) and math.isfinite(float(value)) else None for index,value in enumerate(values)]
    d3={key:(value.tolist() if isinstance(value,np.ndarray) else value) for key,value in WIRE.field(corrected,'D_native_3D').items()}
    if d3.get('SASA_atom_A2') is not None and len(d3['SASA_atom_A2'])!=len(native['z']):raise ValueError('D3_SASA_ATOM_COUNT')
    for key,value in d3.items():
        if isinstance(value,float) and not math.isfinite(value):d3[key]=None;issues.append(key+':NONFINITE')
    return {'rdkit_graph_desc':d20,'rdkit_graph_desc_mask':[value is not None for value in d20],'D20_names':list(WIRE.D20),'D_native_3D':d3,'descriptor_schema_ref':'C4_D20_D3D_REGISTRY_V1','issues':issues,'geometry_context':'native_original_PM7','native_atom_order_sha256':native['native_atom_order_sha256']}

def derived_quantities(tasks):
    by={item['task']:item for item in tasks}
    def get(name):
        item=by.get(name,{})
        return item.get('values',{}) if item.get('status')=='SUCCESS' or (name=='pm7_B' and item.get('B_base_success')) else {}
    neutral,plus,minus=get('pm7_B'),get('pm7_cation'),get('pm7_anion');derived={}
    if neutral.get('heat_of_formation_kcal_mol') is not None:
        e0=neutral['heat_of_formation_kcal_mol']
        if plus.get('heat_of_formation_kcal_mol') is not None:derived['vertical_IP_eV']=(plus['heat_of_formation_kcal_mol']-e0)/23.060548867
        if minus.get('heat_of_formation_kcal_mol') is not None:derived['vertical_EA_eV']=(e0-minus['heat_of_formation_kcal_mol'])/23.060548867
        for name in ('pm7_water','pm7_octanol'):
            solvent=get(name).get('heat_of_formation_kcal_mol')
            if solvent is not None:derived[name+'_HOF_difference_kcal_mol']=solvent-e0
    q0,qp,qm=neutral.get('net_charges_e'),plus.get('net_charges_e'),minus.get('net_charges_e')
    if q0 and qp and qm and len(q0)==len(qp)==len(qm):derived['fukui_Coulson']={'plus':[a-b for a,b in zip(q0,qm)],'minus':[b-a for a,b in zip(q0,qp)],'radical':[(b-c)/2 for b,c in zip(qp,qm)]}
    if 'pm7_B' in by:by['pm7_B'].setdefault('values',{})['derived_from_same_geometry_charged_states']=derived

def raw_record(task,row,result,files):
    keywords=task.get('keywords',task.get('args'))
    if task['family']=='mopac':keywords=keywords+' THREADS=1'
    raw={'record_id':row['record_id'],'molecule_id':row['molecule_id'],'calc_type':task['name'],'source_payload_sha256':row['record_payload_sha256'],
         'software':{'family':task['family'],'version':CONFIG['expected_versions'][task['family']]},'keywords':keywords,'keywordSHA':stable_sha(keywords),
         'source_status':result['source_status'],'scope_status':result['scope_status'],'is_minimum':bool(row.get('molecule_lowest_energy_conformer',False)),
         'input_origin':'ORIGINAL','source_reference':{'shard_id':row['shard_id'],'real_index':row.get('real_index',row.get('source_record_index'))},'files':files}
    if not any(item['role']=='input' for item in files):raw['input_missing_reason']=result.get('failure_reason') or result.get('failure_code') or 'CALL_NOT_LAUNCHED'
    return raw

def compute_molecule(rows,raw_sink=None,descriptor_fn=None,hard_deadline_monotonic=None):
    global CAPTURED,CAPTURE_ERROR
    if NATIVE is None:raise RuntimeError('INITIALIZE_WORKER_REQUIRED')
    if not rows or len({row['molecule_id'] for row in rows})!=1:raise ValueError('WHOLE_MOLECULE_ROWS_REQUIRED')
    molecule_id=rows[0]['molecule_id'];records=[];raws=[];start=time.monotonic()
    for row in rows:
        if hard_deadline_monotonic is not None:NATIVE.DEADLINE=min(NATIVE.DEADLINE,time.time()+hard_deadline_monotonic-time.monotonic())
        if NATIVE.STOP_EVENT.is_set() or time.time()>=NATIVE.DEADLINE-30:return {'molecule_id':molecule_id,'status':'PARTIAL_DEADLINE','record_results':records,'raw_records':raws,'worker_pid':os.getpid()}
        native=None;source_error=None
        try:native=NATIVE.read_native(row)
        except Exception as exc:source_error=f'{type(exc).__name__}: {exc}'
        record={'record_id':row['record_id'],'molecule_id':molecule_id,'source_row':row,'old_energy_kcal_mol':native['energy'] if native else row.get('energy_raw'),'base_geometry':None,'tasks':[],'descriptors':None}
        if native:
            record['base_geometry']={'z':native['z'].tolist(),'positions_A':native['coords'].tolist(),'native_coordinates_sha256':native['native_coordinates_sha256'],'native_atom_order_sha256':native['native_atom_order_sha256'],'source_payload_sha256':row['record_payload_sha256']}
            record['base_geometry'].update(source_bond_graph(native['_source_raw'],native))
            try:record['descriptors']=(descriptor_fn or DESCRIPTOR_FN)(row,native['_source_raw'],native)
            except Exception as exc:record['descriptors']={'status':'DESCRIPTOR_FAILED','issues':[f'{type(exc).__name__}: {exc}'],'rdkit_graph_desc':None,'D_native_3D':None}
        for task in CONFIG['tasks']:
            if NATIVE.STOP_EVENT.is_set() or time.time()>=NATIVE.DEADLINE-30:return {'molecule_id':molecule_id,'status':'PARTIAL_DEADLINE','record_results':records+[record],'raw_records':raws,'worker_pid':os.getpid()}
            CAPTURED=None;CAPTURE_ERROR=None
            if native is None:
                result=NATIVE.skipped(row,None,task,'Q03_SOURCE_READ_FAILED');result['failure_reason']=source_error
            else:result=NATIVE.invoke(task,native,row,WORK)
            if CAPTURE_ERROR is not None:raise RuntimeError('RAW_CAPTURE_FAILED:'+str(CAPTURE_ERROR)) from CAPTURE_ERROR
            if result['status'] in NATIVE.UNFINISHED:return {'molecule_id':molecule_id,'status':'PARTIAL_DEADLINE','record_results':records+[record],'raw_records':raws,'worker_pid':os.getpid()}
            result['source_status']=result['status']
            result['atomic_array_validation']=validate_atomic_arrays(result,native['z']) if native else []
            if result['atomic_array_validation'] and result['status']=='SUCCESS':result.update(status='PROPERTY_FAILED',failure_code='REQUESTED_SCOPE_ATOMIC_ARRAY_QC_FAILED',failure_reason=' | '.join(result['atomic_array_validation']))
            result['scope_status']=result['status'];result['parser_context']=PARSER.context() if native else {}
            files=CAPTURED or []
            raw=raw_record(task,row,result,files)
            if raw_sink is None:raws.append(raw)
            else:result['raw_ref']=raw_sink(raw)
            result['archive']=result.get('raw_ref',result.get('archive'));record['tasks'].append(result)
            CAPTURED=None
        derived_quantities(record['tasks']);records.append(record)
    return {'molecule_id':molecule_id,'status':'COMPLETE_WITH_RECORDED_OUTCOMES','record_results':records,'raw_records':raws,'worker_pid':os.getpid(),'record_count':len(records),'requested_outcomes':sum(len(item['tasks']) for item in records),'elapsed_seconds':time.monotonic()-start}

def check():
    ast.parse(Path(__file__).read_text());config=load_protocol()
    parser=pinned_module('wp5_check_parser',{'path':str(HERE/'wp5_parser.py'),'sha256':sha(HERE/'wp5_parser.py')});parser.check()
    import numpy as np
    native={'symbols':['C','H'],'coords':np.asarray([[0.,0.,0.],[1.,0.,0.]])};row={'record_id':'check'}
    first=render_inputs(config['tasks'][-1],native,row,config);second=render_inputs(config['tasks'][-1],native,row,config)
    assert first==second and native['coords'][1,0]==1.
    assert validate_atomic_arrays({'values':{'fukui':[[1.,2.,3.],[1.,2.,3.]]}},2)==[]
    assert validate_atomic_arrays({'values':{'D4_atomic_C6_au':[1.,2.],'D4_atomic_alpha_bohr3':[3.,4.]}},2)==[]
    print(json.dumps({'status':'WP5_ENGINE_STATIC_INPUT_AND_ATOMIC_QC_PASS','QM_started':False,'LMDB_opened':False,'tasks':TASK_NAMES}))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
    if args.check:check()
