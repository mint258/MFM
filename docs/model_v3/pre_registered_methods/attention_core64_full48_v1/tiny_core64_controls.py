"""Inline actual core64 helper/class controls, separate from all48 model cases."""
import math


def run():
    import torch
    from phychem_mfm.model.attention import DenseGeoSelfAttention
    from phychem_mfm.model.v3_architecture import SharedPairAttention
    from phychem_mfm.model.v3_attention_numerics import (
        CORE64_DIAGNOSTIC, diagnostic_core64_logits, diagnostic_core64_value)
    import phychem_mfm.model.attention as dense_module
    import phychem_mfm.model.v3_architecture as pair_module
    def need(ok, message):
        if not ok: raise ValueError(message)
    old = (torch.get_float32_matmul_precision(), torch.backends.cuda.matmul.allow_tf32,
           torch.backends.cudnn.allow_tf32)
    rng = torch.cuda.get_rng_state()
    records, handles = [], []
    originals = [(module, module.diagnostic_core64_logits, module.diagnostic_core64_value)
                 for module in (dense_module, pair_module)]
    current = [None]
    def logits_spy(q, k):
        result = diagnostic_core64_logits(q, k)
        records.append({'class':current[0], 'port':'QK',
                        'Q':str(q.dtype),'K':str(k.dtype),'output':str(result.dtype)})
        return result
    def value_spy(p, v, mask, *, attention_dropout=None):
        result = diagnostic_core64_value(p, v, mask, attention_dropout=attention_dropout)
        records.append({'class':current[0], 'port':'AV',
                        'P':str(p.dtype),'V_external':str(v.dtype),'context_public':str(result.dtype)})
        return result
    try:
        torch.set_float32_matmul_precision('highest')
        torch.backends.cuda.matmul.allow_tf32 = torch.backends.cudnn.allow_tf32 = False
        with torch.autocast(device_type='cuda', enabled=False), torch.enable_grad():
            q = torch.tensor([[[[1.,2.],[-1.,0.]]]],device='cuda:0',requires_grad=True)
            k = torch.tensor([[[[2.,-1.],[1.,3.]]]],device='cuda:0',requires_grad=True)
            actual = diagnostic_core64_logits(q,k)
            expected = torch.tensor([[[[0.,7.],[-2.,-1.]]]],device='cuda:0',dtype=torch.float64)/math.sqrt(2)
            need(torch.equal(actual,expected),'Tiny hand-computed QK64 oracle differs')
            actual.sum().backward()
            expected_q = (torch.tensor([3.,2.],device='cuda:0',dtype=torch.float64)/math.sqrt(2)).float()
            expected_k = (torch.tensor([0.,2.],device='cuda:0',dtype=torch.float64)/math.sqrt(2)).float()
            need(torch.equal(q.grad,expected_q.expand_as(q)) and torch.equal(k.grad,expected_k.expand_as(k)),
                 'Tiny analytic Q/K gradients differ')
            logits = torch.zeros((1,1,4,4),device='cuda:0',dtype=torch.float64,requires_grad=True)
            values = torch.tensor([[[[1.,2.],[3.,0.],[-1.,2.],[5.,4.]]]],device='cuda:0',requires_grad=True)
            mask = torch.ones((1,4),device='cuda:0',dtype=torch.bool)
            probability = logits.softmax(-1)
            output = diagnostic_core64_value(probability,values,mask)
            need(output.dtype == torch.float32 and torch.equal(output,torch.full_like(output,2.)),
                 'Tiny dyadic centered core output differs')
            (output[0,0,0]*torch.tensor([1.,-2.],device='cuda:0')).sum().backward()
            expected_l = torch.zeros_like(logits)
            expected_l[0,0,0] = torch.tensor([-.25,1.25,-.75,-.25],device='cuda:0',dtype=torch.float64)
            need(torch.equal(logits.grad,expected_l) and torch.equal(values.grad,torch.tensor([.25,-.5],device='cuda:0').expand_as(values)),
                 'Tiny analytic softmax/V gradients differ')
            mass = torch.tensor([[[[0.,.125,.125,.125]]*4]],device='cuda:0',dtype=torch.float64)
            anchored = torch.tensor([[[[99.],[2.],[4.],[6.]]]],device='cuda:0',requires_grad=True)
            anchor_mask = torch.tensor([[False,True,True,True]],device='cuda:0')
            answer = diagnostic_core64_value(mass,anchored,anchor_mask)
            answer[0,0,0,0].backward()
            need(torch.equal(answer,torch.full_like(answer,2.75)) and
                 torch.equal(anchored.grad,torch.tensor([[[[0.],[.75],[.125],[.125]]]],device='cuda:0')),
                 'Tiny first-valid/non-detached anchor control differs')
            for module,_,_ in originals:
                module.diagnostic_core64_logits = logits_spy
                module.diagnostic_core64_value = value_spy
            linear_dtypes = []
            x = torch.arange(24,device='cuda:0',dtype=torch.float32).reshape(2,3,4)/17
            pos = torch.tensor([[[0.,0.,0.],[1.,.2,.3],[0.,0.,0.]],
                                [[.1,.2,.3],[.4,.8,1.],[.9,.3,.7]]],device='cuda:0')
            native = torch.tensor([[True,True,False],[True,True,True]],device='cuda:0')
            for kind in ('DenseGeoSelfAttention','SharedPairAttention'):
                current[0] = kind
                with torch.random.fork_rng(devices=[]):
                    torch.random.default_generator.manual_seed(64123)
                    base = DenseGeoSelfAttention(4,1,dropout=0.,attention_aggregation_mode=CORE64_DIAGNOSTIC)
                    module = base if kind=='DenseGeoSelfAttention' else SharedPairAttention(base,4)
                module.eval().to('cuda:0')
                for name in ('qkv','proj','dist_mlp' if kind=='DenseGeoSelfAttention' else 'pair_projection'):
                    child = getattr(module,name)
                    handles.append(child.register_forward_hook(
                        lambda _,args,out,name=name: linear_dtypes.append((name,str(args[0].dtype),str(out.dtype)))))
                if kind=='DenseGeoSelfAttention':
                    result,public_p = module(x,pos,native)
                    need(public_p.dtype==torch.float32,'Public Dense auxiliary weights must stay FP32')
                else:
                    pair = torch.arange(72,device='cuda:0',dtype=torch.float32).reshape(2,3,3,4)/31
                    result = module(x,pair,torch.cdist(pos,pos),native)
                need(result.dtype==torch.float32 and bool(torch.isfinite(result).all()) and bool(result.abs().sum()>0),
                     'Actual tiny class must return finite nonzero FP32')
                for handle in handles:handle.remove()
                handles.clear()
            need(len(records)==4 and sum(r['port']=='QK' for r in records)==2 and
                 all(r['Q']==r['K']=='torch.float32' and r['output']=='torch.float64'
                     for r in records if r['port']=='QK') and
                 all(r['P']=='torch.float64' and r['V_external']==r['context_public']=='torch.float32'
                     for r in records if r['port']=='AV'),'Actual core dtype ports differ')
            need(len(linear_dtypes)==6 and all(a==b=='torch.float32' for _,a,b in linear_dtypes),
                 'QKV/bias/projection must remain FP32')
            rejected=[]
            for label,p,v,m,drop in (
                ('all_masked',probability.detach(),values.detach(),torch.zeros_like(mask),None),
                ('empty',probability.detach()[:,:,:0,:0],values.detach()[:,:,:0],mask[:,:0],None),
                ('bf16_external',probability.detach(),values.detach().bfloat16(),mask,None),
                ('rounded_probability',probability.detach().float(),values.detach(),mask,None),
                ('active_dropout',probability.detach(),values.detach(),mask,torch.nn.Dropout(.25).train())):
                state=torch.cuda.get_rng_state()
                try:diagnostic_core64_value(p,v,m,attention_dropout=drop)
                except ValueError:rejected.append(label)
                else:raise ValueError('Tiny unsupported input admitted: '+label)
                need(torch.equal(state,torch.cuda.get_rng_state()),'Guard consumed CUDA RNG')
            need(torch.equal(rng,torch.cuda.get_rng_state()),'Tiny controls changed CUDA RNG')
            return {'scope':'INLINE_TINY_ACTUAL_CORE64_HELPER_AND_CLASSES_NOT_FULL48',
                'arithmetic_scope':'FP32_PARAMETERS_IO_WITH_FP64_ATTENTION_CORE_DIAGNOSTIC',
                'dtype_observation':'PyTorch operand/return dtypes; not hardware-accumulator proof',
                'actual_attention_forward_calls':2,'analytic_QK_gradient':True,
                'analytic_softmax_value_gradient':True,'non_detached_first_valid_anchor':True,
                'actual_dtype_ports':records,'FP32_linear_ports':linear_dtypes,'guard_rejections':rejected,
                'CUDA_RNG_unchanged':True,'scientific_cases_added':0,'encoder_forwards':0,
                'formal_FP32_gate_satisfied':False,'model_freeze_candidate':False}
    finally:
        for handle in handles:handle.remove()
        for module,qk,value in originals:
            module.diagnostic_core64_logits= qk
            module.diagnostic_core64_value= value
        torch.set_float32_matmul_precision(old[0])
        torch.backends.cuda.matmul.allow_tf32,torch.backends.cudnn.allow_tf32=old[1:]
