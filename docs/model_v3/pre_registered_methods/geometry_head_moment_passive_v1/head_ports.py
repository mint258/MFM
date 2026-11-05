"""Only two synthetic dipole heads: retain original objects, never replace returns."""
from contextlib import contextmanager
import numpy as np
import torch
from torch.overrides import TorchFunctionMode
from phychem_mfm.model import v3_heads as implementation

FIELDS = ('p_dipole', 'p_dipole_magnitude')
PARAM_SHAPES = {'0.weight':(64,512), '0.bias':(64,), '2.weight':(1,64), '2.bias':(1,)}
PARAMETER_BYTES = 263176


def need(ok, message):
    if not ok: raise ValueError(message)


def copied(value):
    return value.detach().cpu().contiguous().numpy().copy()


class HeadPorts:
    """Aliases/hooks are local to one full original forward and restored before copies."""
    def __init__(self, bank, role):
        self.bank, self.role, self.active = bank, role, None
        self.records = {name:[] for name in FIELDS}
        self.handles, self.overrides, self.modules = [], [], {}
        self.aliases = {name:getattr(implementation,name) for name in
                        ('compensated_pool','compensated_index_add','compensated_norm3')}
        self.armed = False
        try:
            for name in FIELDS:
                head = bank.field_heads[bank.keys[name]]
                need(type(head).__name__ == '_DipoleHead'
                     and head.magnitude is (name == 'p_dipole_magnitude'), 'Actual independent dipole head differs')
                need({k:tuple(p.shape) for k,p in head.charges.named_parameters()} == PARAM_SHAPES
                     and not list(head.charges.named_buffers()), 'Actual charges MLP/state layout differs')
                self.modules[name] = head
                original = head.forward
                had, previous = 'forward' in head.__dict__, head.__dict__.get('forward')
                self.overrides.append((head,had,previous,original))
                head.forward = self._forward(name,original)
                self.handles.append(head.charges.register_forward_hook(self._charge_hook(name)))
            need(self.modules[FIELDS[0]] is not self.modules[FIELDS[1]]
                 and self.modules[FIELDS[0]].charges is not self.modules[FIELDS[1]].charges,
                 'The two independently parameterized heads must not be collapsed')
            for alias in self.aliases:
                setattr(implementation,alias,self._alias(alias))
            self.armed = True
        except BaseException:
            self.disarm()
            raise

    def _charge_hook(self,name):
        def hook(module,args,output):
            if self.active is not None and self.active['field'] == name:
                self.active['charge_calls'].append((args,output))
            # Forward hooks return None: no tensor substitution.
        return hook

    def _alias(self,name):
        original = self.aliases[name]
        def call(*args,**kwargs):
            result = original(*args,**kwargs)
            if self.active is not None:
                self.active['aliases'][name].append((args,kwargs,result))
            return result
        return call

    def _forward(self,name,original):
        observer = self
        class Operations(TorchFunctionMode):
            def __init__(self,record):
                super().__init__(); self.record=record
            def __torch_function__(self,func,types,args=(),kwargs=None):
                kwargs = {} if kwargs is None else kwargs
                result = func(*args,**kwargs)  # Once; return this exact original result.
                record = self.record
                label = getattr(func,'__name__','')
                # Only identities and Python metadata are read inside the original head.
                centers = record['aliases']['compensated_pool']
                charges = record['charge_calls']
                if label == '__getitem__' and len(args)==2 and centers and args[0] is centers[-1][2] and args[1] is record['batch']:
                    record['indexed_center'].append(result)
                if label in ('sub','__sub__') and len(args)==2 and record['indexed_center'] and args[0] is record['pos'] and args[1] is record['indexed_center'][-1]:
                    record['relative'].append(result)
                if label in ('mul','__mul__') and len(args)==2 and charges and record['relative'] and args[0] is charges[-1][1] and args[1] is record['relative'][-1]:
                    record['product'].append(result)
                return result
        def forward(h,pos,batch,graphs):
            record = dict(field=name,h=h,pos=pos,batch=batch,graphs=graphs,
                charge_calls=[],indexed_center=[],relative=[],product=[],
                aliases={alias:[] for alias in observer.aliases},output=None)
            observer.records[name].append(record)
            previous=observer.active
            observer.active=record
            try:
                with Operations(record):
                    result=original(h,pos,batch,graphs)  # Original complete head exactly once.
                record['output']=result
                return result
            finally:
                observer.active=previous
        return forward

    def disarm(self):
        for handle in self.handles: handle.remove()
        self.handles.clear()
        for head,had,previous,_ in reversed(self.overrides):
            if had: head.forward=previous
            elif 'forward' in head.__dict__: del head.__dict__['forward']
        self.overrides.clear()
        for name,original in self.aliases.items(): setattr(implementation,name,original)
        self.armed=False
        self.active=None

    def take(self,base_arrays,header,prior_parameters,full_result):
        need(not self.handles and not self.overrides and not self.armed,
             'Disarm all head observation before any validation/copy')
        need(self.role in range(4) and set(self.records)==set(FIELDS)
             and all(len(v)==1 for v in self.records.values()), 'Exactly two original head calls per role required')
        rows=base_arrays['clean_rows']
        expected_h=base_arrays['stage__packed_H0'][rows]
        expected_pos=base_arrays['pos'][rows]
        expected_batch=np.repeat(np.arange(3,dtype=np.int64),(3,9,32))
        arrays,metadata,bindings={},[],{}
        shared=None
        for name in FIELDS:
            r=self.records[name][0]
            need(full_result.clean_h0 is r['h'] and full_result.pd_predictions[name] is r['output'],
                 'Actual head input/output objects must be the full same-forward returned H0/terminal')
            need(r['graphs']==3 and len(r['charge_calls'])==len(r['indexed_center'])==len(r['relative'])==len(r['product'])==1,
                 'Exact original charge/index/sub/product call sequence required')
            pool=r['aliases']['compensated_pool']; reduce=r['aliases']['compensated_index_add']; norm=r['aliases']['compensated_norm3']
            need(len(pool)==len(reduce)==1 and len(norm)==int(name==FIELDS[1]),
                 'Original center/moment/norm alias call coverage differs')
            pa,pk,center=pool[0]; ra,rk,moment=reduce[0]
            qa,q=r['charge_calls'][0]
            need(len(pa)==4 and pa[0] is r['pos'] and pa[1] is r['batch'] and pa[2:]==(3,'mean') and not pk
                 and len(qa)==1 and qa[0] is r['h']
                 and len(ra)==3 and ra[1] is r['batch'] and ra[2] is r['product'][0] and not rk,
                 'Actual operands are not the original center/readout/moment operands')
            need(isinstance(ra[0],torch.Tensor) and ra[0].dtype==torch.float32
                 and ra[0].device.type=='cuda' and tuple(ra[0].shape)==(3,3)
                 and not np.any(copied(ra[0])), 'Actual moment base must remain the original literal FP32 zero')
            if name==FIELDS[1]:
                na,nk,no=norm[0]
                need(len(na)==1 and na[0] is moment and nk=={'keepdim':True} and no is r['output'],
                     'Magnitude must use its own captured moment and original norm')
            else:
                need(moment is r['output'], 'Vector output must be the original reduced moment object')
            tensors=dict(h=r['h'],pos=r['pos'],charges=q,center=center,indexed_center=r['indexed_center'][0],
                         relative=r['relative'][0],product=r['product'][0],moment=moment,output=r['output'])
            shapes=dict(h=(44,512),pos=(44,3),charges=(44,1),center=(3,3),indexed_center=(44,3),
                        relative=(44,3),product=(44,3),moment=(3,3),output=(3,1) if name==FIELDS[1] else (3,3))
            need(all(isinstance(v,torch.Tensor) and v.dtype==torch.float32 and v.device.type=='cuda'
                     and tuple(v.shape)==shapes[k] for k,v in tensors.items())
                 and r['batch'].dtype==torch.long and r['batch'].device.type=='cuda' and tuple(r['batch'].shape)==(44,), 'Actual head port dtype/shape/device differs')
            values={k:copied(v) for k,v in tensors.items()}
            batch=copied(r['batch'])
            need(np.array_equal(values['h'],expected_h) and np.array_equal(values['pos'],expected_pos)
                 and np.array_equal(batch,expected_batch), 'Actual head inputs differ from same-forward clean44/native rows')
            if shared is None:
                arrays.update(head__H0=values['h'],head__pos=values['pos'],head__batch=batch)
                shared=(r['h'],r['pos'],r['batch'])
            else:
                need(r['h'] is shared[0] and r['pos'] is shared[1] and r['batch'] is shared[2],
                     'Both heads must consume the same original bank input objects')
            prefix='head__'+name+'__'
            for key in ('charges','center','indexed_center','relative','product','moment','output'):
                arrays[prefix+key]=values[key]
            parameters=dict(self.modules[name].charges.named_parameters())
            names={}
            for key in PARAM_SHAPES:
                value=parameters[key]
                need(value.dtype==torch.float32 and value.device.type=='cuda' and tuple(value.shape)==PARAM_SHAPES[key],
                     'Actual synthetic charges parameter identity/layout differs')
                array_name=prefix+'parameter__'+key
                if self.role==0:
                    arrays[array_name]=copied(value); names[key]=dict(array=array_name,**header(arrays[array_name]))
                else:
                    need(type(prior_parameters) is dict and name in prior_parameters and key in prior_parameters[name],
                         'Later roles must bind the completed role0 parameter subset')
                    names[key]=prior_parameters[name][key]
            bindings[name]=names
            metadata.append(dict(field=name,head_class=type(self.modules[name]).__name__,magnitude=self.modules[name].magnitude,
                arrays={key:prefix+key for key in ('charges','center','indexed_center','relative','product','moment','output')},
                original_head_calls=1,original_charge_calls=1,original_center_calls=1,original_product_calls=1,
                original_moment_calls=1,original_norm_calls=int(name==FIELDS[1]),
                parameter_names=list(PARAM_SHAPES),parameters_role0_only=True,
                actual_reduction_base='verified original literal3x3 FP32 zero',
                full_returned_H0_and_terminal_object_identity=True))
        if self.role==0:
            need(sum(v.nbytes for k,v in arrays.items() if '__parameter__' in k)==PARAMETER_BYTES,
                 'Exactly263176B synthetic two-charges-MLP subset required')
        else:
            need(not any('__parameter__' in k for k in arrays),'Later role must not duplicate parameters')
        return arrays,dict(fields=metadata,parameter_bindings=bindings,
            contains_parameter_weights=self.role==0,
            parameter_scope='Seeded synthetic two independent charges-MLP subsets only; no trained/native/full model weights',
            parameter_arrays_role=0,actual_clean_native_atoms=[3,9,32],
            original_objects_retained_no_return_replacement=True,all_new_copies_after_full_return_and_disarm=True)

    def close(self):
        self.disarm()
        self.records.clear();self.modules.clear()
        need(not self.handles and not self.overrides and not self.records and not self.modules,
             'Head observer final cleanup incomplete')
