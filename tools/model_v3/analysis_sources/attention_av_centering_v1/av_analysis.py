"""Local fixed-operand tests; no replacement model forward or acceptance claim."""
import math
import torch
from av_capture import require, header, restore_operand

def summary(value, mask):
    selected = value[mask]
    require(selected.numel() > 0 and bool(selected.isfinite().all()), 'Finite populated statistics required')
    flat = int(value.abs().masked_fill(~mask,-1).reshape(-1).argmax())
    index = []
    for size in reversed(value.shape):
        index.append(flat % size); flat //= size
    return {'components': selected.numel(), 'maxabs': float(selected.abs().max()),
            'rms': float(selected.square().mean().sqrt()), 'signed_mean': float(selected.mean()),
            'components_gt_1e_5': int((selected.abs() > 1e-5).sum()), 'argmax': list(reversed(index))}

def analyze(frame):
    meta, values = frame['meta'], frame['values']
    p = restore_operand(values['p'],meta['headers']['p'])
    v = restore_operand(values['v'],meta['headers']['v'])
    logits = restore_operand(values['logits'],meta['headers']['logits'])
    before = {'p':header(p),'v':header(v),'logits':header(logits)}
    flags = {'autocast':torch.is_autocast_enabled('cuda'),
        'tf32':torch.backends.cuda.matmul.allow_tf32,
        'matmul_precision':torch.get_float32_matmul_precision(),
        'deterministic':torch.are_deterministic_algorithms_enabled()}
    require(not flags['autocast'] and not flags['tf32'] and flags['matmul_precision'] == 'highest',
            'Original FP32 arithmetic flags required')
    require(flags == meta['arithmetic_flags'] and flags['deterministic'] is False,
            'Actual capture/replay flags differ from original policy')
    replay = torch.matmul(p,v)  # Exactly one unchanged actual-operand AV replay.
    original = values['output'].to(device=v.device)
    replay_equal = torch.equal(replay.view(torch.int32), original.view(torch.int32))
    require(replay_equal and list(replay.shape) == meta['headers']['output']['shape'], 'OP_REPLAY_MISMATCH')
    mask = frame['mask'].to(device=v.device)
    require(bool(mask.any(-1).all()), 'Unsupported all-masked graph')
    anchor = mask.to(torch.int64).argmax(-1)  # First valid native key; never result-dependent.
    b,h,_,d = v.shape
    indices = anchor[:,None,None,None].expand(b,h,1,d)
    v0 = torch.gather(v,2,indices)
    centered_v = v-v0
    c32 = v0+torch.matmul(p,centered_v)  # Exactly one FP32 centered control.
    pd, vd, v0d, ld = p.double(), v.double(), v0.double(), logits.double()
    rraw = torch.matmul(pd,vd)
    pnorm = torch.softmax(ld,dim=-1)
    rnorm = torch.matmul(pnorm,vd)
    cexact = v0d+torch.matmul(pd,vd-v0d)  # Independent expression, not defined from predicted effect.
    row_sum = pd.sum(-1,keepdim=True)
    predicted = (1-row_sum)*v0d
    closure = (cexact-rraw)-predicted
    scale = max(1.,float(rraw.abs().max()),float(cexact.abs().max()),
                float((pd.abs().sum(-1,keepdim=True)*vd.abs().amax(-2,keepdim=True)).abs().max()))
    closure_bound = 128*torch.finfo(torch.float64).eps*scale
    require(float(closure.abs().max()) <= closure_bound, 'Independent FP64 centering identity failed')
    valid = mask[:,None,:,None].expand_as(rraw)
    errors = {'original_minus_Rraw':original.double()-rraw, 'C32_minus_Rraw':c32.double()-rraw,
        'original_minus_Rnorm':original.double()-rnorm, 'C32_minus_Rnorm':c32.double()-rnorm,
        'original_minus_C32':original.double()-c32.double(), 'Cexact_minus_Rraw':cexact-rraw,
        'predicted_Cexact_minus_Rraw':predicted.expand_as(rraw), 'identity_closure':closure,
        'C32_minus_Cexact':c32.double()-cexact}
    metrics = {name:summary(value,valid) for name,value in errors.items()}
    primary_index = metrics['original_minus_Rnorm']['argmax']
    component = tuple(primary_index)
    same = {name:float(value[component]) for name,value in errors.items()}
    same.update(original=float(original[component]), C32=float(c32[component]),
                Rraw=float(rraw[component]),Rnorm=float(rnorm[component]))
    same['actual_p_row_sum_minus_one'] = float(row_sum[component[0],component[1],component[2],0]-1)
    same['actual_anchor_V_component'] = float(v0d[component[0],component[1],0,component[3]])
    valid_rows = mask[:,None,:].expand_as(row_sum.squeeze(-1))
    subtraction = centered_v.double()-(vd-v0d)
    result = {'layer':meta['layer'], 'class':meta['class'], 'capture':meta, 'flags':flags,
        'original_AV_replay_bitwise_equal':True,
        'restored_layout_semantics':'same dtype/shape/stride/storage_offset/device/value; relocated allocation, not original pointer',
        'anchor_policy':'first valid key by original native mask; all heads; all values including padding are centered',
        'anchor_indices':anchor.cpu().tolist(),
        'FP32_centered_controls':1,'FP32_original_AV_replays':1,
        'FP64_Rraw_calls':1,'FP64_Rnorm_calls':1,'FP64_Cexact_calls':1,
        'Rraw_definition':'stored p32 promoted to FP64 @ stored V32 promoted to FP64',
        'Rnorm_definition':'FP64 softmax of actual stored masked logits32 @ stored V32 promoted to FP64',
        'identity':{'maxabs':float(closure.abs().max()),'floating_audit_bound':closure_bound,
                    'bound_is_not_original_physics_tolerance':True,'independently_evaluated':True},
        'metrics':metrics,'same_component':{'population':'original_minus_Rnorm absolute argmax over all valid queries/head/components',
            'index':primary_index,'signed_values':same},
        'row_sum_residual_maxabs_valid_queries':float((row_sum.squeeze(-1)-1)[valid_rows].abs().max()),
        'row_sum_residual_maxabs_all_queries':float((row_sum-1).abs().max()),
        'normalized64_row_sum_residual_maxabs':float((pnorm.sum(-1)-1).abs().max()),
        'centering_subtraction_error_maxabs':float(subtraction.abs().max()),
        'all_query_rows':int(p.shape[0]*p.shape[1]*p.shape[2]),
        'valid_query_rows':int(mask.sum())*p.shape[1],
        'padded_query_rows':int((~mask).sum())*p.shape[1],
        'effective_dropout_disabled':True,'all_masked_valid_queries':0,
        'NativeRuntimeDense_or_bf16_or_training_dropout_covered':False,
        'production_centered_forward_executed':False,'physics_acceptance':False}
    require({'p':header(p),'v':header(v),'logits':header(logits)} == before, 'Fixed operands mutated')
    return result

def tiny_controls():
    """Real CUDA coupled-class capture + replay + identity; separate from full48."""
    from phychem_mfm.model.attention import DenseGeoSelfAttention
    from phychem_mfm.model.v3_architecture import SharedPairAttention
    from av_capture import AVCapture
    records = []
    data = torch.arange(24,dtype=torch.float32,device='cuda:0').reshape(2,3,4)/17
    pos = torch.tensor([[[0.,0.,0.],[1.,.2,.3],[0.,0.,0.]],
                        [[.1,.2,.3],[.4,.8,1.],[.9,.3,.7]]],device='cuda:0')
    mask = torch.tensor([[True,True,False],[True,True,True]],device='cuda:0')
    for kind in ('DenseGeoSelfAttention','SharedPairAttention'):
        with torch.random.fork_rng(devices=[]):
            torch.random.default_generator.manual_seed(64123)
            base = DenseGeoSelfAttention(4,1,dropout=0.)
            model = base if kind == 'DenseGeoSelfAttention' else SharedPairAttention(base,4)
        model.eval().to('cuda:0')
        recorder = AVCapture([model])
        try:
            with recorder.scope():
                if kind == 'DenseGeoSelfAttention':
                    model(data,pos,mask)
                else:
                    pair = torch.arange(72,dtype=torch.float32,device='cuda:0').reshape(2,3,3,4)/31
                    model(data,pair,torch.cdist(pos,pos),mask)
            row = analyze(recorder.take_cpu()[0])
            records.append({'class':kind,'original_AV_replay_bitwise_equal':row['original_AV_replay_bitwise_equal'],
                'identity':row['identity'],'FP32_centered_controls':row['FP32_centered_controls']})
        finally:
            recorder.close()
    negative = {}
    # The real finite -1e9 implementation returns a uniform row for an empty
    # graph. Observe and refuse it; do not introduce a different safe softmax.
    bad_mask = mask.clone(); bad_mask[0].zero_()
    recorder = AVCapture([model])
    try:
        with recorder.scope():
            model(data,pair,torch.cdist(pos,pos),bad_mask)
        try:
            recorder.take_cpu()
        except ValueError as error:
            require(str(error) == 'UNSUPPORTED_ALL_MASKED_OR_EMPTY_GRAPH', 'Unexpected negative-control error')
            negative['all_masked_graph_refused_after_original_return'] = True
        else:
            raise ValueError('All-masked negative control was admitted')
    finally:
        recorder.close()
    model.attn_drop = torch.nn.Dropout(.25).train()
    recorder = AVCapture([model])
    try:
        try:
            with recorder.scope():
                model(data,pair,torch.cdist(pos,pos),mask)
        except ValueError as error:
            require(str(error) == 'Effective attention dropout must be disabled', 'Unexpected dropout-control error')
            negative['effective_dropout_refused_before_original_attention'] = True
        else:
            raise ValueError('Effective-dropout negative control was admitted')
    finally:
        recorder.close()
    return {'scope':'INLINE_TINY_REAL_CUDA_CAPTURE_REPLAY_IDENTITY_NOT_SCIENTIFIC_CASES',
        'tiny_attention_forward_returns':3,'tiny_supported_attention_forward_returns':2,
        'tiny_all_masked_negative_forward_returns':1,'tiny_dropout_refused_before_forward':1,
        'tiny_original_AV_replays':2,'tiny_centered_controls':2,
        'tiny_FP64_Rraw_calls':2,'tiny_FP64_Rnorm_calls':2,'tiny_FP64_Cexact_calls':2,
        'records':records,'negative_controls':negative,'scientific_seed_or_model_changed':False}
