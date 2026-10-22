"""Current metrics plus label-weighted raw monitoring; no old convergence rule."""
import math
from phychem_mfm.phase1.denoising_metrics import DenoisingMetrics

TASKS=('element','denoise_eps_mse','bond_order','distance')


class SMeter:
    def __init__(self,cutoff=2.):
        self.metrics=DenoisingMetrics(cutoff=cutoff,sigma=.10)
        self.raw_sum={k:0. for k in TASKS}
        self.counts={k:0 for k in TASKS}

    def add_loss(self,loss):
        for key in TASKS:
            count=int(loss.counts.get(key,0))
            if not count: continue
            value=float(loss.raw[key].detach().float())
            if not math.isfinite(value): raise FloatingPointError('GUIDE_STOP_NONFINITE_S_LOSS')
            self.raw_sum[key]+=value*count; self.counts[key]+=count

    def add_outputs(self,batch,outputs):
        self.metrics.add(outputs,batch)

    def result(self):
        result=self.metrics.result()
        result['raw_losses']={k:self.raw_sum[k]/n if n else None for k,n in self.counts.items()}
        result['valid_loss_counts']=self.counts.copy()
        return result
