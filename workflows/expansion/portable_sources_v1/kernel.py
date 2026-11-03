"""Relocated original function objects; no old Main path or UID is impersonated."""
import copy
import importlib
import importlib.util
import math
import os
from pathlib import Path
import sys
import types
from ..common import load,require
from ..uff3_candidate_v1.core import canonical,sha
from .transport import Transport,verify
from .capsule import ORIGINAL_RECIPE_SHA

_CAPSULES={}


def get_capsule(reference):
    key=canonical(reference)
    if key not in _CAPSULES:
        require(len(_CAPSULES)<4,'Fresh worker required for a different source capsule set')
        path=verify(reference);value=Capsule(reference)
        frame=path.lstat();value.manifest_path=path
        value.manifest_frame=(frame.st_dev,frame.st_ino,frame.st_size,frame.st_mtime_ns,frame.st_ctime_ns,frame.st_uid)
        _CAPSULES[key]=value
    value=_CAPSULES[key];frame=value.manifest_path.lstat()
    require((frame.st_dev,frame.st_ino,frame.st_size,frame.st_mtime_ns,frame.st_ctime_ns,frame.st_uid)==value.manifest_frame,
        'Live immutable source capsule manifest changed')
    return value

CATALOG=('seed_science','conformer_common','selection','embedding','generator','generator_schema','wire',
    'D_names','family_writer','wire_runtime_schema','wire_runtime_phase1_specs')


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value);return value


class Capsule:
    def __init__(self,reference):
        self.reference=reference;self.manifest=load(verify(reference));m=self.manifest
        require(m.get('schema')=='PUBCHEM_ORIGINAL_UFF_SOURCE_CAPSULE_V1' and m.get('status')=='ACTUAL_CLOSED_SOURCE_CAPSULE'
            and m['destination']['uid']==os.getuid() and m['original_recipe_sha256']==ORIGINAL_RECIPE_SHA,
            'Actual own closed original-source capsule required')
        require((m['destination']['endpoint'],m['destination']['uid']) in
            (('202.38.247.57:22',1278),('218.192.171.238:22',1264)),'Authorized real endpoint/UID pair required')
        self.transport=Transport(m['source_transport_manifest'],m['destination']['endpoint'],m['destination']['uid'])
        for ref in self.transport.entries.values():self.transport.local(ref)
        self.kernels=None;self._writer=None

    def role(self,name):return self.transport.local(self.manifest['roles'][name]['replica_reference'])

    def load(self):
        if self.kernels is not None:return self.kernels
        from rdkit import rdBase
        require(rdBase.rdkitVersion=='2025.09.5' and sys.version.split()[0]=='3.11.14','Original pinned Python/RDKit runtime required')
        recipe=load(self.role('original_recipe'))
        require(self.manifest['roles']['original_recipe']['replica_reference']['sha256']==ORIGINAL_RECIPE_SHA,'Original recipe changed')
        resolved=copy.deepcopy(recipe)
        resolved['science_source_pins']=[self.manifest['roles']['science_pin_'+str(i)]['replica_reference'] for i in range(len(recipe['science_source_pins']))]
        common_path=self.role('conformer_common');folder=common_path.parent
        for name,path in (('common',common_path),('selection',self.role('selection'))):
            prior=sys.modules.get(name)
            require(prior is None or Path(prior.__file__).absolute()==path,'Fresh worker required; original top-level source namespace collision')
        sys.path.insert(0,str(folder))
        try:
            common=importlib.import_module('common');selection=importlib.import_module('selection')
            seed=module('_pubchem_capsule_seed',self.role('seed_science'))
            science=common.load_science(resolved)
        finally:sys.path.pop(0)
        require(Path(sys.modules['prepare'].__file__).absolute()==self.role('science_pin_1'),'Original relocated prepare source differs')
        package='_pubchem_capsule_descriptor_sources'
        parent=types.ModuleType(package);parent.__path__=[str(self.role('generator').parent)];parent.__package__=package
        parent.__spec__=importlib.util.spec_from_loader(package,loader=None,is_package=True);sys.modules[package]=parent
        generator=importlib.import_module(package+'.rdkit_descriptor_generator')
        wire=module('_pubchem_capsule_corrected_base',self.role('wire'))
        # The unchanged wire contains its historical Main RUNTIME constant.
        # Resolve the real verified replica package first; never create that
        # historical path or replace the wire's source/global constants.
        sys.path.insert(0,self.manifest['runtime_import_root'])
        try:metadata=wire.metadata()
        finally:sys.path.pop(0)
        for name,role in (('phychem_mfm.data.descriptor_schema','wire_runtime_schema'),('phychem_mfm.model.phase1_specs','wire_runtime_phase1_specs')):
            require(Path(sys.modules[name].__file__).absolute()==self.role(role),'Actual relocated runtime schema import differs')
        names=module('_pubchem_capsule_label_names',self.role('D_names')).D20_NAMES
        require(list(wire.D20)==names and len(names)==20,'Original no-Kappa field ordering differs')
        functions={n:fn for n,fn,mode in generator.GRAPH_DESCRIPTOR_SPECS if mode=='2d'}
        require(set(names)<=set(functions),'Original descriptor function objects missing')
        science.worker_init()
        import torch
        if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)
        self.kernels={'science':science,'seed_for':seed.seed_for,'selection':selection,'wire':wire,'D20':names,'functions':functions,'metadata':metadata}
        refs={name:self.manifest['roles'][name]['replica_reference'] for name in CATALOG}
        identity={'recipe_sha256':ORIGINAL_RECIPE_SHA,'rdkit':rdBase.rdkitVersion,'python':sys.version.split()[0],
            'sources':{name:{'bytes':ref['bytes'],'sha256':ref['sha256']} for name,ref in refs.items()},
            'frozen_science_source_sha256':[r['sha256'] for r in recipe['science_source_pins']]}
        self.provenance={'fingerprint':sha(canonical(identity)),'identity':identity,
            'actual_source_references':refs,'original_recipe_reference':self.manifest['roles']['original_recipe']['replica_reference'],
            'original_science_source_references':recipe['science_source_pins'],'source_capsule_reference':self.reference,
            'actual_endpoint':self.manifest['destination']['endpoint'],'actual_uid':os.getuid(),
            'source_origin':self.manifest['origin'],'original_Main_paths_preserved_as_origin_metadata_only':True}
        return self.kernels

    def graph(self,smiles):
        from rdkit import Chem
        k=self.load();template=Chem.MolFromSmiles(smiles);require(template is not None,'Original source graph unavailable; no repair')
        mol=Chem.AddHs(template)
        unresolved=[{'type':str(i.type),'center':int(i.centeredOn),'specified':str(i.specified)} for i in Chem.FindPotentialStereo(mol)
            if str(i.specified)!='Specified' and k['science'].stereo_scope(mol,i)]
        return template,mol,unresolved

    def d20(self,template):
        import torch
        k=self.load();values=[];mask=[];issues=[]
        for name in k['D20']:
            try:
                value=float(k['functions'][name](template));valid=math.isfinite(value)
                if not valid:issues.append(name+':NONFINITE')
            except Exception as exc:value=float('nan');valid=False;issues.append(name+':'+repr(exc))
            values.append(value);mask.append(valid)
        shell=torch.full((len(k['wire'].GRAPH_NAMES),),float('nan'),dtype=torch.float64);flags=torch.zeros(len(shell),dtype=torch.bool)
        for name,value,valid in zip(k['D20'],values,mask):index=k['wire'].GRAPH_NAMES.index(name);shell[index]=value;flags[index]=valid
        return {'names':k['D20'],'values':values,'valid_mask':mask,'issues':issues},shell,flags

    def descriptors(self,source,template,mol,z,xyz,shell,flags):
        import numpy as np
        import torch
        k=self.load();edges=[(b.GetBeginAtomIdx(),b.GetEndAtomIdx()) for b in mol.GetBonds()]
        indices=np.asarray(edges,dtype=np.int64).reshape(-1,2).T
        raw={'smiles':source['isomeric_smiles'],'x':torch.tensor(z-1,dtype=torch.int64),'pos':torch.tensor(xyz,dtype=torch.float64),
            'rdkit_graph_desc':shell,'rdkit_graph_desc_mask':flags,'rdkit_bond_index':torch.tensor(indices,dtype=torch.int64),
            'geometry_context':'NEW_UFF_NO_PM7_INPUT','energy':None}
        output,issues=k['wire'].corrected_base(raw,{'smiles':source['isomeric_smiles']})
        require(output['rdkit_graph_desc'].dtype==torch.float64,'Original descriptor float64 seam differs')
        value=output['D_native_3D'];value['PBF_A']=value.pop('PBF')
        value['SASA_atom_A2']=None if value['SASA_atom_A2'] is None else value['SASA_atom_A2'].tolist()
        return value,issues,{'names':k['D20'],'values':output['rdkit_graph_desc'].tolist(),
            'valid_mask':output['rdkit_graph_desc_mask'].tolist(),'issues':[]}

    def writer(self):
        if self._writer is None:self._writer=module('_pubchem_capsule_family_writer',self.role('family_writer'))
        return self._writer

    def quality_reference(self,review):
        require(review.get('schema')=='ROOT_NO_PM7_UFF_D_MATCHED_TRAIN_REFERENCE_V1'
            and review.get('status')=='APPROVED_REFERENCE_APPLICATION_ONLY' and review.get('reviewer')=='root'
            and review.get('R_N_fit_as_TRAIN') is False
            and review.get('same_D_function_units_and_family_field_map_reviewed') is True
            and review.get('UFF_D3_vs_original_TRAIN_domain_difference_reviewed') is True,
            'Original independently approved reference-domain application required')
        fields=load(verify(review['field_map_reference']));cfg=load(verify(review['original_mask_config_reference']))
        selected=[f for f in fields if f['task'] in ('D20','D3')]
        names=module('_pubchem_capsule_quality_names',self.role('D_names')).D20_NAMES
        require(len(selected)==27 and len({f['field_id'] for f in selected})==27
            and {f['source_path'] for f in selected if f['task']=='D20'}==set(names)
            and {f['source_path'] for f in selected if f['task']=='D3'}=={'PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2','SASA_atom_A2'},
            'Unchanged original20+7 field map required')
        for pin in cfg['adapter_source_pins']:self.transport.verify(pin)
        calibration=load(verify(review['TRAIN_calibration_reference']));domain=load(verify(review['TRAIN_reference_domain_reference']))
        require(calibration['fit_role']==domain['fit_role']=='TRAIN_ONLY'
            and domain['calibration_reference']==review['TRAIN_calibration_reference']
            and domain['coverage_fingerprint']==calibration['coverage_fingerprint']
            and domain['actual_source_and_role_census_closed'] is True
            and all(str(f['field_id']) in calibration['fields'] for f in selected),'Original TRAIN-only reference/closed scope required')
        return selected,cfg,calibration

    def quality_init(self,review):
        selected,cfg,calibration=self.quality_reference(review);resolved=copy.deepcopy(cfg)
        resolved['adapter_source_pins']=[{**pin,'path':str(self.transport.verify(pin))} for pin in cfg['adapter_source_pins']]
        folder=self.role('label_support').parent
        for name,role in (('support','label_support'),('scan_v2','label_scan')):
            prior=sys.modules.get(name);require(prior is None or Path(prior.__file__).absolute()==self.role(role),
                'Fresh quality namespace required')
        sys.path.insert(0,str(folder))
        try:
            support=importlib.import_module('support');common,masks=support.legacy(resolved);scan=importlib.import_module('scan_v2')
        finally:sys.path.pop(0)
        from ..no_pm7_uff_d_main_v1 import families as original
        # Same normal initialization state as original quality_init. Original
        # task_components/masks/crosschecks/reviews/quality_packet objects stay
        # unchanged; only metadata paths resolve to actual verified replicas.
        original.QUALITY.update(common=common,masks=masks,scan=scan,fields=selected,calibration=calibration['fields'])
