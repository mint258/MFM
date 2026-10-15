"""Preserve parent RNG when replacing a loader during checkpoint continuation."""
from s_loader_recovery_v1 import RecoveringLoaderIterator as _Iterator,LoaderRetryExhausted

class RecoveringLoaderIterator(_Iterator):
    def __init__(self,factory,sampler,close_iterator,torch,*,preserve_initial_rng=False,**kwargs):
        rng=torch.get_rng_state().clone() if preserve_initial_rng else None
        try:
            super().__init__(factory,sampler,close_iterator,torch,**kwargs)
        finally:
            if rng is not None:torch.set_rng_state(rng)
