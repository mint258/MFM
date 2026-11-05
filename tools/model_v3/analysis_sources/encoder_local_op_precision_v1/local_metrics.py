"""Same-component local drift summaries; never inject a reference into the model."""
import torch

def need(ok,message):
    if not ok:raise ValueError(message)

def record(value):
    value=value.double();flat=int(value.abs().argmax());width=value.shape[-1]
    return {'rows':value.shape[0],'channels':value.shape[-1],'components':value.numel(),
        'maxabs':float(value.abs().max()),'squared_sum':float(value.square().sum()),
        'rms':float(value.square().mean().sqrt()),'argmax':[flat//width,flat%width],
        'signed_at_argmax':float(value.reshape(-1)[flat])}

def summarize(roles,transforms):
    need(len(roles)==4 and len(transforms)==3,'Exactly four original roles required')
    names=set(roles[0]['ops'])
    need(all(set(row['ops'])==names for row in roles),'No selected module subset')
    need(all(row['batch_header']==roles[0]['batch_header'] and row['element_header']==roles[0]['element_header']
             and row['clean_rows_header']==roles[0]['clean_rows_header'] for row in roles),
         'Actual physical roles changed native graph/atom/view identities')
    observations=[];controls=[]
    for name in sorted(names):
        original=roles[0]['ops'][name]
        controls.append({'module':name,'state_mapping':original['state_mapping'],
            'roles':[{'replay':role['ops'][name]['replay'],'context':role['ops'][name]['context']} for role in roles]})
        for role_index,transform in enumerate(transforms,1):
            moved=roles[role_index]['ops'][name]
            need(original['kind']==moved['kind'] and len(original['ports'])==len(moved['ports']),'Local port topology differs')
            rotation=torch.tensor(transform['rotation_float64'],dtype=torch.float64)
            translation=torch.tensor(transform['translation_A'],dtype=torch.float64)
            input_rows=[]
            need(len(original['inputs'])==len(moved['inputs']),'Actual input set differs')
            for a,b in zip(original['inputs'],moved['inputs']):
                need(a['kind']==b['kind'] and a['values'].shape==b['values'].shape,'Input population differs')
                delta=b['values'].double()-(a['values'].double()@rotation+translation
                    if a['kind']=='position' else a['values'].double())
                input_rows.append({'kind':a['kind'],'law':'x@R+t' if a['kind']=='position' else 'invariant',
                    'physical_input_drift':record(delta),'base_raw_header':a['raw'],'moved_raw_header':b['raw']})
            for port,(base,changed) in enumerate(zip(original['ports'],moved['ports'])):
                need(base['denominator']==changed['denominator']
                     and base['actual'].shape==changed['actual'].shape==base['reference'].shape==changed['reference'].shape,
                     'Local output population/shape differs across actual transforms')
                actual=changed['actual'].double()-base['actual'].double()
                inherited=changed['reference']-base['reference']
                e0=base['actual'].double()-base['reference'];et=changed['actual'].double()-changed['reference']
                arithmetic=actual-inherited
                closure=float((actual-inherited-(et-e0)).abs().max())
                need(closure<=1e-10,'Signed same-input local arithmetic closure failed')
                terms={'F32_D':actual,'F64_same_actual_input_D':inherited,
                       'arithmetic_residual':arithmetic,'base_local_error':e0,'moved_local_error':et}
                at={}
                for target in ('F32_D','F64_same_actual_input_D','arithmetic_residual'):
                    flat=int(terms[target].abs().argmax());width=actual.shape[-1];r,c=flat//width,flat%width
                    at[target+'_argmax']={'physical_row':r,'channel_or_head':c,
                        'signed_tuple':{key:float(value[r,c]) for key,value in terms.items()}}
                observations.append({'module':name,'kind':original['kind'],'layer':original['layer'],'port':port,
                    'transform':transform['name'],'population':base['denominator'],
                    'statistics':{key:record(value) for key,value in terms.items()},'same_component':at,
                    'input_drift':input_rows,'signed_closure_maxabs':closure,
                    'inherited_input_scope':'Independent reference evaluated separately at each ACTUAL F32 input; no F64 upstream substitution',
                    'whole_model_cause_or_causal_layer_ranking':False})
    return {'observations':observations,'module_controls':controls,
        'all_local_F32_replays_bitwise':all(item['bitwise_equal'] for role in roles for op in role['ops'].values() for item in op['replay']),
        'local_module_count':len(names),'module_calls_per_role':len(names),
        'F64_encoder_forwards':0,'reference_outputs_injected':False}