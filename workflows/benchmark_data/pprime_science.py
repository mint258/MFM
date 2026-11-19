"""Downstream inputs for the unchanged WP5 twelve-task native invocation/parser."""
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import socket
import stat
import sys
import threading
import time
import numpy as np
from rdkit import Chem,rdBase

WP5=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
PROTOCOL_SHA='3e831aa57d4d90376c6107e309484e231038a3536ed0f28371d2f8554149a6bc'


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def native_input(source,conformer,cutoff=4.0):
    """Same graph parser/AddHs order as S′; do not generate any coordinates."""
    params=Chem.SmilesParserParams();params.removeHs=False
    template=Chem.MolFromSmiles(source['model_smiles'],params)
    if template is None:raise ValueError('Generated S-prime source graph is unavailable')
    mol=Chem.AddHs(template)
    z=np.asarray([a.GetAtomicNum() for a in mol.GetAtoms()],dtype=np.int64)
    if z.tolist()!=source['atomic_numbers']:raise ValueError('S-prime graph/source atom order differs')
    xyz=np.asarray(conformer['coordinates_A'],dtype=np.float64)
    if xyz.shape!=(len(z),3) or not np.isfinite(xyz).all():raise ValueError('S-prime source coordinates are incomplete')
    if conformer.get('converged') is not True or conformer.get('geometry_source')!='UFF_Sprime':
        raise ValueError('Only original accepted S-prime geometries are inputs to P-prime')
    pairs={(max(b.GetBeginAtomIdx(),b.GetEndAtomIdx()),min(b.GetBeginAtomIdx(),b.GetEndAtomIdx())) for b in mol.GetBonds()}
    pairs.update((i,j) for i in range(len(z)) for j in range(i) if float(np.linalg.norm(xyz[i]-xyz[j]))<=cutoff)
    return {'symbols':[a.GetSymbol() for a in mol.GetAtoms()],'z':z,'coords':xyz,'energy':None,
        'pairs':sorted(pairs),'native_coordinates_sha256':None,'native_atom_order_sha256':None}


def load(scratch,deadline,stop_event=None):
    node=socket.gethostname().split('.')[0]
    if node not in {'compute-0-'+str(i) for i in range(8,20)} or not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Actual development CPU-node Slurm allocation required')
    if rdBase.rdkitVersion!='2025.09.5':raise RuntimeError('Original RDKit version required')
    scratch=Path(scratch).resolve()
    if not scratch.is_dir() or not scratch.is_relative_to(Path('/tmp')) or scratch.stat().st_uid!=os.getuid():
        raise ValueError('Owned node-local scratch required')
    scripts=WP5/'scripts';sys.path.insert(0,str(scripts))
    engine=module('_benchmark_original_wp5_engine',scripts/'wp5_engine_v3.py')
    if engine.sha(WP5/'configs/protocol.json')!=PROTOCOL_SHA:raise ValueError('Original WP5 protocol changed')
    protocol=engine.load_protocol()
    contract=json.loads((WP5/'configs/production_contract_v7.json').read_text())
    package=json.loads(Path(contract['reproduction_package']['path']).read_text())
    for family,version in package['software_versions'].items():
        if version['version']!=protocol['expected_versions'][family] or engine.sha(protocol[family+'_executable'])!=version['sha256']:
            raise ValueError('Original quantum executable version/binary differs: '+family)
    if engine.sha(protocol['registry']['path'])!=protocol['registry']['sha256']:
        raise ValueError('Original label registry changed')
    native=engine.pinned_module('_benchmark_original_wp5_native',protocol['frozen_dependencies']['native_lifecycle'])
    parser=module('_benchmark_original_wp5_parser',scripts/'wp5_parser_v2.py')
    native.MULLIKEN=engine.pinned_module('_benchmark_original_wp5_mulliken',protocol['frozen_dependencies']['mulliken'])
    protocol['scratch_base']=str(scratch)
    native.CONFIG=protocol;native.PARSER=parser;native.DEADLINE=float(deadline)
    native.STOP_EVENT=stop_event if stop_event is not None else threading.Event()
    native.OUTPUT=scratch
    engine.CONFIG=protocol;engine.NATIVE=native;engine.PARSER=parser
    engine.REGISTRY=json.loads(Path(protocol['registry']['path']).read_text())['entries']
    engine.PACKAGE=package
    engine.WIRE=module('_benchmark_original_wp5_registry_wire',scripts/'wp5_parquet_v2.py')
    return Adapter(engine,scratch,contract['reproduction_package'])


class Adapter:
    def __init__(self,engine,scratch,reproduction_reference):
        self.engine=engine;self.scratch=Path(scratch);self.reproduction_reference=reproduction_reference
        self.call_scratch=None
        self.original_cleanup=engine.NATIVE.cleanup_scratch
        # These replace only archive/cleanup I/O hooks, as in original WP5.
        # The actual quantum invocation, input rendering and parsing functions
        # are unchanged. No original LMDB reader or dummy source is used.
        engine.NATIVE.output_archive=self.defer_archive
        engine.NATIVE.cleanup_scratch=self.defer_cleanup

    def defer_archive(self,paths,target,member_prefix):
        if paths:self.call_scratch=Path(paths[0]).parent
        paths[:]=[]  # no legacy per-output data hashes or tiny archives
        return {'storage':'B0_SHARED_LANE_RAW_CONTAINER_AFTER_SCOPE_STATUS','input_bodies_saved':False}

    def defer_cleanup(self,path):
        self.call_scratch=Path(path)
        return 0

    def files(self,complete):
        result=[]
        if self.call_scratch is None:return result
        for path in sorted(self.call_scratch.iterdir()):
            info=path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid():raise ValueError('Unowned/nonregular QM scratch output')
            if path.name in {'input.xyz','input.mop','native.inp'}:continue
            if not complete and path.name not in {'input.out','process.out'}:continue
            result.append({'name':path.name,'byte_count':info.st_size,'role':'output','data':path.read_bytes()})
        return result

    def compute(self,source,conformer,row,sink,admit):
        engine=self.engine;native=native_input(source,conformer,engine.CONFIG['pair_cutoff_A'])
        details=[]
        for task in engine.CONFIG['tasks']:
            admit(67108864)
            if time.time()>=engine.NATIVE.DEADLINE-30:raise RuntimeError('Original quantum lifecycle deadline reached; no scientific retry')
            self.call_scratch=None
            result=engine.NATIVE.invoke(task,native,row,self.scratch)
            if result.get('scratch_cleanup_error'):raise RuntimeError('Original lifecycle preserved scratch: '+result['scratch_cleanup_error'])
            original_status=result['status'];result['source_status']=original_status
            issues=engine.validate_atomic_arrays(result,native['z'])
            result['atomic_array_validation']=issues
            if issues and original_status=='SUCCESS':result.update(status='PROPERTY_FAILED',failure_code='REQUESTED_SCOPE_ATOMIC_ARRAY_QC_FAILED')
            result['status']=engine.canonical_status(result['status']);result['scope_status']=result['status']
            result['parser_context']=engine.PARSER.context()
            result['precision_by_field']=result['parser_context'].get('rounding_decimal_places',{})
            result['raw_audit_selected']=bool(row['audit_selected'])
            keep=row['audit_selected'] or result['scope_status']!='SUCCESS'
            files=self.files(complete=keep)
            result['archived_files']=[{'name':f['name'],'bytes':f['byte_count'],'sha256':None} for f in files] if keep else []
            result['aux_archived']=bool(keep and any(f['name']=='input.aux' for f in files))
            scf=engine.extract_scf(task['name'],files,result.get('values'),result['status'],original_status)
            result['provenance']={'software_version_id':engine.PACKAGE['software_versions'][task['family']]['software_version_id'],
                'software_version':engine.CONFIG['expected_versions'][task['family']],
                'status':result['scope_status'],'scf_iterations':scf['scf_iterations'],'converged':scf['converged'],
                'scf_iteration_definition':scf['iteration_definition'],'scf_missing_reason':scf['missing_reason'],
                'elapsed_seconds':result.get('elapsed_seconds'),'input_file_sha256':None,'input_bundle_sha256':None,
                'input_hash_missing_reason':'Benchmark directive: no additional data/input content hashing; original renderer and source geometry retained'}
            # Actual source values + registry paths are retained. No separate
            # source-token QA pass or numerical readback is introduced here.
            result['registry_source_evidence']={'status':'ORIGINAL_PARSER_VALUES_AND_CONTEXT_RETAINED_NO_EXTRA_QA',
                'label_registry':engine.CONFIG['registry']}
            meta={'record_id':row['record_id'],'molecule_id':row['molecule_id'],'calc_type':task['name'],
                'source_status':original_status,'scope_status':result['scope_status'],'audit_selected':row['audit_selected'],
                'software_version':engine.CONFIG['expected_versions'][task['family']],
                'keywords_or_arguments':task.get('keywords',task.get('args')),'provenance':result['provenance'],
                'original_reproduction_reference':self.reproduction_reference,'geometry_source':'UFF_Sprime',
                'source_conformer_id':conformer['conformer_id'],'input_bodies_saved':False}
            meta['parsed_detail']=dict(result)
            result['raw_ref']=sink(meta,files if keep else [],keep,admit)
            result['archive']=result['raw_ref']
            if self.call_scratch is not None:
                result['scratch_bytes_removed']=self.original_cleanup(self.call_scratch)
                self.call_scratch=None
            result['Q02_applicable']=False;result['Q02_reason']='UFF_GEOMETRY_HAS_NO_STORED_PM7_HOF'
            if result.get('Q02_delta_HOF_kcal_mol') is not None:raise ValueError('Different-geometry old energy was subtracted')
            details.append(result)
            if original_status in engine.NATIVE.UNFINISHED:raise RuntimeError('Original quantum lifecycle partial outcome preserved; no retry')
        engine.derived_quantities(details)
        return {'record_id':row['record_id'],'molecule_id':row['molecule_id'],
            'source_conformer_id':conformer['conformer_id'],'geometry_source':'UFF_Sprime',
            'state':'COMPLETE_WITH_RECORDED_OUTCOMES','tasks':details,
            'all_twelve_tasks_success':all(d['scope_status']=='SUCCESS' for d in details),
            'task_status_counts':dict(Counter(d['scope_status'] for d in details)),
            'source_atom_order':'Exact source S-prime model graph order, new H appended',
            'label_units':engine.CONFIG['units'],'P_ready':False,'no_scientific_retry':True,
            'pretraining_loss_disabled_registry_ids':[674],
            'sigma_pi_training_columns':'Frozen same-symmetry sigma/sigma and pi/pi sums; raw mixed/delta entries retained'}
