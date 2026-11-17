"""GPU log buffering and optimizer selection for the opt-in short-study path."""
import torch


def make_optimizer(parameters, configuration):
    options = configuration.get('step_overhead', {})
    keywords = dict(lr=configuration['lr'], betas=tuple(configuration['betas']),
                    weight_decay=configuration['weight_decay'])
    if not options.get('fused_optimizer', False):
        return torch.optim.AdamW(parameters, **keywords)
    parameters = list(parameters)
    try:
        optimizer = torch.optim.AdamW(parameters, fused=True, **keywords)
        optimizer.perf_sync_backend = 'fused'
        return optimizer
    except (TypeError, RuntimeError, NotImplementedError):
        optimizer = torch.optim.AdamW(parameters, foreach=True, **keywords)
        optimizer.perf_sync_backend = 'foreach'
        return optimizer


class StepBuffer:
    """One CPU transfer per drain; FP64 sums preserve Python float accumulation."""
    def __init__(self, *, device='cuda'):
        self.rows = []
        self.values = []
        self.family = {}
        self.clipped = torch.zeros((), dtype=torch.int64, device=device)
        self.finite = torch.ones((), dtype=torch.bool, device=device)

    def seed_family(self, window):
        self.family = {name: (self.clipped.new_tensor(value, dtype=torch.float64), count)
                       for name, (value, count) in window.items()}

    def add(self, row, total, norm, clip, family, checks):
        self.rows.append(row)
        self.values.append(torch.stack((total.detach().double(), norm.detach().double())))
        self.clipped.add_(norm.detach().double() > clip)
        self.finite.logical_and_(torch.isfinite(norm) & torch.isfinite(total))
        for check in checks:
            self.finite.logical_and_(check.detach())
        for name, value in family.items():
            previous, count = self.family.get(name, (value.new_zeros((), dtype=torch.float64), 0))
            self.family[name] = (previous + value.detach().double(), count + 1)

    def drain(self):
        if not self.rows:
            return [], {}, 0
        fields = list(self.family)
        packed = torch.cat((torch.stack(self.values).flatten(),
            torch.stack([self.family[name][0] for name in fields]) if fields else self.values[0].new_empty(0),
            self.clipped.double().view(1), self.finite.double().view(1))).cpu().tolist()
        if not packed[-1]:
            raise RuntimeError('Nonfinite gradient, loss, or internal activation in buffered step window')
        rows = [dict(row, total=packed[2*i], preclip_norm=packed[2*i+1])
                for i, row in enumerate(self.rows)]
        start = 2*len(rows)
        family = {name: (packed[start+i], self.family[name][1]) for i, name in enumerate(fields)}
        clipped = int(packed[-2])
        self.rows.clear()
        self.values.clear()
        self.clipped.zero_()
        self.finite.fill_(True)
        return rows, family, clipped
