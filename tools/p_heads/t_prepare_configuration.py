"""Prepare only user-authorized fresh T configurations from an explicit published base."""
import argparse,copy,pathlib
from h_resources import REPO,CONTROL,load,save
RECOVERY_KEYS=('resume','resume_samples','resume_from_output','attempt','required_gpu_uuid','recovery_reason','replaces_run','source_last_samples','rollback_samples')
def fresh(source,arm,seed=0):
    c=copy.deepcopy(source)
    for key in RECOVERY_KEYS:c.pop(key,None)
    c.update(arm=arm,seed=seed,run='p_heads_'+arm+'_seed'+str(seed))
    c['output']=str(CONTROL/'training'/c['run']);c['results_directory']='results/p_heads/T'
    c['control_directory']=str(CONTROL/'control')
    c['handoff_request']=str(CONTROL/'control'/(c['run']+'_request.json'))
    c['handoff_ack']=str(CONTROL/'control'/(c['run']+'_ack.json'))
    return c

def prepare(base,arm,reference):
    c=fresh(base,arm)
    if arm=='T1':
        fields=sorted(load(REPO/'results/p_heads/T/T1_acceptance.json')['heads'])
        if len(fields)!=45:raise ValueError('Use exactly the existing45 decoder fields')
        c['p_recipe'].update(atom_attention_decoder=True,atom_decoder_fields=fields)
    elif arm=='T4':c['p_recipe']['pma_sum_gate_one']=True
    elif arm=='T5':c['p_recipe']['simple_molecular_readout']=True
    elif arm=='T2_confirm':
        c['p_recipe']['physical_constraint_heads']=load(REPO/'configs/p_heads/T/T2_seed0.json')['p_recipe']['physical_constraint_heads']
    else:raise ValueError('Only directive-authorized new configurations')
    c['p_heads_reference']=dict(seed0_configuration=reference,seed1_configuration=None,reuse_external_seed1=arm in ('T1','T2_confirm'))
    return c

def main():
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=['T1','T4','T5','T2_confirm'],required=True)
    p.add_argument('--base-configuration',required=True);a=p.parse_args()
    base=load(a.base_configuration)
    if 'p_recipe' not in base:raise ValueError('Resolve CURRENT_BEST to its actual recipe configuration first')
    save(REPO/'configs/p_heads/T'/(a.arm+'_seed0.json'),prepare(base,a.arm,a.base_configuration))
if __name__=='__main__':main()