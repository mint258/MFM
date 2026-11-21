"""The single registered F1 shared-parameter/method-embedding unit test."""
import json
from types import SimpleNamespace
import numpy as np
import torch
from phychem_mfm.phase1.v31_loader import TrainingView
from phychem_mfm.phase1.v31_training import V31PDModel


def test_paired_fields_share_head_parameters_and_method_vectors_change_outputs(tmp_path):
    class Encoder(torch.nn.Module):
        latent_dim=8
        def __init__(self):
            super().__init__();self.anchor=torch.nn.Parameter(torch.ones(()))
    columns=[];fields=[];layout={};pairs=[]
    for quantity,axes in [('energy',('value',)),('dipole',tuple('xyz'))]:
        pair=dict(quantity=quantity)
        for method,side in [('pm7','PM7_fields'),('xtb','xTB_fields')]:
            names=[];indices=[];target=method+'_'+quantity
            for axis in axes:
                name=method+'.'+quantity+'.'+axis;column=len(columns);names.append(name);indices.append(column)
                columns.append(dict(field_key=name,column_index=column,family='multipole' if quantity=='dipole' else 'energy',
                    level='molecule_vector' if quantity=='dipole' else 'molecule',kind='vector' if quantity=='dipole' else 'scalar'))
                fields.append(dict(field_key=name,group='P',target_id=target,selectors=[[23,column,'mol_labels']]))
            if quantity=='dipole':layout[target]=dict(array_name='mol_labels',column_indices=indices,kind='vector')
            pair[side]=names
        pairs.append(pair)
    schema=dict(columns={'mol_labels':columns},target_layout=layout,source_D3_reference={'sha256':'a'*64})
    norms={column['field_key']:dict(fit_role='TRAIN',center=0.,scale=1.) for column in columns}
    view=TrainingView(schema,dict(fields=fields),norms)
    path=tmp_path/'pairs.json';path.write_text(json.dumps(dict(pairs=pairs)))
    model=V31PDModel(Encoder(),view,p_recipe=dict(fidelity_pairs=str(path),method_embedding_dim=8))
    model.configure_step_overhead(dict(grouped_fields=True,head_checkpointing=False))
    fidelity=model.fidelity_heads
    for pair in pairs:
        left=model.selections[pair['PM7_fields'][0]][0];right=model.selections[pair['xTB_fields'][0]][0]
        lkey,lmethod=fidelity.bindings[left];rkey,rmethod=fidelity.bindings[right]
        assert lkey==rkey and lmethod==0 and rmethod==1
        assert tuple(fidelity.heads[lkey].parameters())==tuple(fidelity.heads[rkey].parameters())
    with torch.no_grad():
        fidelity.method_embedding.weight[0].zero_();fidelity.method_embedding.weight[1].fill_(.25)
        for core in fidelity.heads.values():
            for parameter in core.parameters():parameter.fill_(.1)
    h=torch.arange(32,dtype=torch.float32).reshape(4,8)/16
    batch=SimpleNamespace(batch=torch.tensor([0,0,1,1]),pos=torch.tensor([[-1.,0.,0.],[1.,1.,0.],[0.,-1.,0.],[1.,1.,1.]]))
    samples=[dict(targets={column['field_key']:SimpleNamespace(valid=np.ones((1,1),dtype=bool))
                         for column in columns}) for _ in range(2)]
    prediction=model.predict(samples,groups=('P',),clean_features=h,clean_batch=batch)
    for pair in pairs:
        left=torch.cat([prediction[name] for name in pair['PM7_fields']],-1)
        right=torch.cat([prediction[name] for name in pair['xTB_fields']],-1)
        assert not torch.allclose(left,right)
