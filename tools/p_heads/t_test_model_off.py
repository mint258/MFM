"""One whole PD-model off-path test against task-start source, no real checkpoint."""
import argparse,json,os,pathlib,shutil,subprocess,sys
from h_resources import REPO,CONTROL,guard,watchdog,save

CHANGED=('model/v3_latent.py','model/v3_heads.py','model/v31_grouped_heads.py','phase1/v31_training.py')

def worker(destination):
    from types import SimpleNamespace
    import numpy as np
    import torch
    from torch import nn
    from phychem_mfm.phase1.v31_training import V31PDModel
    from phychem_mfm.phase1.v31_loader import collate_samples
    torch.set_num_threads(1);torch.manual_seed(19)
    class Encoder(nn.Module):
        latent_dim=512
        def __init__(self):
            super().__init__();self.embedding=nn.Embedding(119,512);self.geometry=nn.Linear(3,512);self.mix=nn.Linear(512,512)
        def encode_atoms(self,batch):return self.mix(torch.nn.functional.silu(self.embedding(batch.x.reshape(-1))+self.geometry(batch.pos)))
    definitions=[dict(name='atom',group='P',family='charge',level='atom'),
        dict(name='pair',group='P',family='bonding',level='sparse_atom_pair'),
        dict(name='molecule',group='P',family='energy',level='molecule'),
        dict(name='force',group='P',family='force',level='atom_vector',representation='vector')]
    definitions += [dict(name='dipole.'+axis,group='P',family='multipole',level='molecule_vector',representation='vector',target_id='dipole',selectors=[[23,i,'mol_labels']]) for i,axis in enumerate('xyz')]
    schema=dict(columns={},source_D3_reference={'sha256':'a'*64},target_layout={'dipole':dict(kind='vector',column_indices=[0,1,2])})
    view=SimpleNamespace(fields=definitions,schema=schema,normalizations={})
    model=V31PDModel(Encoder(),view,forms='H1',pooling='registry',p_recipe=dict(pma_pooling=True,pma_uniform_weights=False,atom_attention_decoder=False,physical_constraint_heads={},atom_decoder_fields=[]))
    model.configure_step_overhead(dict(grouped_fields=True,head_checkpointing=False,distance_tiling=True,prepared_input=True))
    model.eval();samples=[]
    for i,z in enumerate(([6,1,8],[7,1])):
        n=len(z);pos=np.arange(n*3,dtype=np.float32).reshape(n,3)*.17
        index=np.asarray([[0,1],[1,0]],dtype=np.int64)
        targets={}
        for f in definitions:
            rows=n if f['level'] in ('atom','atom_vector') else 2 if f['level']=='sparse_atom_pair' else 1
            width=3 if f['level']=='atom_vector' else 1
            targets[f['name']]=SimpleNamespace(raw=np.zeros((rows,width),np.float32),valid=np.ones((rows,width),bool),pair_index=index if f['level']=='sparse_atom_pair' else None)
        samples.append(dict(molecule_index=i,conformer_index=0,Z=np.asarray(z,np.uint8),pos=pos,pos_perturbed=None,targets=targets,bonds=np.asarray([[0,1]],dtype=np.int64),bond_order=np.asarray([1],dtype=np.int64)))
    with torch.no_grad():
        outputs=model.predict(samples,groups=('P',))
        outputs['downstream_H0']=model.encode_atoms(collate_samples(samples))
        outputs['PMA_z']=model.p_recipe_pma.last_z
    guard(force=True);torch.save({name:value.detach().cpu() for name,value in outputs.items()},destination)

def main():
    p=argparse.ArgumentParser();p.add_argument('--worker');p.add_argument('--scratch');a=p.parse_args()
    if a.worker:return worker(pathlib.Path(a.worker))
    watchdog();root=pathlib.Path(a.scratch) if a.scratch else CONTROL/'off_path_golden';package=root/'current/phychem_mfm'
    if root.exists():raise FileExistsError('Do not silently repeat the producer test: '+str(root))
    root.mkdir();shutil.copytree(REPO/'current/phychem_mfm',package,ignore=shutil.ignore_patterns('__pycache__'))
    for relative in CHANGED:
        code=subprocess.check_output(['git','-C',str(REPO),'show','9d66cf3:current/phychem_mfm/'+relative])
        guard(force=True);(package/relative).write_bytes(code)
    files={}
    for label,current in (('old',root/'current'),('new',REPO/'current')):
        destination=root/(label+'_outputs.pt');environment=dict(os.environ,PYTHONPATH=str(current),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
        subprocess.run([sys.executable,'-B',str(pathlib.Path(__file__).resolve()),'--worker',str(destination)],env=environment,check=True)
        files[label]=destination
    import torch
    old=torch.load(files['old'],map_location='cpu',weights_only=True);new=torch.load(files['new'],map_location='cpu',weights_only=True)
    if set(old)!=set(new):raise AssertionError('Whole-model output fields differ')
    comparison={name:torch.equal(old[name],new[name]) for name in old}
    if not all(comparison.values()):raise AssertionError('Off-path output differs: '+str(comparison))
    save(REPO/'results/p_heads/T/model_off_path.json',dict(status='PASS',old_source='9d66cf3',new_source='current task implementation',whole_model='V31PDModel.predict with512d synthetic encoder',existing_PMA=True,grouped_fields=True,new_switches='All off/empty',torch_equal=comparison,real_checkpoint_reread=False))
    print('WHOLE_MODEL_OFF_PATH_PASS',comparison,flush=True)
if __name__=='__main__':main()
