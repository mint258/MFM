"""B2/B4/B5/B6 immutable native-pilot analysis; no new QM or source writes."""
from __future__ import annotations
import argparse,collections,concurrent.futures,hashlib,json,math,multiprocessing,os,re,subprocess,sys,tarfile,time
from pathlib import Path
OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
sys.path.insert(0,'/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps')
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
GEOMS={};POLAR_IDS=set()
QC={'normal_end','property_failure_lines','parse_errors','warnings','mulliken_overlap_qc','mulliken_reconstruction_charge_max_error_e','max_antisymmetric_component_bohr3','negative_frequency_count_raw','imaginary_frequency_count_below_minus20','gradient_norm_kcal_mol_A','spin_Sz','spin_S2'}
PROV={'method','version','positions_A','elements','perturb_seed','perturb_sigma_A','ao_atom_index_1based','ao_types'}
SPECIAL_UNITS={'gradient_kcal_mol_A':'kcal mol^-1 A^-1','gradient_Eh_bohr':'Eh bohr^-1','forces_eV_A':'eV A^-1','frequencies_cm_inverse':'cm^-1','IR_km_mol':'km mol^-1','thermo_tot_H_cal_mol_Cp_cal_mol_K_S_cal_mol_K_S_J_mol_K':'[cal/mol,cal/mol/K,cal/mol/K,J/mol/K]','sigma_pi_entries':'bond-order population','valences':'bond-order population','bond_orders':'bond-order population','wiberg_pairs':'bond-order population','spin_S2':'dimensionless','spin_Sz':'dimensionless'}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda:stream.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def save(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.with_suffix(path.suffix+'.pending').write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    path.with_suffix(path.suffix+'.pending').replace(path)
def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def present(v):
    if v is None:return False
    if isinstance(v,(list,dict)):return bool(v)
    if isinstance(v,float):return math.isfinite(v)
    return True
def fields(values,prefix='values'):
    for key,v in values.items():
        path=prefix+'.'+key
        if key=='derived_from_same_geometry_charged_states' and isinstance(v,dict):
            for k,x in v.items():
                if k=='fukui_Coulson' and isinstance(x,dict):
                    for sub,y in x.items():yield path+'.'+k+'.'+sub,y
                else:yield path+'.'+k,x
        elif key=='static_polar_block' and isinstance(v,dict):
            for k,x in v.items():yield path+'.'+k,x
        else:yield path,v

def classify(path):
    key=path.split('.')[-1]
    if key in QC:return 'QC'
    if key in PROV:return 'provenance'
    return 'physical_label'
def unit(path):
    key=path.split('.')[-1]
    if key in SPECIAL_UNITS:return SPECIAL_UNITS[key]
    for suffix,u in [('kcal_mol','kcal/mol'),('eV','eV'),('Eh','Eh'),('bohr3','bohr^3'),('A3','A^3'),('A2','A^2'),('Debye','Debye'),('_au','atomic units'),('_e','e')]:
        if key.endswith(suffix):return u
    if 'fukui' in path:return 'e'
    if key in ('frequency_eV',):return 'eV'
    if key in ('polar_blocks','static_polar_block','STATIC_finite_field_tensors_bohr3'):return 'bohr^3 (tensor); compound metadata explicitly retained'
    return 'dimensionless or compound; see source field'
def level(path):
    key=path.split('.')[-1]
    if 'pairs' in key or key in ('bond_orders','sigma_pi_entries'):return 'sparse_atom_pair'
    if any(s in key for s in ('charges','atomic','FOD_atom','fukui','valences','shell','one_center','heavy_atom_rows')):return 'atom'
    if key in ('gradient_Eh_bohr','forces_eV_A','gradient_kcal_mol_A'):return 'atom_vector'
    if 'dipole' in key:return 'molecule_vector'
    if any(s in key for s in ('tensor','quadrupole','polar_block')):return 'molecule_tensor'
    if 'frequencies' in key or 'IR_' in key:return 'vibrational_mode'
    return 'molecule'
def entry(task,path):
    key=path.split('.')[-1]
    charge='+1' if task=='pm7_cation' else '-1' if task=='pm7_anion' else '0'
    method='PM7' if task.startswith('pm7_') else 'GFN1-xTB' if task=='xtb_vipea' else 'GFN2-xTB'
    context='water' if 'water' in task else 'octanol' if 'octanol' in task else 'gas'
    derived=[];dedup=None;notes=[]
    if 'derived_from_same_geometry_charged_states' in path:derived=['pm7_B.values.heat_of_formation_kcal_mol','pm7_cation.values.heat_of_formation_kcal_mol','pm7_anion.values.heat_of_formation_kcal_mol','corresponding stored net_charges_e or solvent HOF as formula requires']
    if key=='forces_eV_A':derived=['xtb_perturbed_gradient.values.gradient_Eh_bohr']
    if key=='average_A3':derived=[task+'.values.static_polar_block.average_bohr3']
    if key=='average_bohr3':derived=[task+'.values.static_polar_block.tensor_bohr3']
    if 'static_polar_block.' in path:dedup=task+'.values.polar_blocks[frequency_eV=0].'+key
    excluded='polar' in path.lower() or 'STATIC_finite_field' in path
    if excluded:notes.append('POLAR asymmetry diagnostic retained; excluded from trusted candidate labels after B2 confirmation.')
    if task=='xtb_perturbed_gradient':notes.append('Random perturbation sensitivity includes seeded noise, not solely native-conformer sensitivity.')
    return {'task':task,'source_path':path,'canonical_target':method+'.charge'+charge+'.'+context+'.'+key,'level':level(path),'unit':unit(path),'classification':classify(path),'derived_from':derived,'dedup_of':dedup,'excluded':excluded,'method':method,'charge':int(charge),'context':context,'notes':notes}

def init(geoms,polar_ids,barrier):
    global GEOMS,POLAR_IDS
    import numpy as np,pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);GEOMS=geoms;POLAR_IDS=set(polar_ids);barrier.wait(timeout=120)

def feature(v,path,geom):
    """Invariant tensor summaries; site-wise arrays only after native graph/order checks."""
    import numpy as np
    if finite(v):return {'scalar':float(v)}
    if not isinstance(v,(list,dict)) or not v:return {}
    key=path.split('.')[-1]
    if isinstance(v,dict):return {k:float(x) for k,x in v.items() if finite(x)}
    if isinstance(v[0],dict):
        result={}
        for idx,row in enumerate(v):
            site=(str(row.get('i'))+':'+str(row.get('j'))) if 'i' in row and 'j' in row else str(row.get('atom_index',idx))
            for k,x in row.items():
                if k in ('i','j','atom_index','atom_i','atom_j','basis_i','basis_j'):continue
                if finite(x):result[site+':'+k]=float(x)
                elif isinstance(x,list) and all(finite(y) for y in x):
                    for j,y in enumerate(x):result[site+':'+k+':'+str(j)]=float(y)
        return result
    try:a=np.asarray(v,dtype=float)
    except (ValueError,TypeError):return {}
    if not np.isfinite(a).all():return {}
    if key=='dipole_Debye':return {'norm':float(np.linalg.norm(a))}
    if key=='molecular_quadrupole_traceless_au':return {'component_norm_proxy':float(np.linalg.norm(a))} # six-component convention, same program across conformers
    if a.ndim==2 and a.shape==(3,3):return {'trace':float(np.trace(a)),'frobenius':float(np.linalg.norm(a))}
    if key in ('frequencies_cm_inverse','IR_km_mol'):return {'minimum':float(a.min()),'mean':float(a.mean()),'norm':float(np.linalg.norm(a))}
    if key=='thermo_tot_H_cal_mol_Cp_cal_mol_K_S_cal_mol_K_S_J_mol_K':return {str(i):float(x) for i,x in enumerate(a.ravel())}
    if key in ('gradient_kcal_mol_A','gradient_Eh_bohr','forces_eV_A'):
        if a.size%3:return {}
        a=a.reshape(-1,3);return {str(i)+':norm':float(np.linalg.norm(x)) for i,x in enumerate(a)}
    return {str(i):float(x) for i,x in enumerate(a.ravel())}

def raw_polar(detail):
    ref=detail.get('archive',{});target=ref.get('member_prefix','')+'/input.out';archive=ref.get('path')
    if not archive or not target:return {'error':'RAW_REFERENCE_UNAVAILABLE'}
    child=subprocess.Popen(['/share/apps/softwares/anaconda3/bin/zstd','-dc',archive],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    found=None
    with tarfile.open(fileobj=child.stdout,mode='r|') as tar:
        for item in tar:
            if item.name==target:
                with tar.extractfile(item) as stream:found=stream.read().decode(errors='replace')
    child.stdout.close();err=child.stderr.read().decode(errors='replace');rc=child.wait(timeout=30)
    if rc or found is None:return {'error':'RAW_STREAM_NOT_CLOSED_OR_MEMBER_MISSING','returncode':rc,'stderr':err,'target':target,'archive':archive}
    lines=found.splitlines();start=next((i for i,l in enumerate(lines) if re.search(r'ALPHA AT\s+0\.0+\s+EV',l)),None)
    if start is None:return {'error':'RAW_STATIC_ALPHA_BLOCK_MISSING','archive':archive,'member':target}
    section=lines[start:start+24];rows=[]
    for line in section:
        tokens=line.split()
        if tokens and tokens[0] in ('*=X:','*=Y:','*=Z:'):
            try:rows.append([float(x.replace('D','E')) for x in tokens[1:4]])
            except ValueError:pass
    tensor=detail.get('values',{}).get('static_polar_block',{}).get('tensor_bohr3')
    import numpy as np
    error=float(np.max(np.abs(np.asarray(rows)-np.asarray(tensor)))) if len(rows)==3 and tensor else None
    return {'archive':archive,'archive_sha256_reference':ref.get('sha256'),'member':target,'raw_excerpt':'\n'.join(section),'raw_tensor_bohr3':rows,'parsed_tensor_bohr3':tensor,'parser_max_abs_error_bohr3':error,'raw_text_sha256':hashlib.sha256(found.encode()).hexdigest(),'manual_check':'Independent line/token extraction of the literal three printed rows; no use of native POLAR parser.'}

def scan(arg):
    import numpy as np,pyarrow.parquet as pq
    path,panel=arg;receipt=json.loads(Path(path).read_text());ref=receipt['parquet']
    if sha(ref['path'])!=ref['sha256']:raise ValueError('MANIFEST_PARQUET_SHA_MISMATCH')
    rows=pq.read_table(ref['path'],use_threads=False).to_pylist();details={};observed={};missing=[];status=collections.Counter();cost=[];qc=[];polar=[];manual=[];formula=[]
    for row in rows:
        task=row['task'];rid=row['record_id'];d=json.loads(row['details_json']);details.setdefault(rid,{})[task]=d
        status[(task,row['status'])]+=1
        cost.append({k:row[k] for k in ('record_id','molecule_id','size_stratum','heavy_atoms','task','status','elapsed_seconds','qm_child_cpu_seconds')})
        values=d.get('values',{});fs=dict(fields(values));observed.setdefault(task,set()).update(fs)
        for p,v in fs.items():missing.append((task,p,rid,present(v)))
        if task=='pm7_B':
            qc.append({'record_id':rid,'Q01_gradient_norm_kcal_mol_A':d.get('Q01_gradient_norm_kcal_mol_A'),'Q02_delta_HOF_kcal_mol':d.get('Q02_delta_HOF_kcal_mol'),'qc_codes':d.get('qc_codes',[])})
            alpha=values.get('static_polar_block');at=details.get(rid,{}).get('xtb_singlepoint',{}).get('values',{}).get('D4_atomic_alpha_bohr3')
            if isinstance(alpha,dict) and isinstance(alpha.get('tensor_bohr3'),list):
                a=np.asarray(alpha['tensor_bohr3'],dtype=float);polar.append({'record_id':rid,'molecule_id':receipt['molecule_id'],'size_stratum':row['size_stratum'],'heavy_atoms':row['heavy_atoms'],'alpha_iso_bohr3':float(np.trace(a)/3),'max_abs_antisymmetry_bohr3':float(np.abs(a-a.T).max()),'relative_antisymmetry_frobenius':float(np.linalg.norm(a-a.T)/max(np.linalg.norm(a),1e-15))})
            if rid in POLAR_IDS:manual.append({'record_id':rid,'molecule_id':receipt['molecule_id'],**raw_polar(d)})
        if task in ('pm7_cation','pm7_anion'):
            s2=values.get('spin_S2');qc.append({'record_id':rid,'task':task,'status':row['status'],'spin_S2':s2,'spin_S2_minus_doublet_0_75':s2-.75 if finite(s2) else None,'spin_Sz':values.get('spin_Sz')})
        if task=='xtb_perturbed_gradient':
            forces=values.get('forces_eV_A')
            if forces and np.isfinite(np.asarray(forces)).all():qc.append({'record_id':rid,'perturb_force_norm_eV_A':float(np.linalg.norm(forces)),'maximum_atom_force_eV_A':float(np.linalg.norm(forces,axis=1).max())})
        for key in d:
            if key!='values':observed.setdefault(task,set()).add('detail.'+key)
        if all(finite(values.get(k)) for k in ('total_energy_eV','electronic_energy_eV','core_core_repulsion_eV')):
            formula.append(('PM7_total_energy_equals_electronic_plus_core',values['total_energy_eV'],values['electronic_energy_eV']+values['core_core_repulsion_eV']))
        if task=='xtb_perturbed_gradient' and values.get('gradient_Eh_bohr') and values.get('forces_eV_A'):
            x=np.asarray(values['forces_eV_A']).ravel();y=-np.asarray(values['gradient_Eh_bohr']).ravel()*27.211386245988/.529177210903
            formula.extend(('xTB_force_from_gradient_unit_conversion',float(a),float(b)) for a,b in zip(x,y))
    for item in polar:
        a=details[item['record_id']].get('xtb_singlepoint',{}).get('values',{}).get('D4_atomic_alpha_bohr3')
        item['D4_atomic_alpha_sum_bohr3']=sum(a) if isinstance(a,list) and all(finite(x) for x in a) else None
    # Per-molecule component means and within sums, using common sparse sites;
    # nonmatching source atom order/bond graph stays explicitly unassessed.
    molecule=receipt['molecule_id'];g=GEOMS.get(molecule,{})
    signatures={json.dumps([v.get('atomic_numbers'),v.get('bond_pairs_zero_based'),v.get('bond_order_codes')],sort_keys=True) for v in g.values()}
    aligned=bool(g) and len(signatures)==1 and all(v.get('xyz_roundtrip_status')=='PASS' and v.get('bond_pairs_zero_based') is not None for v in g.values())
    icc=[];pairchecks=[];scalars=[]
    tasks=sorted({t for d in details.values() for t in d})
    for task in tasks:
        targetpaths=sorted(p for p in observed.get(task,set()) if p.startswith('values.') and classify(p)=='physical_label')
        for p in targetpaths:
            key=p.split('.')[-1]
            if 'polar' in p.lower() or 'STATIC' in p:continue
            values=[]
            for rid,ds in details.items():
                d=ds.get(task,{});valid=d.get('status')=='SUCCESS' or (task=='pm7_B' and d.get('B_base_success'))
                if not valid:continue
                v=dict(fields(d.get('values',{}))).get(p)
                if not present(v):continue
                if level(p) in ('atom','atom_vector','sparse_atom_pair') and not aligned:continue
                f=feature(v,p,g.get(rid))
                if f:values.append(f)
                if finite(v):scalars.append((task,p,rid,float(v)))
            if len(values)<2:continue
            sites=set.intersection(*(set(v) for v in values))
            for site in sites:
                a=np.asarray([v[site] for v in values]);icc.append((task,p,site,len(a),float(a.mean()),float(((a-a.mean())**2).sum())))
    for rid,ds in details.items():
        b=ds.get('pm7_B',{}).get('values',{});e=ds.get('pm7_ESP',{}).get('values',{})
        for key in set(b)&set(e):
            if key in QC or key in PROV or key.startswith('polar') or isinstance(b[key],dict):continue
            try:x=np.asarray(b[key],dtype=float);y=np.asarray(e[key],dtype=float)
            except (TypeError,ValueError):continue
            if x.size and x.shape==y.shape and np.isfinite(x).all() and np.isfinite(y).all():pairchecks.append((key,x.size,float(np.max(np.abs(x-y)))))
        derived=b.get('derived_from_same_geometry_charged_states',{})
        e0=b.get('heat_of_formation_kcal_mol')
        for target,t,sign in [('vertical_IP_eV','pm7_cation',1),('vertical_EA_eV','pm7_anion',-1)]:
            ec=ds.get(t,{}).get('values',{}).get('heat_of_formation_kcal_mol')
            if finite(e0) and finite(ec) and finite(derived.get(target)):formula.append((target,derived[target],sign*(ec-e0)/23.060548867))
        for task in ('pm7_water','pm7_octanol'):
            es=ds.get(task,{}).get('values',{}).get('heat_of_formation_kcal_mol');v=derived.get(task+'_HOF_difference_kcal_mol')
            if finite(es) and finite(e0) and finite(v):formula.append((task+'_HOF_difference',v,es-e0))
        fs=derived.get('fukui_Coulson',{});q0=b.get('net_charges_e');qp=ds.get('pm7_cation',{}).get('values',{}).get('net_charges_e');qm=ds.get('pm7_anion',{}).get('values',{}).get('net_charges_e')
        if q0 and qp and qm and len(q0)==len(qp)==len(qm):
            for name,yy in [('plus',np.asarray(q0)-qm),('minus',np.asarray(qp)-q0),('radical',(np.asarray(qp)-qm)/2)]:
                if fs.get(name):formula.extend(('PM7_fukui_'+name,float(a),float(z)) for a,z in zip(fs[name],yy))
    return {'worker_pid':os.getpid(),'rows':len(rows),'molecule_id':molecule,'observed':{t:sorted(s) for t,s in observed.items()},'missing':missing,'statuses':list((t,s,n) for (t,s),n in status.items()),'cost':cost,'qc':qc,'polar':polar,'manual':manual,'formula':formula,'icc':icc,'paired':pairchecks,'scalars':scalars,'atom_graph_alignment_assessed':aligned,'receipt':str(path)}

def raw_check(arg):
    import pyarrow.parquet as pq
    path,rid=arg; receipt=json.loads(Path(path).read_text())
    for row in pq.read_table(receipt['parquet']['path'],columns=['record_id','task','details_json'],use_threads=False).to_pylist():
        if row['record_id']==rid and row['task']=='pm7_B':return {'record_id':rid,'molecule_id':receipt['molecule_id'],**raw_polar(json.loads(row['details_json']))}
    return {'record_id':rid,'error':'RAW_CASE_NOT_FOUND'}

def stats(v):
    import numpy as np
    a=np.asarray([x for x in v if finite(x)],dtype=float)
    if not len(a):return {'n':0}
    return {'n':len(a),'min':float(a.min()),'p01':float(np.quantile(a,.01)),'p10':float(np.quantile(a,.1)),'p50':float(np.quantile(a,.5)),'p90':float(np.quantile(a,.9)),'p99':float(np.quantile(a,.99)),'max':float(a.max()),'mean':float(a.mean())}
def pearson(x,y):
    import numpy as np
    a=np.asarray(x);b=np.asarray(y)
    if len(a)<3 or np.std(a)==0 or np.std(b)==0:return None
    return float(np.corrcoef(a,b)[0,1])
def r_squared(actual,pred):
    import numpy as np
    a=np.asarray(actual);p=np.asarray(pred);den=float(((a-a.mean())**2).sum())
    return 1-float(((a-p)**2).sum())/den if den else None

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=32);parser.add_argument('--check',action='store_true');a=parser.parse_args()
    if a.check:
        import ast;ast.parse(Path(__file__).read_text());print('AST_PASS_NO_QM_NO_LMDB');return
    if not os.environ.get('SLURM_JOB_ID') or not 16<=a.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK',0)):raise ValueError('SLURM_16_WORKERS_REQUIRED')
    import numpy as np,pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(a.workers);pa.set_io_thread_count(min(a.workers,8));start=time.monotonic()
    out=ROOT/'b_quantum/analysis';out.mkdir(parents=True,exist_ok=False)
    panelpath=OLD/'wp4_native_panel/pilot_panel.parquet';panel=pq.read_table(panelpath).to_pylist();byid={r['record_id']:r for r in panel};manifest=json.loads((OLD/'wp4_native_panel/pilot_panel_manifest.json').read_text())
    paths=sorted((OLD/'wp4_native_full_v4').glob('bucket_*/molecules/*/receipt.json'))
    if len(panel)!=10020 or len(paths)!=1441:raise ValueError('MANIFEST_COUNTS_MISMATCH')
    geompath=ROOT/'c_engineering/xyz/analysis_geometry.parquet';geoms={}
    if geompath.exists():
        for r in pq.read_table(geompath).to_pylist():geoms.setdefault(r['molecule_id'],{})[r['record_id']]=r
    # Twenty molecules, balanced seven heavy-atom strata, minimum PM7 conformer.
    groups=collections.defaultdict(list)
    for r in panel:
        if r.get('molecule_lowest_energy_conformer'):groups[r['size_stratum']].append(r)
    for rows in groups.values():rows.sort(key=lambda r:hashlib.sha256(('B2|20261011|'+r['molecule_id']).encode()).hexdigest())
    chosen=[];offset=0
    while len(chosen)<20:
        for key in sorted(groups):
            if offset<len(groups[key]):chosen.append(groups[key][offset])
            if len(chosen)==20:break
        offset+=1
    context=multiprocessing.get_context('spawn');barrier=context.Barrier(a.workers);results=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=context,initializer=init,initargs=(geoms,[],barrier)) as pool:
        for r in pool.map(scan,[(str(p),None) for p in paths],chunksize=1):results.append(r)
    if sum(r['rows'] for r in results)!=131701 or len({r['molecule_id'] for r in results})!=1441:raise ValueError('MANIFEST_OUTCOMES_MISMATCH')
    observed=collections.defaultdict(set)
    for r in results:
        for t,fields_ in r['observed'].items():observed[t].update(fields_)
    entries=[]
    for task,paths_ in sorted(observed.items()):
        for p in sorted(paths_):
            e=entry(task,p)
            if p.startswith('detail.'):
                e.update(classification='QC' if p[7:] in ('status','failure_code','failure_reason','qc_codes','Q01_gradient_norm_kcal_mol_A','Q02_delta_HOF_kcal_mol','B_base_success','missing_properties','length_issues','diagnostic_lines') else 'provenance',level='case',unit='not a physical label',excluded=False,dedup_of=None,derived_from=[])
            e['registry_id']=len(entries);entries.append(e)
    registry={'status':'ALL_NATIVE_PILOT_PRODUCED_FIELDS_MAPPED','entries':entries,'source_parquet_files':1441,'requested_outcomes':131701,'no_final_field_schema_adopted':True,'unmapped_fields':0,'metadata_container_policy':'Each values-field and each detail root field maps once; derived-state dict and static polar dict expanded to semantic named leaf fields. Atom/pair dictionaries remain structured numeric arrays; index keys part of their wire, not stand-alone target.', 'script_sha256':sha(__file__)}
    save(ROOT/'reports/label_registry.json',registry)
    # Universal field missingness includes absent keys, not just explicit nulls.
    flags={(t,p,rid):ok for r in results for t,p,rid,ok in r['missing']};rows_missing=[]
    physical=[e for e in entries if e['classification']=='physical_label']
    task_records=collections.defaultdict(set)
    costs=[item for r in results for item in r['cost']]
    for r in costs:task_records[r['task']].add(r['record_id'])
    for e in physical:
        groups_=collections.defaultdict(lambda:[0,0])
        for rid in task_records[e['task']]:
            row=byid[rid];keys=[('all','all'),('size',row['size_stratum'])]+[('element',str(z)) for z in set(row['elements'])]
            ok=flags.get((e['task'],e['source_path'],rid),False)
            for k in keys:groups_[k][0]+=1;groups_[k][1]+=not ok
        for (kind,group),(n,miss) in groups_.items():rows_missing.append({'registry_id':e['registry_id'],'task':e['task'],'source_path':e['source_path'],'group_kind':kind,'group':group,'scheduled':n,'missing':miss,'missing_rate':miss/n})
    pq.write_table(pa.Table.from_pylist(rows_missing),out/'B4_missing_by_label_group.parquet',compression='zstd')
    pq.write_table(pa.Table.from_pylist(costs),out/'pilot_costs.parquet',compression='zstd')
    qc=[item for r in results for item in r['qc']];statuses=collections.Counter()
    for r in results:
        for t,s,n in r['statuses']:statuses[(t,s)]+=n
    B4={'Q01':stats([r.get('Q01_gradient_norm_kcal_mol_A') for r in qc]),'Q02_signed':stats([r.get('Q02_delta_HOF_kcal_mol') for r in qc]),'Q02_absolute':stats([abs(r['Q02_delta_HOF_kcal_mol']) for r in qc if finite(r.get('Q02_delta_HOF_kcal_mol'))]),'perturb_force_norm_eV_A':stats([r.get('perturb_force_norm_eV_A') for r in qc]),'maximum_atom_force_eV_A':stats([r.get('maximum_atom_force_eV_A') for r in qc]),'task_statuses':[{'task':t,'status':s,'count':n} for (t,s),n in sorted(statuses.items())],'spin':{t:{'spin_S2':stats([r.get('spin_S2') for r in qc if r.get('task')==t]),'spin_contamination_S2_minus0_75':stats([r.get('spin_S2_minus_doublet_0_75') for r in qc if r.get('task')==t]),'missing_S2':sum(r.get('spin_S2') is None for r in qc if r.get('task')==t)} for t in ('pm7_cation','pm7_anion')},'missingness_reference':'B4_missing_by_label_group.parquet','missingness_policy':'Absent/null/nonfinite/empty are missing; values availability and calculation outcome reported separately; no zero imputation.'}
    save(out/'B4_QC.json',B4)
    polar=[item for r in results for item in r['polar']]
    valid_groups=collections.defaultdict(list)
    for r in polar:
        if byid[r['record_id']].get('molecule_lowest_energy_conformer'):valid_groups[r['size_stratum']].append(r)
    for rr in valid_groups.values():rr.sort(key=lambda r:hashlib.sha256(('B2|20261011|'+r['molecule_id']).encode()).hexdigest())
    chosen=[];offset=0
    while len(chosen)<20:
        for key in sorted(valid_groups):
            if offset<len(valid_groups[key]):chosen.append(valid_groups[key][offset])
            if len(chosen)==20:break
        offset+=1
        if offset>1441:raise ValueError('B2_20_VALID_MOLECULES_UNAVAILABLE')
    receipts={r['molecule_id']:r['receipt'] for r in results}
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=context) as pool:
        manual=list(pool.map(raw_check,[(receipts[r['molecule_id']],r['record_id']) for r in chosen],chunksize=1))
    pairs=[r for r in polar if finite(r.get('D4_atomic_alpha_sum_bohr3'))];x=[r['alpha_iso_bohr3'] for r in pairs];y=[r['D4_atomic_alpha_sum_bohr3'] for r in pairs]
    from scipy.stats import spearmanr
    B2={'molecular_polar_tensors':len(polar),'antisymmetry_abs_bohr3':stats([r['max_abs_antisymmetry_bohr3'] for r in polar]),'relative_antisymmetry_frobenius':stats([r['relative_antisymmetry_frobenius'] for r in polar]),'asymmetric_gt0_01':sum(r['max_abs_antisymmetry_bohr3']>.01 for r in polar),'raw_manual_20':manual,'requested_manual_molecules':20,'verified_printed_tensor_equal_parser':sum(r.get('parser_max_abs_error_bohr3')==0 for r in manual),'correlation_PM7_trace_over3_vs_sum_D4_atomic_alpha':{'n':len(pairs),'pearson':pearson(x,y),'spearman':float(spearmanr(x,y).statistic) if len(x)>2 else None,'by_size':{key:{'n':sum(r['size_stratum']==key for r in pairs),'pearson':pearson([r['alpha_iso_bohr3'] for r in pairs if r['size_stratum']==key],[r['D4_atomic_alpha_sum_bohr3'] for r in pairs if r['size_stratum']==key])} for key in sorted(groups)},'interpretation':'D4 screened atom polarizability sum is an empirical comparison proxy, not the same molecular response tensor.'},'decision':'DELETE_POLAR_NO_FURTHER_INVESTIGATION' if sum(r.get('parser_max_abs_error_bohr3')==0 for r in manual)>=16 and all(r['max_abs_antisymmetry_bohr3']>.01 for r in polar) else 'INSPECT_MANUAL_MISSING_EVIDENCE'}
    save(out/'B2_POLAR.json',B2)
    with (out/'B2_raw_manual_20.md').open('w') as f:
        for i,r in enumerate(manual):f.write(f"\n{i+1}. {r['record_id']} parser/raw max error={r.get('parser_max_abs_error_bohr3')}\n\n```text\n{r.get('raw_excerpt',r.get('error'))}\n```\n")
    # Unbalanced one-way random-effects ANOVA at each common site/component.
    accum=collections.defaultdict(list)
    for r in results:
        for t,p,site,n,mean,ss in r['icc']:accum[(t,p,site)].append((n,mean,ss))
    components=[]
    for (t,p,site),items in accum.items():
        if len(items)<2:continue
        ns=np.asarray([i[0] for i in items],float);means=np.asarray([i[1] for i in items]);N=ns.sum();k=len(items);grand=float((ns*means).sum()/N)
        MSW=sum(i[2] for i in items)/(N-k);MSB=float((ns*(means-grand)**2).sum()/(k-1));n0=float((N-(ns*ns).sum()/N)/(k-1));between=(MSB-MSW)/n0
        between_nonnegative=max(between,0);icc=between_nonnegative/(between_nonnegative+MSW) if between_nonnegative+MSW>0 else None
        ratio=MSW/between_nonnegative if between_nonnegative>0 else None
        components.append({'task':t,'source_path':p,'component':site,'molecules':k,'records':int(N),'within_variance':float(MSW),'between_variance_raw':float(between),'between_variance_nonnegative':float(between_nonnegative),'within_over_between_ratio':float(ratio) if ratio is not None else None,'ICC':float(icc) if icc is not None else None,'within_fraction':float(1-icc) if icc is not None else None})
    if components:pq.write_table(pa.Table.from_pylist(components),out/'B5_ICC_components.parquet',compression='zstd')
    summary=[]
    wanted=[e for e in physical if e['task'].startswith('xtb_') or e['task'] in ('pm7_water','pm7_octanol','pm7_cation','pm7_anion') or 'derived_from_same_geometry' in e['source_path']]
    for e in wanted:
        cs=[r for r in components if r['task']==e['task'] and r['source_path']==e['source_path']]
        fractions=[r['within_fraction'] for r in cs if r['within_fraction'] is not None]
        summary.append({'task':e['task'],'source_path':e['source_path'],'level':e['level'],'assessed_components':len(cs),'within_fraction':stats(fractions),'within_over_between_ratio':stats([r['within_over_between_ratio'] for r in cs]),'conformer_sensitive_components_gt10pct':sum(x>.1 for x in fractions),'minimum_molecule_count':min([r['molecules'] for r in cs],default=0),'availability':'assessed' if cs else 'not_estimable_from_pilot (minimum-only/sparse/missing/single-conformer)','notes':e['notes']})
    save(out/'B5_coverage_ICC.json',{'method':'Unbalanced one-way random-effects ANOVA, within=MSW, between=(MSB-MSW)/n0; negative between estimates reported and clipped to0 only for ICC. ICC=between/(between+within); requested within/between ratio also reported. Only molecules with>=2 valid conformers contribute.','array_policy':'Native atom sequence and stored bond graph compared within molecule; common sparse sites used, absent pairs never zero. Scalar/vector magnitude and tensor norm/trace summaries, not unaligned vector components. Frequency arrays use invariant summaries; modes not matched. Perturbed gradients additionally contain seeded noise.','atom_graph_aligned_molecules':sum(r['atom_graph_alignment_assessed'] for r in results),'labels':summary,'components_reference':'B5_ICC_components.parquet'})
    recipes=collections.defaultdict(list)
    for r in results:
        for name,x,y in r['formula']:recipes[name].append((x,y))
    proven=[]
    for name,pairs_ in sorted(recipes.items()):
        xx=[p[0] for p in pairs_];yy=[p[1] for p in pairs_];err=max(abs(x-y) for x,y in pairs_);rs=r_squared(xx,yy)
        proven.append({'formula':name,'n':len(pairs_),'R2':rs,'max_abs_error':err,'exact_observed':err==0,'R2_gt0_9999':rs is not None and rs>.9999})
    duplicates=collections.defaultdict(list)
    for r in results:
        for key,n,err in r['paired']:duplicates[key].append((n,err))
    duplist=[{'field':k,'tasks':['pm7_B','pm7_ESP'],'same_method_charge_geometry':True,'paired_records':len(v),'numeric_components':sum(x[0] for x in v),'max_abs_difference':max(x[1] for x in v),'exact_duplicate_in_observed_pairs':all(x[1]==0 for x in v)} for k,v in sorted(duplicates.items())]
    B6={'registry':str(ROOT/'reports/label_registry.json'),'registry_entries':len(entries),'unmapped_fields':0,'formula_checks':proven,'within_method_duplicates':duplist,'misgrouped_or_nonphysical_fields':[{'task':e['task'],'source_path':e['source_path'],'classification':e['classification']} for e in entries if e['classification']!='physical_label'],'specialty_xTB_scope':'Existing runner filters vipea/vfukui/ALPB/FOD final internal-state dumps to requested labels. Registry method, charge and solvent scope kept; no reclassification of final ionic state into neutral SP.','POLAR_static_duplicate':'static_polar_block mirrors polar_blocks frequency0; retained in QC report only.','no_automatic_physical_label_deletion':True}
    save(out/'B6_registry_audit.json',B6)
    report={'status':'B2_B4_B5_B6_ANALYSIS_CLOSED','job_id':os.environ['SLURM_JOB_ID'],'source_records':10020,'source_molecules':1441,'source_outcomes':131701,'actual_worker_pids':sorted({r['worker_pid'] for r in results}),'seconds':time.monotonic()-start,'script_sha256':sha(__file__),'original_data_written':False,'new_QM_invocations':0,'lmdb_1_created':False,'B2':str(out/'B2_POLAR.json'),'B4':str(out/'B4_QC.json'),'B5':str(out/'B5_coverage_ICC.json'),'B6':str(out/'B6_registry_audit.json')}
    save(out/'manifest.json',report);print(json.dumps(report))
if __name__=='__main__':main()
