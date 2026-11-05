"""Bounded cross-job segments over the unchanged sample-budget implementation."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import fcntl
import os
import resource
import stat
from pathlib import Path

from .v3_sample_budget_events import (PanelEventController, binding, canonical, encoded,
    owned_bytes, physical, read_bound, require, verify_checkpoint_record, write_once)
from .v3_sample_budget_experiment import SampleBudgetExperiment


@contextmanager
def owned_lock(root,name):
    path = physical(root/name)
    descriptor = os.open(path,os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,0o600)
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1,
            'Owned ordinary single-link lock required')
        with os.fdopen(descriptor,'r+b') as stream:
            descriptor = None
            yield stream
    finally:
        if descriptor is not None: os.close(descriptor)


def allocate_launch(root,*,request_ref,lineage,job_root,segment_id,maximum_attempts,maximum_bytes):
    """Register even SDK/model-init failures before either initialization.

    This allocation supplies no trainer/checkpoint authority or success marker.
    It only binds otherwise-unregistered failed output roots to joint capacity.
    """
    import re
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',segment_id or ''),'Explicit launch identity required')
    require(type(maximum_attempts) is int and 1 <= maximum_attempts <= 128
        and type(maximum_bytes) is int and 8 << 20 <= maximum_bytes <= 32 << 20,'Bounded launch ledger required')
    root,job_root = physical(root),physical(job_root)
    require(root != job_root and not root.is_relative_to(job_root) and not job_root.is_relative_to(root),'Disjoint launch ledger/job roots required')
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    require(root.stat().st_uid == os.getuid() and job_root.is_dir(),'Owned initialized job root required')
    policy = {'schema':'model_v3_proxy_launch_policy_v1','request':request_ref,'lineage':lineage,
        'maximum_attempts':maximum_attempts,'maximum_bytes':maximum_bytes}
    with owned_lock(root,'metadata.lock') as descriptor:
        fcntl.flock(descriptor,fcntl.LOCK_EX)
        try:
            folder = physical(root/'launches'); folder.mkdir(exist_ok=True)
            records = list(folder.glob('*.json')); path = folder/(segment_id+'.json')
            require(len(records) < maximum_attempts and not path.exists(),'Immutable global launch attempt cap reached or identity reused')
            require(all(read_bound(binding(p))['job_root'] != str(job_root) for p in records),'Launch job root reused')
            body = {'schema':'model_v3_proxy_launch_allocation_v1','segment_id':segment_id,'job_root':str(job_root),'request':request_ref}
            additional = len(encoded(body))+(0 if (root/'LAUNCH_POLICY.json').exists() else len(encoded(policy)))
            require(owned_bytes(root)+additional <= maximum_bytes,'Launch ledger metadata cap exhausted')
            write_once(root/'LAUNCH_POLICY.json',policy)
            return write_once(path,body)
        finally: fcntl.flock(descriptor,fcntl.LOCK_UN)


class BoundedLineageController(PanelEventController):
    """One canonical, bounded metadata ledger; training/ACK locks are separate."""
    def __init__(self, root, *, contract, max_records, maximum_bytes):
        require(type(maximum_bytes) is int and 8 << 20 <= maximum_bytes <= 32 << 20,
            'Explicit 8 to 32 MiB canonical metadata reserve required')
        if contract.get('trainer_bindings',{}).get('proxy_scope') is not None:
            config = read_bound(contract['model_configuration'])
            require(maximum_bytes == config['proxy_contract']['resources']['ledger_bytes'],
                'Canonical ledger byte allowance cannot drift on resume or ACK')
            require(max_records == contract['plan']['max_total_checkpoints'],'Global checkpoint attempt cap differs')
        self.byte_limit, self._depth, self._metadata_fd = maximum_bytes, 0, None
        self.root = physical(root); self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        require(self.root.stat().st_uid == os.getuid(), 'Owned canonical lineage root required')
        self.maximum = max_records
        with self.transaction():
            if (self.root/'LAUNCH_POLICY.json').exists():
                policy = read_bound(binding(self.root/'LAUNCH_POLICY.json'))
                require(policy['maximum_bytes'] == maximum_bytes and policy['maximum_attempts'] == max_records,
                    'Canonical launch metadata/count allowance differs')
            self._space(0 if (self.root/'EXPERIMENT.json').exists() else
                len(encoded({'schema': 'model_v3_sample_experiment_ledger_v1', 'contract': contract})))
            super().__init__(self.root, contract=contract, max_records=max_records)
            (self.root/'segments').mkdir(exist_ok=True)
            self._space(0)

    @contextmanager
    def transaction(self):
        if self._depth:
            self._depth += 1
            try: yield
            finally: self._depth -= 1
            return
        with self._lock('metadata.lock') as descriptor:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            self._depth = 1
            try: yield
            finally:
                self._depth = 0
                fcntl.flock(descriptor, fcntl.LOCK_UN)

    @contextmanager
    def _lock(self, name):
        with owned_lock(self.root,name) as descriptor: yield descriptor

    @contextmanager
    def training_lease(self):
        with self._lock('training.lock') as descriptor:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try: yield
            finally: fcntl.flock(descriptor, fcntl.LOCK_UN)

    def _space(self, additional):
        require(owned_bytes(self.root)+additional <= self.byte_limit, 'Canonical lineage metadata cap exhausted')

    def register_segment(self, *, segment_id, experiment_root, request_ref, parent):
        import re
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', segment_id or ''), 'Explicit segment id required')
        root = physical(experiment_root)
        require(not root.is_relative_to(self.root) and not self.root.is_relative_to(root), 'Disjoint ledger/segment roots required')
        body = {'schema': 'model_v3_proxy_segment_registration_v1', 'segment_id': segment_id,
            'experiment_root': str(root), 'request': request_ref, 'parent_checkpoint': parent,
            'contract_sha256': canonical(self.contract)}
        with self.transaction():
            path = self.root/'segments'/(segment_id+'.json')
            records = list((self.root/'segments').glob('*.json'))
            require(not path.exists() and len(records) < self.maximum, 'Segment id reused or total attempt cap reached')
            require(all(read_bound(binding(p))['experiment_root'] != str(root) for p in records), 'Fresh job output root required')
            if (self.root/'LAUNCH_POLICY.json').exists():
                launch = read_bound(binding(self.root/'launches'/(segment_id+'.json')))
                require(launch['job_root'] == str(root.parent) and launch['request'] == request_ref,
                    'Segment must match its immutable pre-SDK allocation')
            self._space(len(encoded(body)))
            return write_once(path, body)

    def registered_segments(self):
        with self.transaction():
            paths = list((self.root/'segments').glob('*.json'))
            require(len(paths) <= self.maximum, 'Global segment attempt cap exceeded')
            records = [read_bound(binding(path)) for path in paths]
            require(all(r['schema'] == 'model_v3_proxy_segment_registration_v1'
                and r['contract_sha256'] == canonical(self.contract) for r in records), 'Foreign segment contract')
            return records

    def launch_roots(self):
        with self.transaction():
            if not (self.root/'LAUNCH_POLICY.json').exists(): return []
            policy = read_bound(binding(self.root/'LAUNCH_POLICY.json'))
            paths = list((self.root/'launches').glob('*.json'))
            require(len(paths) <= self.maximum and policy['maximum_attempts'] == self.maximum,'Global launch count drift')
            rows = [read_bound(binding(path)) for path in paths]
            require(all(row['schema'] == 'model_v3_proxy_launch_allocation_v1'
                and row['request'] == policy['request'] for row in rows),'Foreign launch allocation')
            return [physical(row['job_root']) for row in rows]

    def publish(self, completion_ref):
        with self.transaction():
            _, state = verify_checkpoint_record(completion_ref)
            body = {'schema': 'model_v3_checkpoint_panel_event_v1', 'body': state['event'], 'checkpoint_completion': completion_ref}
            target = self.root/'events'/(state['event']['event_id']+'.json')
            self._space(0 if target.exists() else len(encoded(body)))
            result = super().publish(completion_ref); self._space(0); return result

    def events(self):
        with self.transaction(): return super().events()

    def acknowledgements(self):
        with self.transaction(): return super().acknowledgements()

    def pending(self):
        with self.transaction(): return super().pending()

    def acknowledge(self, event_ref, result_ref, evidence_ref):
        with self.transaction():
            body = read_bound(event_ref)['body']
            receipt = {'schema': 'model_v3_sample_panel_ack_v1', 'event_id': body['event_id'],
                'event': event_ref, 'result': result_ref, 'evidence': evidence_ref}
            self._space(0 if body['event_id'] in self.acknowledgements() else 2*len(encoded(receipt)))
            result = super().acknowledge(event_ref, result_ref, evidence_ref); self._space(0); return result

    def curve(self):
        with self.transaction(): return super().curve()


class ProxySegmentExperiment(SampleBudgetExperiment):
    """Fresh job-owned checkpoint forest plus a canonical cross-job outbox/ACK."""
    def __init__(self, *args, lineage_root, ledger_bytes, controller_factory=BoundedLineageController, **kwargs):
        super().__init__(*args, **kwargs)
        # Preserve the small local constructor receipt. All active events and
        # ACKs use the canonical ledger, never a copied/rollbackable snapshot.
        self.controller = controller_factory(lineage_root, contract=self.contract,
            max_records=self.plan.max_total_checkpoints, maximum_bytes=ledger_bytes)

    def _all_checkpoint_directories(self):
        result = []
        for record in self.controller.registered_segments():
            root = physical(record['experiment_root'])/'segments'/record['segment_id']
            if root.exists():
                require(root.is_dir() and not root.is_symlink(), 'Unsafe registered segment directory')
                result.extend(root.glob('checkpoint_*'))
        require(len(result) == len(set(result)), 'Duplicate registered checkpoint path')
        return result

    def resume_from(self, completion_ref):
        record, state = verify_checkpoint_record(completion_ref)
        require(state['contract'] == self.contract, 'Resume source/config/budget/trainer contract differs; no implicit fork')
        directory = physical(completion_ref['path']).parent
        registered = self.controller.registered_segments()
        require(any(directory.is_relative_to(physical(row['experiment_root'])/'segments'/row['segment_id'])
            for row in registered), 'Resume checkpoint is not in this canonical lineage')
        # Authenticate all metadata before the original strict loader mutates
        # model/optimizer/RNG/provider state. No old directory is written.
        self.trainer.load(directory/'trainer', output_root=directory)
        require((self.trainer.clock.samples_consumed, self.trainer.clock.optimizer_updates, self.trainer.log_cursor)
            == (state['samples_consumed'], state['optimizer_updates'], state['log_cursor']), 'Restored committed cursors differ')
        self.points = deepcopy(state['points'])
        self.completed = [*state['previous_checkpoints'], completion_ref]
        self.last_checkpoint = completion_ref
        if not state['pending_log']: self.controller.publish(completion_ref)
        return record

    def lineage_output_roots(self):
        roots = {physical(row['experiment_root']).parent for row in self.controller.registered_segments()}
        roots.update(self.controller.launch_roots())
        roots.add(self.root.parent)
        roots.add(self.controller.root)
        ordered = sorted(roots, key=lambda p: len(p.parts))
        require(all(not b.is_relative_to(a) for i,a in enumerate(ordered) for b in ordered[i+1:]),
            'Canonical ledger and complete job roots must be disjoint; no nested accounting')
        return ordered

    def _checkpoint(self, reason):
        # The unchanged save implementation further reduces this kernel cap
        # to its local segment allowance. A crash/partial consumes this same
        # immutable lineage capacity and remains visible on resume.
        if self.last_checkpoint is not None:
            _,state = verify_checkpoint_record(self.last_checkpoint)
            if (state['samples_consumed'],state['optimizer_updates'],state['log_cursor'],state['pending_log']) == (
                self.trainer.clock.samples_consumed,self.trainer.clock.optimizer_updates,self.trainer.log_cursor,self.trainer.pending_log is not None):
                if not state['pending_log']: self.controller.publish(self.last_checkpoint)
                return self.last_checkpoint
        def save():
            if not hasattr(self, 'joint_remaining_bytes'):
                return super(ProxySegmentExperiment,self)._checkpoint(reason)
            remaining = self.joint_remaining_bytes()
            if hasattr(self,'durable_storage'):
                remaining = min(remaining,self.durable_storage.limits['checkpoint_bytes'])
            require(remaining > 0, 'No joint lineage storage reserve for checkpoint')
            old = resource.getrlimit(resource.RLIMIT_FSIZE)
            limit = remaining if old[0] == resource.RLIM_INFINITY else min(old[0],remaining)
            try:
                resource.setrlimit(resource.RLIMIT_FSIZE,(limit,old[1]))
                return super(ProxySegmentExperiment,self)._checkpoint(reason)
            finally:
                resource.setrlimit(resource.RLIMIT_FSIZE,old)
        if hasattr(self,'durable_storage'): return self.durable_storage.checkpoint(self,reason,save)
        return save()

    def run_segment(self, *, segment_id, until_samples, request_ref, parent=None, preflight):
        require(callable(preflight), 'Whole-job cooperative guard required, including engineering runs')
        with self.controller.training_lease():
            if parent is not None: self.resume_from(parent)
            self.controller.register_segment(segment_id=segment_id, experiment_root=self.root,
                request_ref=request_ref, parent=parent)
            return super().run(segment_id=segment_id, until_samples=until_samples, preflight=preflight)
