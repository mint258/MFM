"""Fit A1/A2/A5 once per adopted label recipe using the clean TRAIN cohort."""
from concurrent.futures import ProcessPoolExecutor
import argparse,json,multiprocessing
from pathlib import Path
import numpy as np
from phychem_mfm.phase1.p_recipe_data import PRecipeDataset,dataset_configuration,read_json,physical_state_groups
from phychem_mfm.phase1.p_recipe_fit import fit_parameters
from phychem_mfm.phase1.v31_training import head_layout
R=Path('/share/home/zixiao/descriptor_analysis')


def initialize(configuration,names,differences):
 global DATA,NAMES,DIFFERENCES
 DATA=PRecipeDataset(**configuration);NAMES=names;DIFFERENCES=differences
 needed=set(names)|set(differences.values());DATA.view.fields=[f for f in DATA.view.fields if f['name'] in needed]


def read_block(indices):
 counts=[];values={n:[] for n in NAMES}
 for molecule,conformer in indices:
  sample=DATA.read(molecule,conformer);counts.append(np.bincount(sample['Z'],minlength=119)[1:119])
  for name in NAMES:
   target=sample['targets'][name];value=target.raw.astype(np.float64);valid=target.valid.copy()
   if name in DIFFERENCES:
    neutral=sample['targets'][DIFFERENCES[name]];value=value-neutral.raw.astype(np.float64);valid=valid&neutral.valid
   values[name].append(np.where(valid,value,np.nan))
 return np.asarray(counts,dtype=np.int32),{n:np.concatenate(v,axis=0) for n,v in values.items()}


def fit(c,output,count=128000,workers=8):
 reader=dataset_configuration({**c,'label_parameters':None,'subset_molecules':None})
 data=PRecipeDataset(**reader);recipe=c.get('p_recipe',{})
 heads,fields,routes,selections,onsite=head_layout(data.view)
 enabled={f.name for f in fields if f.group=='P' and (c.get('fields') is None or f.name in c['fields'])}
 definitions={f['name']:f for f in data.view.fields}
 differences={}
 if recipe.get('state_difference',False):
  groups=physical_state_groups(data.view,enabled)
  differences={name:members['neutral'] for members in groups.values() for state,name in members.items() if state!='neutral'}
  if not differences:raise ValueError('No registered neutral/state pairs for A2')
 a1=[]
 if recipe.get('element_residual',False):
  a1=[name for name in read_json(R/'runs/p_recipe_20261113/D6_compact_metadata.json')['needs_A1']
      if name in enabled and data.view.normalizations[name].get('element_reference') is None]
 tails=set()
 if recipe.get('heavy_tail',False):
  decision=read_json(R/'runs/p_recipe_20261113/D2_decision.json')
  if not decision['A5']:raise ValueError('A5 is not triggered by D2')
  marked=set(decision['marked_fields']);tails={n for n in enabled if selections[n][0] in marked}
 needed=set(a1)|set(differences)|tails
 # A physical vector keeps all registered components and one isotropic scale.
 selected_heads={selections[n][0] for n in needed}
 needed|={n for n in enabled if selections[n][0] in selected_heads}
 if not needed:
  parameters=dict(normalizations={},state_difference={},heavy_tail={},fit={})
 else:
  order=np.random.default_rng(20261112).permutation(data.indices);rng=np.random.default_rng(20261112)
  counts=[];values={n:[] for n in needed};collected=0;target=min(count,len(order));valid_a1={n:0 for n in a1}
  with ProcessPoolExecutor(workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize,initargs=(reader,tuple(sorted(needed)),differences)) as pool:
   while collected<target:
    chosen=order[collected:target];choices=[(int(m),int(rng.choice(data.choices(int(m))))) for m in chosen]
    blocks=[choices[i:i+256] for i in range(0,len(choices),256)]
    for i,(z,observed) in enumerate(pool.map(read_block,blocks,chunksize=1)):
     counts.append(z);collected+=len(z)
     for name,value in observed.items():
      values[name].append(value)
      if name in valid_a1:valid_a1[name]+=int(np.isfinite(value).all(1).sum())
     if (i+1)%32==0:print(json.dumps(dict(run=c['run'],fit_molecules=collected,target_molecules=target)),flush=True)
    if a1 and min(valid_a1.values())<100000 and collected<len(order):
     minimum=min(valid_a1.values());estimate=int(np.ceil(105000*collected/minimum)) if minimum else collected+count
     target=min(len(order),max(collected+16384,estimate))
     print(json.dumps(dict(run=c['run'],A1_valid_molecules=valid_a1,extend_TRAIN_to=target)),flush=True)
  parameters=fit_parameters(data.view.normalizations,definitions,selections,np.concatenate(counts),{n:np.concatenate(v) for n,v in values.items()},a1_fields=a1,differences=differences,tail_fields=tails)
  parameters.update(fit_molecules=collected,fit_seed=20261112,fit_role='TRAIN',source=c['source'],cohort=c['corpus'])
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(parameters,indent=2)+'\n')
 data.close();print(json.dumps(dict(status='LABEL_PARAMETERS_FITTED',path=str(output),A1_fields=len(a1),A2_fields=len(differences),A5_fields=len(tails))),flush=True)
 return parameters

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--configuration',required=True);p.add_argument('--output',required=True);p.add_argument('--molecules',type=int,default=128000);p.add_argument('--workers',type=int,default=8);a=p.parse_args()
 fit(read_json(a.configuration),a.output,a.molecules,a.workers)