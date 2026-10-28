#!/usr/bin/env python3
"""Bounded saved-trace inputs: inherited IO/typed ZIP/fd-finally guards, extended head ports."""
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
    need(type(leaf) is dict and set(leaf) == {'path','bytes','sha256'} and rawref(leaf['path'],maximum) == leaf,
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
        NP,TORCH=np,torch
        need(not torch.cuda.is_initialized() and os.environ.get('CUDA_VISIBLE_DEVICES')=='', 'CPU-only local arithmetic')
        torch.set_num_threads(4);torch.set_num_interop_threads(1)
        torch.set_float32_matmul_precision('highest')
    return NP,TORCH

def stats(values):
    np = NP
    need(values.dtype == np.float64 and values.size and np.isfinite(values).all(), 'Finite nonempty statistics required')
    square = float(np.sum(values*values,dtype=np.float64))
    index = tuple(int(v) for v in np.unravel_index(int(np.abs(values).argmax()),values.shape))
    return dict(components=int(values.size),nonzero_components=int(np.count_nonzero(values)),
                sumsq=square,RMS=math.sqrt(square/values.size),maxabs=float(np.abs(values[index])),argmax=list(index))

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
    fields=('p_dipole','p_dipole_magnitude')
    parameters={'0.weight':(64,512),'0.bias':(64,),'2.weight':(1,64),'2.bias':(1,)}
    hp=pop['head_ports'];role=call['role']
    need(role in range(4) and hp['contains_parameter_weights'] is (role==0)
         and artifact['contains_parameter_weights'] is (role==0)
         and pop['contains_parameter_weights'] is (role==0)
         and hp['actual_clean_native_atoms']==[3,9,32]
         and hp['original_objects_retained_no_return_replacement'] is True
         and hp['all_new_copies_after_full_return_and_disarm'] is True
         and [x['field'] for x in hp['fields']]==list(fields), 'Actual head provenance/population differs')
    head_names={'head__H0','head__pos','head__batch'}
    for field in fields:
        head_names|={'head__'+field+'__'+port for port in
                    ('charges','center','indexed_center','relative','product','moment','output')}
        if role==0:head_names|={'head__'+field+'__parameter__'+key for key in parameters}
    need(set(headers)==BASE_KEYS|{'stage__'+k for k in STAGES}|names|head_names,
         'Exact complete original plus specific head/parameter keys required')
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
    clean=arrays['clean_rows']
    need(arrays['head__H0'].dtype==np.float32 and arrays['head__H0'].shape==(44,512)
         and arrays['head__H0'].tobytes()==arrays['stage__packed_H0'][clean].tobytes()
         and arrays['head__pos'].dtype==np.float32 and arrays['head__pos'].shape==(44,3)
         and arrays['head__pos'].tobytes()==arrays['pos'][clean].tobytes()
         and arrays['head__batch'].dtype==np.int64
         and np.array_equal(arrays['head__batch'],np.repeat(np.arange(3),(3,9,32))),
         'Actual same-forward PD H0/position/native44 differs')
    weight_bytes=0
    for item,field in zip(hp['fields'],fields):
        need(item['head_class']=='_DipoleHead' and item['magnitude'] is (field==fields[1])
             and item['original_head_calls']==item['original_charge_calls']==item['original_center_calls']
                 ==item['original_product_calls']==item['original_moment_calls']==1
             and item['original_norm_calls']==int(field==fields[1])
             and item['full_returned_H0_and_terminal_object_identity'] is True
             and item['actual_reduction_base']=='verified original literal3x3 FP32 zero',
             'Exact original head and local-call controls differ')
        shapes={'charges':(44,1),'center':(3,3),'indexed_center':(44,3),'relative':(44,3),
                'product':(44,3),'moment':(3,3),'output':(3,1) if field==fields[1] else (3,3)}
        for port,shape in shapes.items():
            key='head__'+field+'__'+port
            need(item['arrays'][port]==key and arrays[key].dtype==np.float32 and arrays[key].shape==shape,
                 'Actual head typed port differs')
        need(set(hp['parameter_bindings'][field])==set(parameters),'Exact four named parameters per independent MLP required')
        for key,shape in parameters.items():
            binding=hp['parameter_bindings'][field][key];name='head__'+field+'__parameter__'+key
            need(binding['array']==name and tuple(binding['shape'])==shape
                 and np.dtype(binding['dtype'])==np.float32
                 and set(binding)=={'array','dtype','shape','nbytes','sha256'},
                 'Exact captured parameter header required')
            if role==0:
                need({k:v for k,v in binding.items() if k!='array'}==headers[name]
                     and arrays[name].dtype==np.float32 and arrays[name].shape==shape,
                     'Actual typed synthetic parameter payload differs')
                weight_bytes+=arrays[name].nbytes
    need(weight_bytes==(263176 if role==0 else 0),'Exactly one role0 synthetic two-MLP subset, never duplicate weights')
    return arrays,pop,src,dst

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

