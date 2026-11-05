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

def retained_geometry_and_projection_controls():
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

def ffn_controls():
    """One small actual DenseFFN; exact real-function derivative control, zero encoders."""
    import torch
    from phychem_mfm.model.attention import DenseFFN
    from phychem_mfm.model.v3_ffn_projection import BLOCKED_FFN
    cpu_rng, gpu_rng = torch.get_rng_state().clone(), torch.cuda.get_rng_state().clone()
    previous = (torch.get_float32_matmul_precision(), torch.backends.cudnn.allow_tf32)
    try:
        torch.set_float32_matmul_precision('highest')
        torch.backends.cudnn.allow_tf32 = False
        with torch.random.fork_rng(devices=[0]):
            torch.random.default_generator.manual_seed(1742)
            module = DenseFFN(512, 2, ffn_projection_mode=BLOCKED_FFN).to('cuda:0')
        identities = {name:id(value) for name,value in module.named_parameters()}
        with torch.autocast('cuda', enabled=False), torch.enable_grad():
            with torch.no_grad():
                for parameter in module.parameters(): parameter.zero_()
                module.net[0].weight[0,0],module.net[0].weight[0,64] = .5,.25
                module.net[3].weight[0,0],module.net[3].weight[1,0] = .75,-.5
                module.net[3].bias[0],module.net[3].bias[1] = .5,-.25
            x=torch.zeros((1,512),device='cuda:0')
            x[0,0],x[0,64]=1.,-2.;x.requires_grad_()
            values=(x,module.net[0].weight,module.net[0].bias,module.net[3].weight,module.net[3].bias)
            directions=[torch.zeros_like(v) for v in values]
            directions[0][0,0],directions[0][0,64]=.125,-.25
            directions[1][0,0],directions[1][0,64]=-.125,.0625
            directions[2][0]=.5
            directions[3][0,0],directions[3][1,0]=.125,.25
            directions[4][0],directions[4][1]=-.125,.25
            output=module(x)
            need(torch.equal(output[:,:2],torch.tensor([[.5,-.25]],device='cuda:0'))
                 and torch.count_nonzero(output[:,2:])==0,'Independent full FFN dyadic forward differs')
            first=torch.autograd.grad(.5*output.square().sum(),values,create_graph=True)
            expected=[torch.zeros_like(v) for v in values]
            expected[0][0,0],expected[0][0,64]=.125,.0625
            expected[1][0,0],expected[1][0,64]=.25,-.5
            expected[2][0]=.25
            expected[4][0],expected[4][1]=.5,-.25
            need(all(torch.equal(a,b) for a,b in zip(first,expected)),
                 'Independent input/W1/b1/W2/b2 FFN first derivatives differ')
            directional=sum((g*d).sum() for g,d in zip(first,directions))
            need(float(directional)==-.0625,'Independent FFN first direction differs')
            second=torch.autograd.grad(directional,values)
            expected=[torch.zeros_like(v) for v in values]
            expected[0][0,0],expected[0][0,64]=-.029296875,.0166015625
            expected[1][0,0],expected[1][0,64]=.03515625,-.0703125
            expected[2][0]=.00390625
            expected[3][0,0],expected[3][1,0]=.0625,-.03125
            expected[4][0],expected[4][1]=-.03125,.1875
            need(all(torch.equal(a,b) and a.abs().sum()>0 for a,b in zip(second,expected))
                 and float(sum((g*d).sum() for g,d in zip(second,directions)))==.0361328125,
                 'Independent complete FFN mixed Hessian/direction37/1024 differs')
            need(all(t.dtype==torch.float32 for t in (*first,*second,output)),
                 'Actual FFN derivative ports must remain FP32')
            rejected=[]
            for dtype in (torch.float64,torch.bfloat16,torch.float16):
                try: module(torch.ones((1,512),device='cuda:0',dtype=dtype))
                except ValueError: rejected.append(str(dtype))
                else: raise ValueError('FFN admitted a non-FP32 tensor')
            with torch.autocast('cuda',dtype=torch.bfloat16):
                try: module(torch.ones((1,512),device='cuda:0'))
                except ValueError: rejected.append('active_cuda_autocast')
                else: raise ValueError('FFN admitted active CUDA AMP')
            need(identities=={name:id(value) for name,value in module.named_parameters()},
                 'Tiny actual FFN replaced original Parameter objects')
            need(torch.equal(cpu_rng,torch.get_rng_state()) and torch.equal(gpu_rng,torch.cuda.get_rng_state()),
                 'Tiny FFN controls changed CPU/CUDA RNG')
            return {'scope':'INLINE_TINY_ACTUAL_DENSE_FFN_ALL_FP32_NOT_FULL48',
                'mode':BLOCKED_FFN,'actual_affine_dimensions':[[512,1024],[1024,512]],
                'independent_five_first_derivative_blocks':True,
                'independent_five_mixed_Hessian_blocks':True,'second_direction':.0361328125,
                'analytic_basis':'SiLU(0)=0; SiLU prime and double-prime at0 both1/2; real affine chain',
                'parameter_object_identity':True,'all_actual_floating_derivative_ports_FP32':True,
                'guard_rejections':rejected,'CPU_and_CUDA_RNG_unchanged':True,
                'encoder_forwards':0,'scientific_cases_added':0,'FP64_arithmetic':False,
                'nonFP32_guard_tensors_are_not_arithmetic':True,'scientific_adoption':False}
    finally:
        torch.set_float32_matmul_precision(previous[0])
        torch.backends.cudnn.allow_tf32=previous[1]


def residual_controls():
    """Actual three-input primitive; independent nonlinear derivatives, zero encoders."""
    import torch
    from phychem_mfm.model.v3_residual_accumulation import two_sum_three_term_fp32, TWO_SUM_RESIDUAL
    cpu_rng, gpu_rng = torch.get_rng_state().clone(), torch.cuda.get_rng_state().clone()
    previous = (torch.get_float32_matmul_precision(), torch.backends.cudnn.allow_tf32)
    try:
        torch.set_float32_matmul_precision('highest')
        torch.backends.cudnn.allow_tf32 = False
        with torch.autocast('cuda', enabled=False), torch.enable_grad():
            actual = two_sum_three_term_fp32(*(torch.tensor([v],device='cuda:0')
                for v in (2.**24,1.,-(2.**24))))
            need(float(actual) == 1., 'Independent real three-term cancellation oracle differs')
            x = torch.tensor([.5],device='cuda:0',requires_grad=True)
            a = x.square(); u = x+a; b = u.square()
            y = two_sum_three_term_fp32(x,a,b)
            first, = torch.autograd.grad(y.sum(),(x,),create_graph=True)
            second, = torch.autograd.grad(first.sum(),(x,))
            need(float(y) == 21/16 and float(first) == 5. and float(second) == 13.,
                 'Independent nonlinear x squared/u squared value/first/second oracle differs')
            terms = [torch.tensor([[v,-v]],device='cuda:0',requires_grad=True) for v in (1.,2.,3.)]
            output = two_sum_three_term_fp32(*terms)
            gradients = torch.autograd.grad(.5*output.square().sum(),terms,create_graph=True)
            directions = [torch.tensor([[v,-v]],device='cuda:0') for v in (.25,-.5,1.)]
            mixed = torch.autograd.grad(sum((g*d).sum() for g,d in zip(gradients,directions)),terms)
            need(all(torch.equal(g,torch.tensor([[6.,-6.]],device='cuda:0')) for g in gradients)
                 and all(torch.equal(g,torch.tensor([[.75,-.75]],device='cuda:0')) for g in mixed)
                 and float(sum((g*d).sum() for g,d in zip(mixed,directions))) == 1.125,
                 'Independent three-input mixed Hessian/VJP connectivity differs')
            need(all(value.dtype == torch.float32 for value in
                     (actual,y,first,second,output,*gradients,*mixed)),
                 'Actual residual derivative ports must remain FP32')
            rejected = []
            for dtype in (torch.float64,torch.bfloat16,torch.float16):
                try:
                    two_sum_three_term_fp32(torch.ones(2,device='cuda:0',dtype=dtype),
                        torch.ones(2,device='cuda:0'),torch.ones(2,device='cuda:0'))
                except ValueError: rejected.append(str(dtype))
                else: raise ValueError('Residual admitted non-FP32 operands')
            with torch.autocast('cuda',dtype=torch.bfloat16):
                try: two_sum_three_term_fp32(*(torch.ones(2,device='cuda:0') for _ in range(3)))
                except ValueError: rejected.append('active_cuda_autocast')
                else: raise ValueError('Residual admitted active AMP')
            maximum = torch.finfo(torch.float32).max
            try:
                two_sum_three_term_fp32(*(torch.tensor([v],device='cuda:0')
                    for v in (maximum,maximum,-maximum)))
            except ValueError: rejected.append('finite_inputs_intermediate_overflow')
            else: raise ValueError('Residual silently repaired an unsupported intermediate overflow')
            need(torch.equal(cpu_rng,torch.get_rng_state()) and torch.equal(gpu_rng,torch.cuda.get_rng_state()),
                 'Tiny residual controls changed CPU/CUDA RNG')
            return {'scope':'INLINE_ACTUAL_RESIDUAL_PRIMITIVE_NOT_FULL48',
                'mode':TWO_SUM_RESIDUAL, 'independent_cancellation':True,
                'nonlinear_value':21/16, 'nonlinear_first':5., 'nonlinear_second':13.,
                'complete_three_input_mixed_Hessian':True, 'mixed_second_direction':1.125,
                'all_actual_floating_derivative_ports_FP32':True, 'guard_rejections':rejected,
                'CPU_and_CUDA_RNG_unchanged':True, 'encoder_forwards':0, 'scientific_cases_added':0,
                'FP64_arithmetic':False, 'nonFP32_guard_inputs_not_arithmetic':True,
                'no_correct_rounding_or_monotonic_improvement_claim':True, 'scientific_adoption':False}
    finally:
        torch.set_float32_matmul_precision(previous[0])
        torch.backends.cudnn.allow_tf32 = previous[1]

def run():
    return {'scope':'INLINE_TINY_CONTROLS_SEPARATE_FROM192_ENCODER_FORWARDS',
            'retained_geometry_and_projection':retained_geometry_and_projection_controls(),
            'retained_actual_FFN':ffn_controls(), 'new_actual_residual':residual_controls(),
            'encoder_forwards':0,'scientific_adoption':False}
