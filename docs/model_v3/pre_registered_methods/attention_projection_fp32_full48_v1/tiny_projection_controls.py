"""Actual fixed helper, independent dyadic FP32 gradient controls; no encoders."""
def need(value, message):
    if not value:
        raise ValueError(message)

def run():
    import torch
    from phychem_mfm.model.v3_attention_projection import blocked_linear_fp32, K_BLOCK, DENSE_ROW_TILE
    need(K_BLOCK == 64 and DENSE_ROW_TILE == 128, 'Registered fixed method constants differ')
    need(torch.cuda.is_available() and torch.cuda.device_count() == 1, 'One admitted GPU required')
    previous = (torch.get_float32_matmul_precision(), torch.backends.cudnn.allow_tf32)
    cpu_rng, gpu_rng = torch.get_rng_state().clone(), torch.cuda.get_rng_state().clone()
    try:
        torch.set_float32_matmul_precision('highest')
        torch.backends.cudnn.allow_tf32 = False
        with torch.autocast('cuda', enabled=False), torch.enable_grad():
            x = torch.ones((2,192), device='cuda:0')
            w = torch.zeros((1,192), device='cuda:0')
            w[0,0], w[0,64], w[0,128] = 2.**24, 1., -(2.**24)
            answer = blocked_linear_fp32(x,w,torch.tensor([1.5],device='cuda:0'))
            need(torch.equal(answer,torch.full_like(answer,2.5)),
                 'Exact real cancellation/bias-once control differs')
            x = torch.zeros((1,128),device='cuda:0'); x[0,0],x[0,64] = 2.,3.; x.requires_grad_()
            w = torch.zeros((1,128),device='cuda:0'); w[0,0],w[0,64] = 5.,-1.; w.requires_grad_()
            b = torch.tensor([.5],device='cuda:0',requires_grad=True)
            y = blocked_linear_fp32(x,w,b)
            need(torch.equal(y,torch.full_like(y,7.5)), 'Independent affine scalar7.5 differs')
            first = torch.autograd.grad(.5*y.square().sum(),(x,w,b),create_graph=True)
            ex,ew = torch.zeros_like(x),torch.zeros_like(w)
            ex[0,0],ex[0,64] = 37.5,-7.5
            ew[0,0],ew[0,64] = 15.,22.5
            need(all(torch.equal(a,z) for a,z in zip(first,(ex,ew,torch.full_like(b,7.5)))),
                 'Independent input/weight/bias analytic first derivatives differ')
            u,v = torch.zeros_like(x),torch.zeros_like(w)
            u[0,0],u[0,64] = 1.,-1.
            v[0,0],v[0,64] = .5,.25
            c = torch.full_like(b,-.5)
            directional = sum((g*d).sum() for g,d in zip(first,(u,v,c)))
            second = torch.autograd.grad(directional,(x,w,b),create_graph=True)
            ex.zero_();ew.zero_()
            ex[0,0],ex[0,64] = 40.,-5.375
            ew[0,0],ew[0,64] = 22.,14.25
            need(all(torch.equal(a,z) for a,z in zip(second,(ex,ew,torch.full_like(b,7.25)))),
                 'Independent three-block Hessian-vector controls differ')
            second_direction = sum((g*d).sum() for g,d in zip(second,(u,v,c)))
            need(float(second_direction) == 56.3125, 'Independent full second directional scalar differs')
            rejected = []
            for dtype in (torch.float64,torch.bfloat16,torch.float16):
                state = torch.cuda.get_rng_state().clone()
                try:
                    blocked_linear_fp32(torch.ones((1,128),device='cuda:0',dtype=dtype),
                                        torch.ones((1,128),device='cuda:0',dtype=dtype))
                except ValueError:
                    rejected.append(str(dtype))
                else:
                    raise ValueError('Unsupported helper dtype admitted')
                need(torch.equal(state,torch.cuda.get_rng_state()), 'Guard consumed GPU RNG')
            with torch.autocast('cuda',dtype=torch.bfloat16):
                try:
                    blocked_linear_fp32(x,w,b)
                except ValueError:
                    rejected.append('active_cuda_autocast')
                else:
                    raise ValueError('Active AMP admitted')
            need(torch.equal(cpu_rng,torch.get_rng_state())
                 and torch.equal(gpu_rng,torch.cuda.get_rng_state()), 'Tiny controls changed RNG')
            return {'scope':'INLINE_TINY_ACTUAL_K64_FP32_HELPER_NOT_FULL48',
                'K_block':K_BLOCK,'dense_row_tile':DENSE_ROW_TILE,
                'cancellation_bias_once':True,'independent_all_first_derivatives':True,
                'independent_all_Hessian_vector_blocks':True,'independent_second_direction':56.3125,
                'guard_rejections':rejected,'CPU_and_CUDA_RNG_unchanged':True,
                'FP64_arithmetic':False,'nonFP32_guard_inputs_not_arithmetic':True,
                'encoder_forwards':0,'scientific_cases_added':0,'scientific_adoption':False}
    finally:
        torch.set_float32_matmul_precision(previous[0])
        torch.backends.cudnn.allow_tf32 = previous[1]
