"""P-study cohort and opt-in reversible target definitions."""
from dataclasses import replace
import json
from pathlib import Path
import numpy as np
from .v31_loader import MFM4Dataset,normalize_values
from .v31_training import element_offset

def read_json(path):return json.loads(Path(path).read_text())

def train_indices(configuration):
 corpus=read_json(configuration['corpus']);indices=np.load(corpus['train_indices'])
 count=configuration.get('subset_molecules')
 if count is not None:
  order=np.random.default_rng(configuration.get('subset_seed',20261112)).permutation(len(indices))
  indices=indices[order[:count]]
 return indices

def validation_indices(configuration,count=2000):
 import pyarrow.parquet as pq
 corpus=read_json(configuration['corpus']);manifest=read_json(Path(corpus['source_root'])/'manifest.json')
 common=read_json(manifest['full_source_dependencies']['common']);mids=[]
 for ref in common['membership_tables']:
  table=pq.read_table(ref['path'],columns=['molecule_id','effective_role','common_population_v1'])
  mids.extend(r['molecule_id'] for r in table.to_pylist() if r['effective_role']=='VAL' and r['common_population_v1'])
 chosen=set(np.random.default_rng(20261112).choice(sorted(mids),count,replace=False).tolist())
 table=pq.read_table(Path(manifest['split_roots']['FULL'])/'id_map.parquet',columns=['molecule_id','molecule_index'],filters=[('record_kind','=','M')])
 return np.asarray([r['molecule_index'] for r in table.to_pylist() if r['molecule_id'] in chosen],dtype=np.int64)

class PRecipeDataset(MFM4Dataset):
 def __init__(self,*args,label_parameters=None,**kwargs):
  super().__init__(*args,**kwargs)
  self.label_parameters={} if label_parameters is None else read_json(label_parameters)
  for name,spec in self.label_parameters.get('normalizations',{}).items():
   self.view.normalizations[name]=spec
   for field in self.view.fields:
    if field['name']==name:field['normalization']=spec
 def read(self,molecule,conformer):
  sample=super().read(molecule,conformer);original=sample['targets'];sample['original_targets']=original
  if not self.label_parameters:return sample
  differences=self.label_parameters.get('state_difference',{});tails=self.label_parameters.get('heavy_tail',{});targets={}
  for name,target in original.items():
   value=target.raw.astype(np.float64);valid=target.valid.copy()
   if name in differences:
    neutral=original[differences[name]];value=value-neutral.raw.astype(np.float64);valid=valid&neutral.valid
   if name in tails:
    tail=tails[name];offset=element_offset(sample['Z'],{'element_reference':tail.get('offset_reference')})
    value=value-offset;value=np.sign(value)*np.log1p(np.abs(value)/tail['m'])
   value=np.where(valid,value,np.nan).astype(np.float32)
   spec=self.view.normalizations[name]
   targets[name]=replace(target,raw=value,valid=valid,values=normalize_values(value,spec,Z=sample['Z']))
  sample['targets']=targets;return sample

def dataset_configuration(c,*,validation=False):
 return dict(root=c['root'],split='FULL' if validation else 'TRAIN',training_view=c['training_view'],
  normalizations=read_json(c['normalizations']),source=c['source'],order=c.get('order','fixed_random'),k=10,
  pprime=c['source']=='UFF',molecule_indices=validation_indices(c) if validation else train_indices(c),
  label_parameters=c.get('label_parameters'))

def original_predictions(model,predictions,samples,parameters):
 import torch
 from .p_recipe import heavy_tail
 result=model.original_predictions({n:v.double() for n,v in predictions.items()},samples)
 for name,tail in parameters.get('heavy_tail',{}).items():
  if name not in result:continue
  value=heavy_tail(result[name],tail['m'],inverse=True)
  reference=tail.get('offset_reference')
  if reference is not None:
   offsets=[element_offset(s['Z'],{'element_reference':reference}) for s in samples]
   value=value+value.new_tensor(offsets)[:,None]
  result[name]=value
 # A2's inverse uses the predicted neutral quantity, never its target.
 for name,neutral in parameters.get('state_difference',{}).items():
  if name in result:result[name]=result[name]+result[neutral]
 return result
def physical_state_groups(view,fields):
    """Match registered physical definitions, units and components within method."""
    states={'pm7_b':('PM7','neutral'),'pm7_anion':('PM7','anion'),
        'pm7_cation':('PM7','cation'),'pm7_water':('PM7','water'),
        'pm7_octanol':('PM7','octanol'),'xtb_singlepoint':('xTB','neutral'),
        'xtb_alpb_water':('xTB','water'),'xtb_alpb_octanol':('xTB','octanol')}
    metadata={m['field_key']:m for columns in view.schema['columns'].values() for m in columns}
    result={}
    for field in view.fields:
        name=field['name']
        if name not in fields or field['group']!='P':continue
        condition=name.split('.')[1].lower()
        if condition not in states:continue
        method,state=states[condition];m=metadata.get(field.get('source_field',name),{})
        path=m.get('source_path');unit=field.get('unit',m.get('unit'))
        if not path or not unit or unit in ('UNKNOWN','source_registry_unit'):continue
        physical=('dipole' if 'dipole' in path.lower() else
            'energy' if field['family']=='energy' or 'energy' in path.lower() or 'heat_of_formation' in path.lower() else
            'charge' if field['family']=='charge' else None)
        if physical is None:continue
        key=(method,physical,field['level'],path,str(m.get('component')),unit)
        result.setdefault(key,{})[state]=name
    return {key:members for key,members in result.items() if 'neutral' in members and len(members)>1}