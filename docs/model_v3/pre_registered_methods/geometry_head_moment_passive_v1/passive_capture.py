"""Reference-only hooks; no model/local-op replay, policy setter or FP64 arithmetic."""
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import numpy as np
import torch
from torch_geometric.utils import to_dense_batch
from head_ports import HeadPorts

TRACE_CAP = 512 << 20
ROLE_CAP = 4 << 20
STAGES = ('embedding',) + tuple('layer%d' % i for i in range(6)) + ('out_norm', 'packed_H0')

def need(ok, message):
    if not ok:
        raise ValueError(message)

def rawref(path):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink(), 'Ordinary trace/control file required')
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

def array_header(value):
    value = np.ascontiguousarray(value)
    return dict(dtype=value.dtype.str, shape=list(value.shape), nbytes=value.nbytes,
                sha256=hashlib.sha256(value.tobytes()).hexdigest())

class TraceBudget:
    """One finite writer; the unchanged outer supervisor still owns whole/private2GiB."""
    def __init__(self, root):
        self.root, self.bytes, self.files, self.numeric_bytes = Path(root), 0, 0, 0
        self.paths = set()
    def write(self, path, raw):
        path = Path(path)
        need(path.parent.resolve().is_relative_to(self.root.resolve()) and not path.exists(),
             'Fresh output under the new trace root required')
        need(self.bytes + len(raw) <= TRACE_CAP, 'Passive trace exceeds512MiB; retain partial and HOLD')
        with path.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        fd = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
        self.bytes += len(raw); self.files += 1; self.paths.add(path.absolute())
        return rawref(path)
    def adopt(self, path):
        path = Path(path).absolute()
        if path in self.paths: return
        need(path.parent.resolve().is_relative_to(self.root.resolve()) and path.is_file() and not path.is_symlink(),
             'Only ordinary files generated in this trace root can be accounted')
        size = path.stat().st_size
        need(self.bytes + size <= TRACE_CAP, 'Trace plus original terminal/control outputs exceeds512MiB')
        self.bytes += size; self.files += 1; self.paths.add(path)
    def reserve_case(self):
        # Four role archives, original bounded terminal, case JSON, and final metadata/receipts.
        need(self.bytes + 4*ROLE_CAP + (512<<10) + (2<<20) + (8<<20) <= TRACE_CAP,
             'Insufficient finite trace space for one complete case and finalization')
    def json(self, path, value):
        raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
        need(len(raw) <= 2 << 20, 'One trace metadata file exceeds2MiB')
        return self.write(path, raw)
    def arrays(self, path, arrays):
        need(all(type(key) is str and value.dtype in (np.dtype('float32'), np.dtype('int64'), np.dtype('bool'))
                 and not value.dtype.hasobject for key, value in arrays.items()), 'Typed finite F32/integer/bool payload only')
        need(all(np.isfinite(v).all() for v in arrays.values() if v.dtype == np.float32), 'Nonfinite trace')
        amount = sum(value.nbytes for value in arrays.values())
        need(amount + 65536 <= ROLE_CAP and self.bytes + amount + 65536 <= TRACE_CAP,
             'Role/global trace bound would be exceeded')
        stream = io.BytesIO()
        np.savez(stream, **arrays)  # No pickle; bounded, uncompressed small role archive.
        raw = stream.getvalue()
        need(len(raw) <= ROLE_CAP, 'Role archive exceeds4MiB')
        leaf = self.write(path, raw); self.numeric_bytes += amount
        return dict(file=leaf, arrays={k: array_header(v) for k, v in arrays.items()}, numeric_bytes=amount,
                    contains_parameter_weights=any('__parameter__' in key for key in arrays),
                    parameter_scope=('seeded synthetic two-charges-MLP subset only' if any('__parameter__' in key for key in arrays) else 'no parameter arrays'),
                    serialization='numpy.savez uncompressed; allow_pickle=False on future reads')

def numpy_copy(value):
    return value.detach().cpu().contiguous().numpy().copy()

def state_sha(model, local, reference):
    # Reuse the old typed full-state audit, not any local replay/reference path.
    with torch.no_grad():
        return local.state_digest(model, reference)

class RoleCapture:
    def __init__(self, model, reference, local, role, prior_parameters):
        backbone = model.encoder.backbone
        self.heads, self.role, self.prior_parameters = None, role, prior_parameters
        self.reference = reference
        self.stages = reference.StageReferences(backbone)
        self.geometry = None
        try:
            self.geometry = local.LocalModules(backbone, reference, {})
            # Filter only the observer registry. Never modify model modules or their forwards.
            self.geometry.modules = {name: entry for name, entry in self.geometry.modules.items()
                                     if entry[1] in ('distance_mlp', 'pair_encoder')}
            shared = hasattr(backbone, 'pair_encoder')
            need(len(self.geometry.modules) == (1 if shared else 6), 'Actual distance capture scope differs')
            self.geometry.arm()
            self.heads = HeadPorts(model.pd_heads,role)
        except BaseException:
            self.stages.close()
            if self.geometry is not None: self.geometry.disarm()
            if self.heads is not None: self.heads.close()
            raise
    def disarm(self):
        if self.heads is not None: self.heads.disarm()
        self.geometry.disarm()
        pending, masks, data = dict(self.stages.pending), dict(self.stages.pending_masks), self.stages.input
        # The frozen StageReferences.close ALSO clears refs. Only detach its handles here.
        for handle in self.stages.handles: handle.remove()
        self.stages.handles.clear()
        need(self.stages.input is data and self.stages.pending.keys() == pending.keys()
             and all(self.stages.pending[k] is v for k,v in pending.items())
             and self.stages.pending_masks.keys() == masks.keys()
             and all(self.stages.pending_masks[k] is v for k,v in masks.items()),
             'Disarming must retain exactly the original pending input/stage/mask objects')
    def take(self, views, full_result):
        need(not self.stages.handles and not self.geometry.handles and not self.geometry.armed,
             'All hooks must be removed before any copy/processing')
        cpu_rng = torch.get_rng_state()
        cuda_rng = torch.cuda.get_rng_state()
        need(all(v.dtype == torch.float32 and v.device.type == 'cuda' for v in self.stages.pending.values()),
             'All actual stage ports must remain CUDA F32')
        result = self.stages.take(views.clean_atom_rows)
        data = result['input']
        batch = numpy_copy(data.batch)
        pos = numpy_copy(data.pos)
        elements = numpy_copy(data.x)
        rows = numpy_copy(result['clean_rows'])
        need(batch.dtype == np.int64 and pos.dtype == np.float32 and elements.dtype == np.int64
             and rows.dtype == np.int64 and rows.shape == (44,), 'Actual native row types differ')
        n = len(batch)
        need(n in (88,132) and pos.shape == (n,3) and np.array_equal(np.unique(batch), np.arange(batch.max()+1)),
             'Fixed physical view node/graph population differs')
        counts = np.bincount(batch).tolist()
        view_count = 2 if n == 88 else 3
        need(counts == [count for count in (3,9,32) for _ in range(view_count)]
             and np.array_equal(batch, np.repeat(np.arange(len(counts)), counts)), 'Native graph/atom order differs')
        need(len(np.unique(rows)) == 44 and np.all((rows >= 0) & (rows < n)), 'Clean44 row binding differs')
        _, mask = to_dense_batch(data.batch, data.batch, fill_value=0)
        need(tuple(mask.shape) == (len(counts),32) and mask.dtype == torch.bool, 'Actual dense mask shape differs')
        need(set(self.geometry.masks) == set(range(6))
             and all(self.reference.tensor_header(v) == self.reference.tensor_header(mask)
                     for v in self.geometry.masks.values()), 'All six actual layer masks must match physical rows')
        arrays = dict(pos=pos, batch=batch, elements=elements, clean_rows=rows,
                      native_row=np.arange(n,dtype=np.int64), dense_mask=numpy_copy(mask),
                      base_graph_index=numpy_copy(views.base_graph_index),
                      base_atom_index=numpy_copy(views.base_atom_index),
                      clean_graph_rows=numpy_copy(views.clean_graph_rows),
                      graph_sample_type=numpy_copy(views.batch.sample_type_id))
        need(all(arrays[key].dtype == np.int64 for key in ('base_graph_index','base_atom_index','clean_graph_rows','graph_sample_type')),
             'Actual view association indices must be int64')
        need(np.array_equal(arrays['base_graph_index'],np.repeat(np.arange(3),view_count))
             and np.array_equal(arrays['clean_graph_rows'],np.arange(0,3*view_count,view_count))
             and np.array_equal(arrays['graph_sample_type'].reshape(-1),np.tile((0,3) if view_count==2 else (0,1,2),3))
             and arrays['base_atom_index'].shape == (n,), 'Actual original view/base row association differs')
        need(self.reference.tensor_header(data.x) == self.reference.tensor_header(views.batch.x)
             and self.reference.tensor_header(data.pos) == self.reference.tensor_header(views.batch.pos)
             and self.reference.tensor_header(data.batch) == self.reference.tensor_header(views.batch.batch),
             'Observed backbone input differs from original full physical views')
        need(set(result['stages']) == set(STAGES), 'All nine original stage boundaries required')
        for name in STAGES:
            value = result['stages'][name]
            need(value.dtype == torch.float32 and tuple(value.shape) == (n,512), 'Non-F32/mixed or wrong stage shape')
            arrays['stage__'+name] = numpy_copy(value)
        need(arrays['stage__out_norm'].tobytes() == arrays['stage__packed_H0'].tobytes(),
             'Actual packed H0 and masked out_norm bytes differ')
        pair_mask = mask[:,:,None] & mask[:,None,:]
        pair_rows = sum(count*count for count in counts)
        need(int(pair_mask.sum()) == pair_rows and set(self.geometry.records) == set(self.geometry.modules),
             'Complete actual ordered native-pair population required')
        geometry = []
        for name, record in self.geometry.records.items():
            _, kind, index = self.geometry.modules[name]
            if kind == 'distance_mlp':
                need(len(record['args']) == 1 and not record['kwargs'], 'Actual distance MLP input differs')
                value = record['args'][0]
                need(tuple(value.shape) == (*mask.shape,mask.shape[1],1), 'Actual dist2 input shape differs')
                key, quantity, unit = 'geometry__layer%d_dist2' % index, 'actual_squared_distance_input_to_TiledDistanceMLP', 'angstrom_squared'
            else:
                need(len(record['args']) == 3 and not record['kwargs'] and isinstance(record['output'], tuple)
                     and len(record['output']) == 2, 'Actual Gaussian pair encoder contract differs')
                value = record['output'][1]
                need(tuple(value.shape) == (*mask.shape,mask.shape[1]), 'Actual Gaussian distance output shape differs')
                key, quantity, unit = 'geometry__shared_distance', 'actual_SharedGaussianPairEncoder_distance_output', 'angstrom'
            need(value.dtype == torch.float32 and value.device.type == 'cuda', 'Actual geometry port must be CUDA F32')
            selected = value.detach().cpu()[pair_mask]
            if selected.ndim == 1: selected = selected[:,None]
            need(tuple(selected.shape) == (pair_rows,1), 'Physical ordered-pair scalar shape differs')
            arrays[key] = numpy_copy(selected)
            geometry.append(dict(array=key, module=name, quantity=quantity, unit=unit, physical_pairs=pair_rows,
                                 includes_diagonal=True, padding_in_statistics=False))
        head_arrays,head_metadata = self.heads.take(arrays,array_header,self.prior_parameters,full_result)
        need(not (set(head_arrays) & set(arrays)), 'New head port keys conflict with original trace')
        arrays.update(head_arrays)
        need(torch.equal(cpu_rng,torch.get_rng_state()) and torch.equal(cuda_rng,torch.cuda.get_rng_state()),
             'Passive post-forward copy/metadata consumed RNG')
        return arrays, dict(native_nodes=n, clean_rows=44, channels=512, native_nodes_by_graph=counts,
            head_ports=head_metadata, contains_parameter_weights=self.role==0,
            actual_dense_mask=self.reference.tensor_header(mask), stages=list(STAGES), geometry=geometry,
            physical_order='original packed atom rows; dense flatten selected by actual native mask',
            ordered_pair_order='graph ascending, native i ascending then native j ascending; includes diagonal',
            pair_row_binding='reconstruct from saved contiguous batch and native_row; no dedup or mirrored reduction',
            copies_after_full_model_return_and_all_own_capture_hooks_removed=True, postprocess_RNG_unchanged=True)
    def close(self):
        self.disarm()
        self.stages.close()  # Original full cleanup only AFTER take/copy or an aborted capture.
        if self.heads is not None: self.heads.close()
        self.geometry.records.clear(); self.geometry.masks.clear()
        need(not self.stages.handles and not self.stages.pending and not self.stages.pending_masks
             and self.stages.input is None and not self.geometry.handles and not self.geometry.records
             and not self.geometry.masks, 'Final original observer cleanup incomplete')

@contextmanager
def passive_composition(equation, reference, local, directory, budget):
    """Wrap only this case's already-created model; original full call returns unchanged."""
    old_build = equation.build_composition
    holder = dict(calls=[], errors=[], forward_calls=0, full_forward_returns=0, observed_encoder_returns=0, geometry_policy=None)
    models = []
    def build(spec):
        model, registry = old_build(spec)
        need(not models, 'Exactly one original model per case')
        holder['synthetic_weight_seed'] = spec.weight_seed
        holder['geometry_policy'] = reference.geometry_policy(model.encoder)  # Assertions only; no setters.
        holder['state_before'] = state_sha(model,local,reference)
        models.append(model)
        original = model.forward_pretrain
        had_override, previous = 'forward_pretrain' in model.__dict__, model.__dict__.get('forward_pretrain')
        holder['restore'] = (model,had_override,previous)
        def forward(*args, **kwargs):
            role = holder['forward_calls']; holder['forward_calls'] += 1
            need(role < 4, 'Only four original full forwards allowed')
            observer = None
            try:
                observer = RoleCapture(model,reference,local,role,holder.get("charge_parameters"))
            except Exception as error:
                holder['errors'].append(dict(role=role,scope='arm',type=type(error).__name__,message=str(error)))
                result = original(*args,**kwargs)
                holder['full_forward_returns'] += 1
                return result
            try:
                try:
                    result = original(*args,**kwargs)  # Exactly once; return this exact original object.
                    holder['full_forward_returns'] += 1
                finally:
                    holder['observed_encoder_returns'] += int('packed_H0' in observer.stages.pending)
                    observer.disarm()
                try:
                    arrays, metadata = observer.take(args[0],result)
                    artifact = budget.arrays(Path(directory)/('role_%d.npz'%role), arrays)
                    holder['calls'].append(dict(role=role,artifact=artifact,population=metadata))
                    if role==0: holder['charge_parameters']=metadata['head_ports']['parameter_bindings']
                except Exception as error:
                    # Only post-forward capture errors are retained; the original forward exception propagates.
                    holder['errors'].append(dict(role=role,type=type(error).__name__,message=str(error)))
                return result
            finally:
                observer.close()  # Covers original forward, disarm, take, serialization and normal return.
        model.forward_pretrain = forward
        return model,registry
    equation.build_composition = build
    try:
        yield holder
    finally:
        equation.build_composition = old_build
        if 'restore' in holder:
            model,had_override,previous = holder.pop('restore')
            if had_override: model.forward_pretrain = previous
            else: del model.__dict__['forward_pretrain']
            holder['state_after'] = state_sha(model,local,reference)
            holder['state_unchanged'] = holder['state_after'] == holder['state_before']
