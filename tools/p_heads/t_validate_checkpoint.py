"""Load the real B3 complete state through the unchanged default head routes, once."""
import json,pathlib,torch
from phychem_mfm.phase1.p_recipe_data import PRecipeDataset,dataset_configuration
from phychem_mfm.phase1.v2_s_training import s_model
from phychem_mfm.phase1.v31_training import V31PDModel
from h_resources import guard,save
R=pathlib.Path(__file__).resolve().parents[2]
torch.set_num_threads(1);guard(force=True)
c=json.loads((R/'configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/B3.json').read_text())
data=PRecipeDataset(**dataset_configuration(c))
model,_=s_model('C1-0','three');model.encoder.backbone.activation_checkpointing=False
pd=V31PDModel(model.encoder,data.view,forms=c['head_form'],pooling='registry',p_recipe=c['p_recipe'])
pd.configure_step_overhead(c['step_overhead'])
checkpoint=pathlib.Path(c['output'])/'samples_3000000.pt'
cp=torch.load(checkpoint,map_location='cpu',weights_only=True)
torch.nn.ModuleDict(dict(structural=model,pd=pd)).load_state_dict(cp['model'],strict=True)
result=dict(status='PASS',checkpoint=str(checkpoint),configuration=cp['configuration'],clock=cp['clock'])
save(R/'results/p_heads/T/B3_checkpoint_loading.json',result)
print(json.dumps(dict(status='PASS',checkpoint=str(checkpoint),clock=cp['clock'])),flush=True)
