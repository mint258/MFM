"""Actual fixed helper, independent dyadic FP32 gradient controls; no encoders."""
def need(value, message):
    if not value:
        raise ValueError(message)

def projection_controls():
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

def run():
    import torch
    from phychem_mfm.model.v3_geometry_fp32 import (
        residual_distance_fp32, residual_pairwise_distance_fp32,
        GEOMETRY_TILE_ROWS, SPLITTER, RESIDUAL_GEOMETRY)
    projection = projection_controls()  # Same original actual-helper controls, zero encoders.
    need(GEOMETRY_TILE_ROWS == 65536 and SPLITTER == 4097.0,
         'Frozen residual-expansion constants differ')
    cpu_rng, gpu_rng = torch.get_rng_state().clone(), torch.cuda.get_rng_state().clone()
    previous = (torch.get_float32_matmul_precision(), torch.backends.cudnn.allow_tf32)
    try:
        torch.set_float32_matmul_precision('highest')
        torch.backends.cudnn.allow_tf32 = False
        with torch.autocast('cuda', enabled=False), torch.enable_grad():
            raw = torch.tensor([[2.**24,1.,0.]], device='cuda:0')
            other = torch.tensor([[-1.,0.,0.]], device='cuda:0')
            square = residual_distance_fp32(raw, other, squared=True)
            need(torch.equal(square, torch.tensor([2.**48+2.**25], device='cuda:0')),
                 'Independent real raw-subtraction-tail squared oracle differs')
            left = torch.tensor([[1.,2.,3.]], device='cuda:0', requires_grad=True)
            right = torch.tensor([[-1.,1.,3.]], device='cuda:0', requires_grad=True)
            coefficient = torch.tensor([2.], device='cuda:0', requires_grad=True)
            objective = (coefficient*residual_distance_fp32(left,right,squared=True)).sum()
            need(float(objective) == 10., 'Independent real squared-distance scalar differs')
            first = torch.autograd.grad(objective,(left,right,coefficient),create_graph=True)
            expected = (torch.tensor([[8.,4.,0.]],device='cuda:0'),
                        torch.tensor([[-8.,-4.,0.]],device='cuda:0'),
                        torch.tensor([5.],device='cuda:0'))
            need(all(torch.equal(g,e) for g,e in zip(first,expected)),
                 'Independent both-coordinate/coefficient first derivatives differ')
            directions = (torch.tensor([[1.,0.,1.]],device='cuda:0'),
                          torch.tensor([[0.,1.,-1.]],device='cuda:0'),
                          torch.tensor([.5],device='cuda:0'))
            directional = sum((g*d).sum() for g,d in zip(first,directions))
            second = torch.autograd.grad(directional,(left,right,coefficient))
            expected_second = (torch.tensor([[6.,-3.,8.]],device='cuda:0'),
                               torch.tensor([[-6.,3.,-8.]],device='cuda:0'),
                               torch.tensor([2.],device='cuda:0'))
            need(all(torch.equal(g,e) for g,e in zip(second,expected_second))
                 and float(sum((g*d).sum() for g,d in zip(second,directions))) == 26.,
                 'Independent complete three-block second derivative differs')
            position = torch.tensor([[3.,4.,0.]],device='cuda:0',requires_grad=True)
            origin = torch.zeros_like(position,requires_grad=True)
            norm = residual_distance_fp32(position,origin)
            need(torch.equal(norm,torch.tensor([5.],device='cuda:0')),
                 'Independent 3-4-5 real norm differs')
            gradient, = torch.autograd.grad(norm.sum(),(position,),create_graph=True)
            need(torch.allclose(gradient,torch.tensor([[.6,.8,0.]],device='cuda:0'),rtol=0,atol=2e-7),
                 'Independent norm gradient differs')
            hessian_row, = torch.autograd.grad(gradient[0,2],(position,))
            need(torch.allclose(hessian_row,torch.tensor([[0.,0.,.2]],device='cuda:0'),rtol=0,atol=2e-7),
                 'Independent transverse norm Hessian differs')
            zero = torch.zeros((1,3),device='cuda:0',requires_grad=True)
            zero_norm = residual_distance_fp32(zero,torch.zeros_like(zero))
            zero_gradient, = torch.autograd.grad(zero_norm.sum(),(zero,))
            need(torch.equal(zero_norm,torch.zeros_like(zero_norm))
                 and torch.equal(zero_gradient,torch.zeros_like(zero_gradient)),
                 'Registered coincident-point zero derivative convention differs')
            pair = residual_pairwise_distance_fp32(position.detach()[None],origin.detach()[None])
            need(pair.shape == (1,1,1) and float(pair[0,0,0]) == 5., 'Actual caller pair wrapper differs')
            rejected = []
            for dtype in (torch.float64,torch.bfloat16,torch.float16):
                try:
                    residual_distance_fp32(torch.ones((1,3),device='cuda:0',dtype=dtype),
                                           torch.zeros((1,3),device='cuda:0',dtype=dtype))
                except ValueError:
                    rejected.append(str(dtype))
                else:
                    raise ValueError('Unsupported geometry dtype admitted')
            with torch.autocast('cuda',dtype=torch.bfloat16):
                try:
                    residual_distance_fp32(position,origin)
                except ValueError:
                    rejected.append('active_cuda_autocast')
                else:
                    raise ValueError('Active AMP geometry admitted')
            need(torch.equal(cpu_rng,torch.get_rng_state())
                 and torch.equal(gpu_rng,torch.cuda.get_rng_state()), 'Tiny controls changed RNG')
            return {'scope':'INLINE_ACTUAL_GEOMETRY_AND_ORIGINAL_PROJECTION_HELPERS_NOT_FULL48',
                'geometry_mode':RESIDUAL_GEOMETRY,'geometry_tile_rows':GEOMETRY_TILE_ROWS,
                'splitter':SPLITTER,'raw_difference_tail_exact_squared_oracle':True,
                'analytic_first_derivatives':True,'all_three_second_cross_blocks':True,
                'independent_second_direction':26.,'norm_3_4_5_and_transverse_Hessian':True,
                'norm_gradient_oracle_absolute_tolerance':2e-7,
                'zero_norm_and_zero_derivative_convention':True,'guard_rejections':rejected,
                'original_projection_controls':projection,'CPU_and_CUDA_RNG_unchanged':True,
                'FP64_arithmetic':False,'nonFP32_guard_inputs_not_arithmetic':True,
                'encoder_forwards':0,'scientific_cases_added':0,'scientific_adoption':False}
    finally:
        torch.set_float32_matmul_precision(previous[0])
        torch.backends.cudnn.allow_tf32 = previous[1]