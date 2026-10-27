#!/usr/bin/env python3
"""Saved passive trace only: no encoder/head/model replay or new physical verdict."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import io
import itertools
import json
import math
import multiprocessing
import os
from pathlib import Path
import socket
import stat
import sys
import traceback
import zipfile

HERE = Path(__file__).absolute().parent
INPUT_CAP, ROLE_CAP, OUTPUT_CAP, META_CAP = 512<<20, 4<<20, 128<<20, 2<<20
STAGES = ('embedding',) + tuple('layer%d' % i for i in range(6)) + ('out_norm', 'packed_H0')
SPEC_TUPLES = tuple(itertools.product(('C1-0','C1-a','C1-b'), ('two','three'),
    ('H1_fixed','H1_learned','H2_fixed','H3_fixed'), (20261026,20261027)))
CASE_IDS = tuple('%s__%s__%s__seed%d' % v for v in SPEC_TUPLES)
TRANSFORMS = ('general_rotation','translation_only','other_rotation_and_translation')
BASE_KEYS = {'pos','batch','elements','clean_rows','native_row','dense_mask',
             'base_graph_index','base_atom_index','clean_graph_rows','graph_sample_type'}
NP = TORCH = None

def need(ok, message):
    if not ok:
        raise ValueError(message)

def rawref(path, maximum=META_CAP):
    path = Path(path).absolute()
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid()
         and before.st_size <= maximum, 'Bounded owned regular input required: '+str(path))
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1<<20), b''):
            digest.update(block)
    after = path.lstat()
    fields = ('st_dev','st_ino','st_size','st_mtime_ns','st_uid','st_nlink')
    need(all(getattr(before,k) == getattr(after,k) for k in fields), 'Input changed while hashing')
    return dict(path=str(path), bytes=before.st_size, sha256=digest.hexdigest())

def bound(leaf, maximum=META_CAP):
    need(set(leaf) == {'path','bytes','sha256'} and rawref(leaf['path'],maximum) == leaf,
         'Exact raw metadata binding differs')
    return json.loads(Path(leaf['path']).read_bytes())

def stat_inputs(leaves):
    """This consumer's complete scope before NPZ decode; not the old128MiB Budget."""
    unique, physical = {}, {}
    for leaf in leaves:
        need(set(leaf) == {'path','bytes','sha256'} and type(leaf['bytes']) is int and leaf['bytes'] >= 0,
             'Exact typed rawref3 required')
        path = Path(leaf['path']).absolute()
        need(str(path) == leaf['path'], 'Canonical absolute input required')
        need(str(path) not in unique or unique[str(path)] == leaf, 'Conflicting rawref')
        unique[str(path)] = leaf
        st = path.lstat()
        need(stat.S_ISREG(st.st_mode) and st.st_uid == os.getuid() and st.st_nlink == 1
             and st.st_size == leaf['bytes'], 'Selected ordinary input stat differs')
        key = st.st_dev,st.st_ino
        need(key not in physical or physical[key] == st.st_size, 'Inconsistent physical input')
        physical[key] = st.st_size
    total = sum(physical.values())
    need(total <= INPUT_CAP, 'All selected trace/control/source input exceeds512MiB')
    return unique,total

class Outputs:
    def __init__(self, root):
        self.root,self.total = Path(root),0
    def write(self, name, data):
        path = self.root/name
        need(not path.exists() and path.parent == self.root and self.total+len(data) <= OUTPUT_CAP,
             'Fresh bounded128MiB output required')
        with path.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        self.total += len(data)
        return rawref(path,OUTPUT_CAP)
    def json(self, name, value):
        return self.write(name,(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode())

def runtime():
    global NP,TORCH
    if NP is None:
        import numpy as np
        import torch
        NP,TORCH = np,torch
        need(not torch.cuda.is_initialized() and os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'CPU-only tensor arithmetic')
        torch.set_num_threads(4); torch.set_num_interop_threads(1)
        selfcheck()
    return NP,TORCH

def stats(values):
    np = NP
    need(values.dtype == np.float64 and values.size and np.isfinite(values).all(), 'Finite nonempty statistics required')
    square = float(np.sum(values*values,dtype=np.float64))
    index = tuple(int(v) for v in np.unravel_index(int(np.abs(values).argmax()),values.shape))
    return dict(components=int(values.size),nonzero_components=int(np.count_nonzero(values)),
                sumsq=square,RMS=math.sqrt(square/values.size),maxabs=float(np.abs(values[index])),argmax=list(index))

def close_control(left,right,scale):
    np = NP
    error = np.abs(left-right)
    bound64 = 32*np.finfo(np.float64).eps*scale+np.finfo(np.float64).tiny
    need(bool((error <= bound64).all()), 'Same-component F64 algebraic closure failed')
    return float(error.max())

def real_geometry(pos, src, dst, squared):
    diff = pos[src]-pos[dst]; square = diff*diff
    result = (square[:,0]+square[:,1])+square[:,2]
    return result if squared else NP.sqrt(result)

def selfcheck():
    """Independent small algebra controls inside the single actual CPU analysis job."""
    np = NP
    p = np.array([[0,0,0],[3,4,0]],dtype=np.float64)
    src,dst = np.array([0,1,0]),np.array([1,0,0])
    need(np.array_equal(real_geometry(p,src,dst,True),[25,25,0])
         and np.array_equal(real_geometry(p,src,dst,False),[5,5,0]), '3-4-5/diagonal oracle')
    d = np.array([[6.],[-5.]],dtype=np.float64); previous = np.array([[5.],[7.]],dtype=np.float64)
    increment = d-previous; point = tuple(stats(d)['argmax'])
    need(point == (0,0) and [float(v[point]) for v in (d,previous,increment)] == [6.,5.,1.],
         'Same-component anchor oracle')
    values = (np.array([[3.],[4.]],dtype=np.float64),np.array([[0.]],dtype=np.float64))
    examples = [dict(case_id='inline%d'%i,case={},error=None,records=[dict(kind='inline',port='fixed',
        unit='scalar',population='fixed',transform='fixed',statistics={'D':stats(v)},
        at_D_argmax={'signed_terms':{'D':float(v.max())}})]) for i,v in enumerate(values)]
    pooled = aggregate(examples)[0]['statistics']['D']
    need(pooled['components'] == 3 and pooled['sumsq'] == 25.
         and pooled['RMS'] == math.sqrt(25./3), 'Count-weighted aggregate RMS oracle')
    base,moved = np.array([8.]),np.array([10.])
    q0,qi,qt = np.array([7.5]),np.array([7.75]),np.array([8.5])
    D,B,C,A = moved-base,qi-q0,qt-qi,(moved-qt)-(base-q0)
    need([float(v[0]) for v in (D,B,C,A)] == [2.,.25,.75,1.], 'Four-term geometry oracle')
    close_control(D,B+C+A,np.abs(moved)+np.abs(base)+np.abs(q0)+np.abs(qi)+np.abs(qt))

def load_role(call, expected, directory):
    np = NP
    artifact,pop = call['artifact'],call['population']
    leaf,headers = artifact['file'],artifact['arrays']
    need(leaf == expected and Path(leaf['path']).parent == Path(directory) and leaf['bytes'] <= ROLE_CAP,
         'Original bounded same-case role required')
    need(rawref(leaf['path'],ROLE_CAP) == leaf, 'Role bytes differ before decode')
    n,counts = pop['native_nodes'],pop['native_nodes_by_graph']
    views = 2 if n == 88 else 3
    need(n in (88,132) and counts == [v for v in (3,9,32) for _ in range(views)]
         and pop['channels'] == 512 and pop['clean_rows'] == 44 and pop['stages'] == list(STAGES)
         and pop['copies_after_full_model_return_and_all_own_capture_hooks_removed'] is True
         and pop['postprocess_RNG_unchanged'] is True, 'Original population/transparent scope differs')
    names = {row['array'] for row in pop['geometry']}
    need(set(headers) == BASE_KEYS|{'stage__'+k for k in STAGES}|names, 'Exact array key coverage required')
    amount = 0
    for name,h in headers.items():
        need(set(h) == {'dtype','shape','nbytes','sha256'} and type(h['nbytes']) is int
             and all(type(v) is int and v >= 0 for v in h['shape']), 'Typed array header required')
        dtype = np.dtype(h['dtype'])
        need(dtype in (np.dtype('float32'),np.dtype('int64'),np.dtype('bool')) and not dtype.hasobject
             and math.prod(h['shape'])*dtype.itemsize == h['nbytes'], 'F32/int64/bool exact bytes required')
        amount += h['nbytes']
    need(amount == artifact['numeric_bytes'] and amount+65536 <= ROLE_CAP, 'Role numeric byte budget differs')
    with zipfile.ZipFile(leaf['path']) as archive:
        entries = archive.infolist()
        need(len(entries) == len(headers) and len({e.filename for e in entries}) == len(headers)
             and {e.filename for e in entries} == {k+'.npy' for k in headers}, 'Exact nonduplicated NPY members required')
        for e in entries:
            need(e.file_size <= headers[e.filename[:-4]]['nbytes']+16384, 'Oversized NPY member')
    arrays = {}
    with np.load(leaf['path'],allow_pickle=False) as archive:
        need(set(archive.files) == set(headers), 'Archive keys differ')
        for name,h in headers.items():
            value = archive[name]
            need(value.dtype == np.dtype(h['dtype']) and list(value.shape) == h['shape'] and value.nbytes == h['nbytes']
                 and hashlib.sha256(value.tobytes(order='C')).hexdigest() == h['sha256'], 'Typed array bytes differ: '+name)
            need(value.dtype != np.float32 or np.isfinite(value).all(), 'Nonfinite trace')
            arrays[name] = np.ascontiguousarray(value)
    need(rawref(leaf['path'],ROLE_CAP) == leaf, 'Role changed during decode')
    batch = arrays['batch']; starts = np.cumsum([0]+counts[:-1])
    need(batch.dtype == np.int64 and np.array_equal(batch,np.repeat(np.arange(len(counts)),counts))
         and arrays['pos'].shape == (n,3) and arrays['pos'].dtype == np.float32
         and arrays['elements'].shape == (n,1) and arrays['elements'].dtype == np.int64
         and np.array_equal(arrays['native_row'],np.arange(n))
         and np.array_equal(arrays['dense_mask'],np.arange(32)[None,:] < np.array(counts)[:,None])
         and np.array_equal(arrays['base_graph_index'],np.repeat(np.arange(3),views))
         and np.array_equal(arrays['clean_graph_rows'],np.arange(0,len(counts),views))
         and np.array_equal(arrays['graph_sample_type'].reshape(-1),np.tile((0,3) if views == 2 else (0,1,2),3)),
         'Actual native/view mappings differ')
    expected_atoms = np.concatenate([np.arange(sum((3,9,32)[:g]),sum((3,9,32)[:g])+count)
                                    for g,count in enumerate((3,9,32)) for _ in range(views)])
    clean = np.concatenate([np.arange(starts[g],starts[g]+counts[g]) for g in range(0,len(counts),views)])
    need(np.array_equal(arrays['base_atom_index'],expected_atoms) and np.array_equal(arrays['clean_rows'],clean),
         'Base atom/clean rows differ')
    for name in STAGES:
        need(arrays['stage__'+name].shape == (n,512) and arrays['stage__'+name].dtype == np.float32,
             'All native512 stage matrices required')
    need(arrays['stage__out_norm'].tobytes() == arrays['stage__packed_H0'].tobytes(), 'Packed/out_norm bit control')
    src = np.concatenate([np.repeat(np.arange(s,s+c),c) for s,c in zip(starts,counts)])
    dst = np.concatenate([np.tile(np.arange(s,s+c),c) for s,c in zip(starts,counts)])
    for row in pop['geometry']:
        need(row['physical_pairs'] == len(src) and row['includes_diagonal'] is True and row['padding_in_statistics'] is False
             and arrays[row['array']].shape == (len(src),1) and arrays[row['array']].dtype == np.float32,
             'Complete ordered native pair scalar required')
    return arrays,pop,src,dst

def populations(arrays, src=None):
    np = NP
    batch = arrays['batch']; sizes = np.bincount(batch)[batch]
    picks = {'all_physical':np.arange(len(batch)), 'clean44':arrays['clean_rows']}
    for n in (3,9,32):
        picks['native_atoms_%d'%n] = np.flatnonzero(sizes == n)
    if src is None:
        return picks
    return {name:np.flatnonzero(np.isin(src,rows)) for name,rows in picks.items()}

def point_identity(arrays, row, channel, src=None, dst=None):
    np = NP
    i = int(row if src is None else src[row]); graph = int(arrays['batch'][i])
    start = int(np.flatnonzero(arrays['batch'] == graph)[0])
    value = dict(native_row=i,physical_graph=graph,local_atom=i-start,
        base_graph=int(arrays['base_graph_index'][graph]),base_atom=int(arrays['base_atom_index'][i]),
        native_atoms=int(np.count_nonzero(arrays['batch'] == graph)),
        sample_type=int(arrays['graph_sample_type'].reshape(-1)[graph]),component=int(channel))
    if src is not None:
        value.update(native_j=int(dst[row]),local_j=int(dst[row])-start)
    return value

def record(kind,port,unit,population,indices,terms,arrays,transform,src=None,dst=None,extras=None):
    descriptions = {name:stats(value[indices]) for name,value in terms.items()}
    chosen = descriptions['D']['argmax']; full = int(indices[chosen[0]]),chosen[1]
    anchor = point_identity(arrays,*full,src=src,dst=dst)
    anchor['signed_terms'] = {name:float(value[full]) for name,value in terms.items()}
    for description in descriptions.values():
        description['argmax'][0] = int(indices[description['argmax'][0]])
    result = dict(kind=kind,port=port,unit=unit,population=population,transform=transform,
                  statistics=descriptions,at_D_argmax=anchor)
    if extras:
        result.update(extras)
    return result

def case_worker(task):
    records = []
    try:
        np,torch = runtime()
        row,spec = task['row'],task['spec']; case_ref = row['case_json']; case = bound(case_ref)
        measured,holder,construction = case['original_measurement'],case['passive_capture'],case['construction']
        identity = row['case_id']
        need(case['schema'] == 'model_v3_projection_passive_stage_trace_case_v1' and case['case_id'] == identity
             and case['error'] is None and case['scientific_adoption'] is False
             and case['no_local_module_replays'] is True and case['no_F64_model_or_local_reference_calls'] is True
             and measured['case'] == spec and measured['case_id'] == identity and measured['complete_terminal_count'] == 13
             and measured['passed'] == row['physical_passed'], 'Case scope/identity differs')
        need(construction['original_parameter_sha256'] == construction['actual_parameter_sha256']
             == measured['weight_summary']['all_named_parameter_sha256']
             and construction['attention_projection_mode'] == 'blocked_k64_compensated_fp32_v1'
             and construction['attention_aggregation_mode'] == 'centered_fp32_v1'
             and construction['FP64_core_or_encoder'] is False, 'Original seeded parameter/mode control differs')
        need(holder['state_unchanged'] is True and holder['state_before'] == holder['state_after']
             and holder['errors'] == [] and holder['forward_calls'] == holder['full_forward_returns']
             == holder['observed_encoder_returns'] == 4
             and [v['role'] for v in holder['calls']] == [0,1,2,3], 'Four successful original roles required')
        control = case['terminal_control']
        need(control['passed'] is True and len(control['arrays']) == 52
             and all(v['bitwise_equal'] is True for v in control['arrays'])
             and control['baseline_passed'] == control['fresh_passed'] == measured['passed']
             and row['all52_terminal_arrays_bitwise_equal_4550'] is True, 'External terminal controls differ')
        roles = [load_role(c,r,Path(case_ref['path']).parent) for c,r in zip(holder['calls'],row['role_archives'])]
        need(len(roles) == 4 and [m['transform']['name'] for m in measured['measurements']] == list(TRANSFORMS),
             'Exact three transforms required')
        need(all(len(m['fields']) == 13 and all(f['absolute_tolerance'] == 1e-5 and f['relative_tolerance'] == 0
                 for f in m['fields']) for m in measured['measurements']), 'Original physical criterion altered')
        base,pop,src,dst = roles[0]; squared = spec['distance_bias'] == 'C1-0'; geometry = pop['geometry']
        need([g['array'] for g in geometry] == (['geometry__layer%d_dist2'%i for i in range(6)]
              if squared else ['geometry__shared_distance']), 'Architecture-specific actual ports differ')
        for g in geometry:
            need(g['unit'] == ('angstrom_squared' if squared else 'angstrom'), 'Geometry units differ')
        if squared:
            need(all(base[g['array']].tobytes() == base[geometry[0]['array']].tobytes() for g in geometry),
                 'Same positions produced unequal layer distance ports')
        row_pops,pair_pops = populations(base),populations(base,src)
        p0 = base['pos'].astype(np.float64); q0 = real_geometry(p0,src,dst,squared)[:,None]
        node_ports = geometry_ports = coordinate_ports = 0
        for tnum,(moved,moved_pop,si,sj) in enumerate(roles[1:]):
            document = measured['measurements'][tnum]['transform']
            need(document['row_vector_rule'] == 'x @ R + t', 'Original row-vector convention required')
            for key in BASE_KEYS-{'pos'}:
                need(np.array_equal(base[key],moved[key]), 'Transform changed actual row/view identity: '+key)
            need(np.array_equal(src,si) and np.array_equal(dst,sj) and moved_pop['geometry'] == geometry,
                 'Native ordered-pair population differs')
            for g in geometry:
                if squared:
                    need(moved[g['array']].tobytes() == moved[geometry[0]['array']].tobytes(), 'Layer geometry control differs')
            need(base['stage__embedding'].tobytes() == moved['stage__embedding'].tobytes(),
                 'Same element/weight embedding bit control failed')
            R,t = np.array(document['rotation_float64'],dtype=np.float64),np.array(document['translation_A'],dtype=np.float64)
            need(R.shape == (3,3) and t.shape == (3,) and np.isfinite(R).all() and np.isfinite(t).all(), 'Finite R64/t64 required')
            # Standalone CPU expression from bound pushed_views: no model or project import.
            ideal = torch.from_numpy(base['pos']).double() @ torch.from_numpy(R) + torch.from_numpy(t)
            z,y = ideal.numpy(),moved['pos'].astype(np.float64)
            need(np.array_equal(ideal.float().numpy().view(np.uint32),moved['pos'].view(np.uint32)),
                 'Original CPU F64-to-F32 position castback control failed')
            position_delta = y-z
            for label,indices in row_pops.items():
                records.append(record('coordinate_push','positions','angstrom',label,indices,{'D':position_delta},
                    base,document['name'],extras={'recorded_orthogonality_maxabs':document['orthogonality_maxabs']}))
            coordinate_ports += 1
            previous = np.zeros_like(base['stage__embedding'],dtype=np.float64)
            for stage in STAGES:
                left,right = base['stage__'+stage].astype(np.float64),moved['stage__'+stage].astype(np.float64)
                D = right-left; increment = D-previous
                closure = close_control(D,previous+increment,np.abs(D)+np.abs(previous)+np.abs(increment))
                for label,indices in row_pops.items():
                    records.append(record('scalar_stage',stage,'latent_scalar',label,indices,
                        dict(D=D,previous_drift=previous,drift_increment=increment),base,document['name'],
                        extras={'increment_is_local_operator_error':False,'closure_maxabs':closure}))
                previous = D; node_ports += 1
            qi,qt = real_geometry(z,src,dst,squared)[:,None],real_geometry(y,src,dst,squared)[:,None]
            for g in geometry:
                a0,at = base[g['array']].astype(np.float64),moved[g['array']].astype(np.float64)
                D,B,C,A = at-a0,qi-q0,qt-qi,(at-qt)-(a0-q0)
                closure = close_control(D,B+C+A,np.abs(at)+np.abs(a0)+np.abs(q0)+np.abs(qi)+np.abs(qt))
                for label,indices in pair_pops.items():
                    item = record('geometry_port',g['array'],g['unit'],label,indices,dict(D=D,B=B,C=C,A=A),
                        base,document['name'],src,dst,{'closure_maxabs':closure,
                        'reference_scope':'Independent CPU F64 Euclidean real formula; algorithm AND precision contrast'})
                    pair = item['statistics']['D']['argmax'][0]
                    item['at_D_argmax']['source_values'] = {name:float(value[pair,0]) for name,value in
                        dict(actual_original=a0,actual_transformed=at,q_original=q0,q_ideal_transformed=qi,q_actual_transformed=qt).items()}
                    records.append(item)
                geometry_ports += 1
        for call in holder['calls']:
            need(rawref(call['artifact']['file']['path'],ROLE_CAP) == call['artifact']['file'], 'Role changed after case arithmetic')
        need(not torch.cuda.is_initialized(), 'CPU consumer initialized CUDA')
        return dict(case_id=identity,case=spec,original_physics_passed=measured['passed'],error=None,
            node_comparisons=node_ports,geometry_comparisons=geometry_ports,coordinate_comparisons=coordinate_ports,
            records=records,array_decodes=4,inline_algebra_controls_passed=True,
            runtime=dict(pid=os.getpid(),numpy=str(np.__version__),torch=str(torch.__version__),
                         Torch_threads=torch.get_num_threads(),Torch_interop_threads=torch.get_num_interop_threads(),
                         CUDA_initialized=False))
    except Exception as exc:
        return dict(case_id=task['row']['case_id'],case=task['spec'],error=dict(type=type(exc).__name__,
            message=str(exc),traceback=traceback.format_exc()),records=records,
            node_comparisons=0,geometry_comparisons=0,coordinate_comparisons=0)

def aggregate(cases):
    groups = {}
    for case in cases:
        if case['error'] is not None:
            continue
        for row in case['records']:
            for axis,value in [('all','all')]+list(case['case'].items()):
                key = json.dumps([row['kind'],row['port'],row['unit'],row['population'],row['transform'],axis,value],separators=(',',':'))
                if key not in groups:
                    groups[key] = dict(kind=row['kind'],port=row['port'],unit=row['unit'],population=row['population'],
                        transform=row['transform'],cohort_axis=axis,cohort_value=value,records=0,statistics={})
                group = groups[key]; group['records'] += 1
                for term,s in row['statistics'].items():
                    value = group['statistics'].setdefault(term,dict(components=0,nonzero_components=0,sumsq=0.,maxabs=-1.,witness=None))
                    value['components'] += s['components']; value['nonzero_components'] += s['nonzero_components']; value['sumsq'] += s['sumsq']
                    if s['maxabs'] > value['maxabs']:
                        value['maxabs'] = s['maxabs']
                        value['witness'] = dict(case_id=case['case_id'],argmax=s['argmax'])
                        if term == 'D':
                            value['witness']['same_component_signed_tuple'] = row['at_D_argmax']
    for group in groups.values():
        for value in group['statistics'].values():
            value['RMS'] = math.sqrt(value['sumsq']/value['components'])
    return [groups[k] for k in sorted(groups)]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True); parser.add_argument('--inputs-sha256',required=True)
    parser.add_argument('--source-pins-sha256',required=True); parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--expected-node',choices=['compute-0-'+str(i) for i in (2,*range(8,20))],required=True)
    args = parser.parse_args()
    need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID','').isdigit()
         and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==16 and os.environ.get('CUDA_VISIBLE_DEVICES')==''
         and socket.gethostname().split('.')[0]==args.expected_node,'Actual owned16CPU allocation required')
    pinsref,inputsref = rawref(HERE/'source_pins.json'),rawref(args.inputs)
    need(pinsref['sha256']==args.source_pins_sha256 and inputsref['sha256']==args.inputs_sha256,'Exact new inputs/pins required')
    pins,inputs = bound(pinsref),bound(inputsref)
    need(pins['schema']=='model_v3_passive_stage_offline_CPU_source_v1' and pins['inputs']==inputsref
         and inputs['schema']=='model_v3_passive_stage_offline_CPU_inputs_v1'
         and inputs['input_cap_bytes']==INPUT_CAP and inputs['output_cap_bytes']==OUTPUT_CAP,'Fixed offline scope required')
    deps = bound(inputs['dependencies'])
    leaves = [pinsref,inputsref]+pins['files']+deps['files']+inputs['metadata_refs']
    closure = bound(inputs['GPU_Root_closure'])
    need(closure['schema']=='model_v3_Root_passive_stage_trace_GPU_closure_v1'
         and closure['status']=='ACTUAL_C0_FULL48_192_FP32_PASSIVE_TRACE_ALL2496_TERMINALS_BITWISE_EQUAL_SOURCE_RESOURCE_CLOSED'
         and closure['job_id']=='4524563' and closure['FP32_full_forwards']==192
         and closure['FP64_model_or_local_replays']==0 and closure['stage_observations']==1728
         and closure['geometry_observations']==512 and closure['terminal_bitwise_controls']==2496
         and closure['physical_passed']==12 and closure['physical_failed']==36
         and closure['whole_private_original_limits_unchanged'] is True and closure['scientific_adoption'] is False,
         'Actual closed4563 complete transparent scope required')
    accounting = closure['actual_sacct']
    need(accounting['argv']==['sacct','-X','-n','-P','-j','4524563','--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
         and accounting['returncode']==0 and accounting['stdout'].strip()=='4524563|zixiao|COMPLETED|0:0|63|16|compute-0-21'
         and accounting['stderr']=='','Original actual raw GPU C0 required')
    result,complete = bound(inputs['GPU_result']),bound(inputs['GPU_complete'])
    supervisor = bound(closure['supervisor'])
    need(inputs['GPU_result']==closure['result'] and complete==dict(result=inputs['GPU_result'])
         and supervisor['status']=='COMPLETED' and supervisor['exit_code']==0 and supervisor['first_failure'] is None
         and supervisor['remaining_recorded_processes_before_retirement']==[] and supervisor['private_storage_cleanup_errors']==[],
         'Original committed result/closed supervision required')
    need(result['status']=='PASSIVE_TRACE_COMPLETE_PENDING_ACTUAL_OUTER_C0' and result['job_id']=='4524563'
         and result['failures']==[] and result['ordinary_original_FP32_encoder_forwards']==192
         and result['original_full_model_returns']==192 and result['node_stage_observations']==1728
         and result['geometry_observations']==512 and result['full_FP64_encoder_forwards']==0
         and result['local_module_replays']==0 and result['source_before_after_equal'] is True
         and result['physical_passed']==12 and result['physical_failed']==36,'Complete original trace required')
    need([r['case_id'] for r in closure['cases']]==list(CASE_IDS)
         and [r['case_id'] for r in result['cases']]==list(CASE_IDS),'Exact ordered full48 required')
    tasks = []
    for row,spec,summary in zip(closure['cases'],SPEC_TUPLES,result['cases']):
        need(row['case_json']==summary['case_json'] and len(row['role_archives'])==4
             and summary['transparency_passed'] is True and summary['captured_roles']==4
             and summary['forward_calls']==summary['observed_encoder_returns']==4,'Complete same-case binding required')
        leaves.append(row['case_json']); leaves.extend(row['role_archives'])
        tasks.append(dict(row=row,spec=dict(zip(('distance_bias','views','head_policy','weight_seed'),spec))))
    selected,total = stat_inputs(leaves)
    for leaf in selected.values():
        if not leaf['path'].endswith('.npz'):
            need(rawref(leaf['path'])==leaf,'Source/control drift before analysis')
    need(not args.output_root.exists() and not args.output_root.is_symlink(),'Fresh child output required')
    args.output_root.mkdir()
    output = Outputs(args.output_root)
    # No numerical runtime imported in parent before fork; fork-only children keep stable argv identity.
    with ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('fork')) as pool:
        cases = list(pool.map(case_worker,tasks))
    errors = [dict(case_id=c['case_id'],error=c['error']) for c in cases if c['error'] is not None]
    totals = {k:sum(c[k] for c in cases) for k in ('node_comparisons','geometry_comparisons','coordinate_comparisons')}
    role_decodes = sum(c.get('array_decodes',0) for c in cases)
    saved_geometry_ports = sum(4*(6 if c['case']['distance_bias']=='C1-0' else 1)
                               for c in cases if c['error'] is None)
    complete_ok = not errors and len(cases)==48 and role_decodes==192 and saved_geometry_ports==512 and totals==dict(node_comparisons=1296,geometry_comparisons=384,coordinate_comparisons=144)
    case_refs = [output.json('case_%02d.json'%i,c) for i,c in enumerate(cases)]
    groups = aggregate(cases)
    stream = io.StringIO(newline='')
    columns = ('case_id','kind','port','unit','population','transform','statistics_json','same_component_D_argmax_json')
    writer = csv.DictWriter(stream,fieldnames=columns); writer.writeheader()
    for case in cases:
        for row in case['records']:
            writer.writerow(dict(case_id=case['case_id'],**{k:row[k] for k in columns[1:6]},
                statistics_json=json.dumps(row['statistics'],sort_keys=True),
                same_component_D_argmax_json=json.dumps(row['at_D_argmax'],sort_keys=True)))
    csvref = output.write('all_complete_population_records.csv',stream.getvalue().encode())
    after_errors = []
    for leaf in selected.values():
        try:
            need(rawref(leaf['path'],ROLE_CAP if leaf['path'].endswith('.npz') else META_CAP)==leaf,'Input changed after analysis')
        except Exception as exc:
            after_errors.append(dict(path=leaf['path'],type=type(exc).__name__,message=str(exc)))
    complete_ok = complete_ok and not after_errors
    summary = dict(schema='model_v3_passive_stage_offline_CPU_result_v1',
        status='COMPLETE_PENDING_ACTUAL_CPU_OUTER_C0' if complete_ok else 'HOLD_NO_ATTRIBUTION',
        job_id=os.environ['SLURM_JOB_ID'],node=socket.gethostname(),GPU_source_job='4524563',
        GPU_Root_closure=inputs['GPU_Root_closure'],source_pins=pinsref,inputs=inputsref,
        selected_unique_input_bytes=total,input_cap_bytes=INPUT_CAP,cases=case_refs,errors=errors,
        input_after_errors=after_errors,all_selected_sources_and_payloads_after_match=not after_errors,
        comparisons=totals,decoded_role_archives=role_decodes,saved_node_stage_ports=role_decodes*9,
        saved_geometry_ports=saved_geometry_ports,aggregate_groups=groups,CSV=csvref,figures=[],
        weighted_RMS='sqrt(sum component sumsq / sum component count); overlapping populations never pooled',
        coordinate_push='Exact standalone CPU Torch double@recorded_R64+t64 then F32 castback control',
        geometry_decomposition='D=B+C+A at the same pair: transform/reference residual, rounded-coordinate contrast, actual-port algorithm+precision contrast',
        stage_increments_are_intrinsic_operator_error=False,terminal_causal_attribution=False,
        pure_dtype_only_reference=False,universal_FP32_floor_claim=False,
        new_encoder_or_head_or_model_calls=0,original_4550_physics_counts=dict(passed=12,failed=36),
        official_prior_FP32_gate_from_Root_retained_verbatim=closure['formal_physics_gate_unchanged'],
        scientific_adoption=False,output_bytes_before_summary=output.total,
        scope='All48 actual saved F32 traces only; no layer/seed selection or new candidate')
    finalref = output.json('RESULT.json',summary)
    if complete_ok:
        output.json('COMPLETE.json',dict(result=finalref))
    print(json.dumps(dict(status=summary['status'],cases=len(cases),comparisons=totals,
        errors=len(errors),input_bytes=total,output_bytes=output.total),sort_keys=True))
    return 0 if complete_ok else 1

if __name__=='__main__':
    raise SystemExit(main())
