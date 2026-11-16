"""Fill final A checkpoint provenance from the exact already-used payloads."""
import torch
from resources import REPO,load,save,guard
if __name__=='__main__':
 p=REPO/'results/p_followup/A_collapse_composition/summary.json';result=load(p)
 keys=['condition','distance_bias','views','samples','subset_molecules','subset_size','train_molecules','seed','source','head_form','root','training_view','normalizations','label_parameters','batch_size','p_recipe']
 for name,c in result['conditions'].items():
  if c.get('status')!='COMPLETE':continue
  guard();payload=torch.load(c['source']['checkpoint'],map_location='cpu',weights_only=True)
  config=payload.get('configuration',{});record={k:config.get(k) for k in keys if k in config}
  c['source']['checkpoint_configuration']=record
  if c['source'].get('status')=='EXISTS':c['source']['reason']=None
  print('CHECKPOINT_CONFIGURATION',name,record,flush=True)
  del payload
 save(p,result)