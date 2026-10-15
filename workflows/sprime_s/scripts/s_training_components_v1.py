"""S-only training components; caller must resolve and bind the frozen recipe."""
from __future__ import annotations
import copy,math
import numpy as np,torch
from torch_geometric.utils import to_dense_batch

TASKS=('element','distance','bond_order')

class ExposureBoundedSampler:
    """Split identical base batches at declared exposure events in every run.

    Iterator prefetch does not change committed state. A split base batch is
    committed to the original sampler only when all of its pieces are consumed.
    """
    def __init__(self,base,events):
        self.base=base;self.index=base.index;self.block_size=base.block_size
        self.events=tuple(sorted(set(int(i) for i in events if 0<int(i)<len(self.index))))
        self.offset=0
    @property
    def epoch(self):return self.base.epoch
    @property
    def samples_consumed(self):return self.base.samples_consumed+self.offset
    def _piece(self,base_batch,offset,consumed):
        remaining=len(base_batch)-offset
        next_event=next((i for i in self.events if i>consumed),len(self.index))
        size=min(remaining,next_event-consumed)
        assert size>0
        return base_batch[offset:offset+size]
    def __iter__(self):
        local_offset=self.offset;consumed=self.samples_consumed
        for original in self.base:
            while local_offset<len(original):
                piece=self._piece(original,local_offset,consumed)
                local_offset+=len(piece);consumed+=len(piece);yield piece
            local_offset=0
    def commit_batch(self,indices):
        result=self.base._next(self.base._cursor);assert result is not None
        original,_=result;expected=self._piece(original,self.offset,self.samples_consumed)
        assert list(indices)==expected,'ACTUAL_CONSUMED_RECORD_ORDER_MISMATCH'
        self.offset+=len(indices)
        if self.offset==len(original):self.base.commit_batch(original);self.offset=0
    def advance_epoch(self):
        assert self.offset==0 and self.samples_consumed==len(self.index)
        self.base.advance_epoch()
    def state_dict(self):
        return {'base':self.base.state_dict(),'split_offset':self.offset,'events':list(self.events),'committed_records':self.samples_consumed}
    def load_state_dict(self,value):
        assert value['events']==list(self.events)
        self.base.load_state_dict(value['base']);offset=value['split_offset']
        assert type(offset) is int and offset>=0
        result=self.base._next(self.base._cursor)
        if result is None:assert offset==0
        else:
            original,_=result;cursor=0;consumed=self.base.samples_consumed
            while cursor<offset:
                piece=self._piece(original,cursor,consumed);cursor+=len(piece);consumed+=len(piece)
            assert cursor==offset and offset<len(original)
        self.offset=offset;assert value['committed_records']==self.samples_consumed

class EpochCoverage:
    def __init__(self,records):self.visited=np.zeros(records,dtype=np.uint8);self.consumed=0;self.molecules=set()
    def add(self,indices,molecules):
        values=np.asarray(indices,dtype=np.int64)
        assert len(np.unique(values))==len(values) and np.all((values>=0)&(values<len(self.visited)))
        assert not np.any(self.visited[values]),'ACTUAL_CONSUMED_RECORD_DUPLICATE'
        self.visited[values]=1;self.consumed+=len(values);self.molecules.update(molecules)
    def finish(self,expected_molecules):
        assert self.consumed==len(self.visited) and np.all(self.visited),'EPOCH_RECORD_COVERAGE_MISMATCH'
        assert len(self.molecules)==expected_molecules,'EPOCH_FOLDED_MOLECULE_COUNT_MISMATCH'
        return {'records':self.consumed,'molecules':len(self.molecules),'duplicates':0,'missing':0}

class SMeter:
    """Actual-label-weighted raw losses and the same unordered distance metrics."""
    def __init__(self,cutoff=2.):
        self.cutoff=float(cutoff);self.raw_sum={k:0. for k in TASKS};self.counts={k:0 for k in TASKS}
        self.element_correct=self.element_count=self.bond_correct=self.bond_count=0
        self.local_squared=self.all_squared=self.noisy_local_squared=self.noisy_all_squared=0.
        self.local_pairs=self.all_pairs=0
    def add_loss(self,loss):
        for key in TASKS:
            count=int(loss.counts.get(key,0));value=float(loss.raw[key].detach().float().cpu())
            assert math.isfinite(value),'NONFINITE_S_LOSS'
            self.raw_sum[key]+=value*count;self.counts[key]+=count
    @torch.no_grad()
    def add_outputs(self,batch,outputs):
        group=batch.sample_type_id.view(-1).long();device=outputs.atom_repr.device
        dense=lambda name:to_dense_batch(getattr(batch,name).to(device),batch.batch.to(device))[0]
        node_mask=outputs.node_mask.squeeze(-1).bool();target_x=dense('target_x')[...,0]
        corrupt=dense('element_corrupt_mask').squeeze(-1).bool()
        mask=node_mask&group.eq(2).view(-1,1)&corrupt&target_x.ge(0)&target_x.lt(outputs.element_logits.shape[-1]-1)
        self.element_count+=int(mask.sum());self.element_correct+=int((outputs.element_logits.argmax(-1)[mask]==target_x[mask]).sum())
        bond=outputs.bond;keep=group.eq(0)[bond.pair_graph_index.long()]
        bond_target=bond.order_target.view(-1)
        keep=keep&torch.isfinite(bond_target)&bond_target.eq(bond_target.float().floor())&bond_target.ge(0)&bond_target.lt(5)
        self.bond_count+=int(keep.sum());self.bond_correct+=int((bond.order.argmax(-1)[keep]==bond_target[keep]).sum())
        target=dense('target_pos');noisy=dense('pos')
        truth=torch.cdist(target.float(),target.float())
        prediction=torch.cdist(outputs.coordinate_pred.float(),outputs.coordinate_pred.float())
        observed=torch.cdist(noisy.float(),noisy.float())
        valid=node_mask&torch.isfinite(target).all(-1)
        pairs=valid[:,:,None]&valid[:,None,:]&group.eq(1).view(-1,1,1)
        pairs=pairs&torch.triu(torch.ones((target.shape[1],target.shape[1]),dtype=torch.bool,device=device),diagonal=1).view(1,target.shape[1],target.shape[1])
        local=pairs&(truth<self.cutoff)
        # Match the audited evaluator: float32 cdist, then float64 subtraction
        # and accumulation (the old evaluator converts each array to NumPy).
        error=prediction.double()-truth.double();noisy_error=observed.double()-truth.double()
        assert torch.isfinite(error[pairs]).all() and torch.isfinite(noisy_error[pairs]).all(),'NONFINITE_S_GEOMETRY_METRIC'
        self.all_squared+=float(error[pairs].square().sum());self.noisy_all_squared+=float(noisy_error[pairs].square().sum());self.all_pairs+=int(pairs.sum())
        self.local_squared+=float(error[local].square().sum());self.noisy_local_squared+=float(noisy_error[local].square().sum());self.local_pairs+=int(local.sum())
    def result(self):
        divide=lambda a,n:a/n if n else None
        rmse=lambda a,n:math.sqrt(a/n) if n else None
        return {'raw_losses':{k:divide(self.raw_sum[k],self.counts[k]) for k in TASKS},'valid_loss_counts':self.counts.copy(),
            'element_accuracy':divide(self.element_correct,self.element_count),'element_labels':self.element_count,
            'bond_order_accuracy':divide(self.bond_correct,self.bond_count),'bond_order_labels':self.bond_count,
            'geometry_local_pair_A_rmse':rmse(self.local_squared,self.local_pairs),'geometry_local_pair_count':self.local_pairs,
            'geometry_all_pair_A_rmse':rmse(self.all_squared,self.all_pairs),'geometry_all_pair_count':self.all_pairs,
            'actual_noisy_local_pair_A_rmse':rmse(self.noisy_local_squared,self.local_pairs),
            'actual_noisy_all_pair_A_rmse':rmse(self.noisy_all_squared,self.all_pairs)}
