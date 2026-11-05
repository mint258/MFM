"""Actual candidate helper on tiny CUDA operands; not additional scientific cases."""
def run():
    import torch
    from phychem_mfm.model.v3_attention_numerics import centered_attention_value
    def need(value,message):
        if not value:raise ValueError(message)
    old = (torch.get_float32_matmul_precision(),torch.backends.cuda.matmul.allow_tf32,torch.backends.cudnn.allow_tf32)
    try:
        torch.set_float32_matmul_precision('highest')
        torch.backends.cuda.matmul.allow_tf32 = torch.backends.cudnn.allow_tf32 = False
        with torch.autocast(device_type='cuda',enabled=False),torch.enable_grad():
            logits = torch.zeros((1,2,4,4),device='cuda:0',requires_grad=True)
            values = (torch.arange(32,device='cuda:0',dtype=torch.float32).reshape(1,2,4,4)/8).requires_grad_()
            mask = torch.ones((1,4),device='cuda:0',dtype=torch.bool)
            p = logits.softmax(-1)
            original = torch.matmul(p,values)
            centered = centered_attention_value(p,values,mask,attention_dropout=None)
            need(torch.equal(original.view(torch.int32),centered.view(torch.int32)), 'Tiny dyadic forward mismatch')
            coefficients = torch.arange(1,33,device='cuda:0',dtype=torch.float32).reshape_as(centered)/8
            left = torch.autograd.grad((original*coefficients).sum(),(logits,values),retain_graph=True)
            right = torch.autograd.grad((centered*coefficients).sum(),(logits,values))
            need(all(torch.equal(a.view(torch.int32),b.view(torch.int32)) for a,b in zip(left,right)),
                 'Tiny dyadic logits/V gradients differ')
            constant = torch.tensor([.25,.5,1.,2.],device='cuda:0').reshape(1,1,1,4).expand(1,2,4,4).clone()
            actual = centered_attention_value(p.detach(),constant,mask,attention_dropout=None)
            need(torch.equal(actual,constant),'Constant-V actual helper differs')
            rejected = []
            for label,probabilities,v,m,drop in (
                ('all_masked',p.detach(),values.detach(),torch.zeros_like(mask),None),
                ('empty',p.detach()[:,:,:0,:0],values.detach()[:,:,:0,:],mask[:,:0],None),
                ('bf16',p.detach().bfloat16(),values.detach().bfloat16(),mask,None),
                ('active_dropout',p.detach(),values.detach(),mask,torch.nn.Dropout(.25).train())):
                state = torch.cuda.get_rng_state()
                try:centered_attention_value(probabilities,v,m,attention_dropout=drop)
                except ValueError:rejected.append(label)
                else:raise ValueError('Unsupported tiny input admitted: '+label)
                need(torch.equal(state,torch.cuda.get_rng_state()),'A guard consumed CUDA RNG')
        return {'scope':'INLINE_TINY_CUDA_ACTUAL_CANDIDATE_HELPER_NOT_FULL48',
            'successful_helper_calls':2,'dyadic_forward_bitwise':True,'dyadic_logits_and_V_gradients_bitwise':True,
            'constant_V_exact':True,'guard_rejections':rejected,'guard_CUDA_RNG_unchanged':True,
            'scientific_cases_added':0,'full_FP64_encoder_forwards':0}
    finally:
        torch.set_float32_matmul_precision(old[0])
        torch.backends.cuda.matmul.allow_tf32,torch.backends.cudnn.allow_tf32 = old[1:]
