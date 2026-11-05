"""Actual readonly local MFM3 -> existing Model typed objects, no fake labels."""
from __future__ import annotations
from collections import OrderedDict
from dataclasses import dataclass
import hashlib,json,os
from pathlib import Path
import numpy as np
from .common import need,read,reference,local,sqlite_local,frame,digest,VERSION
from phychem_mfm.phase1.v3_wire_audit import SampleSourceAudit

@dataclass(frozen=True)
class ProvisionalAudit(SampleSourceAudit):
    authority:str='actual_provisional_fast55k_payload'
    def __post_init__(self):
        need(self.authority=='actual_provisional_fast55k_payload'and type(self.fields)is tuple,'ACTUAL_PROVISIONAL_AUDIT')
        for v in(self.identity_sha256,self.native_identity_sha256,self.atom_order_sha256,self.codebook_sha256):
            need(type(v)is str and len(v)==64,'SOURCE_AUDIT_HASH')

def modules():
    from workflows.data_v1_final.export.family_export_day_v1 import store,contract
    return store.Reader,contract.legacy()['pipeline_v1.source']

def reason_audit(meta,arrays,target,model_name,row_valid):
    from phychem_mfm.phase1.v3_wire_audit import MemberReasonAudit,FieldReasonAudit
    tid=target['target_id'];valid=arrays['valid/'+tid];gran=meta['reason_granularity'][tid];members=[]
    for i,m in enumerate(target['members']):
        key=m['field_key'];part=valid[...,i]if len(target['members'])>1 else valid
        shape=tuple(gran['members'][key]['leaf_shape']);need(tuple(part.shape)==shape,'SOURCE_MEMBER_MASK_SHAPE')
        codes=[tuple(int(x)for x in arrays['reason_fields_'+s+'/'+key])for s in('source','new','review')]
        members.append(MemberReasonAudit(key,shape,tuple(bool(v)for v in part.reshape(-1)),*codes,
          tuple(int(x)for x in arrays['reason_leaf_index/'+key]),tuple(int(x)for x in arrays['reason_leaf_code/'+key])))
    return FieldReasonAudit(tid,model_name,tuple(valid.shape),tuple(bool(v)for v in valid.reshape(-1)),
      tuple(bool(v)for v in row_valid),tuple(members),meta['group_exposure_mask'][target['group']],
      meta['family_exposure_mask'][target['family']])

def actual_audit(meta,book_sha,field_audits):
    from phychem_mfm.phase1.v3_wire_audit import SampleSourceAudit,identity_sha256
    # Distinct module-level/pickleable authority subtype, never a fixture ACK.
    native={k:meta[k]for k in('molecule_id','export_record_id','geometry_source','native_record_id','sprime_conf_idx')}
    return ProvisionalAudit(meta['export_record_id'],meta['export_record_id'],identity_sha256(meta),digest(native),
      meta['atom_order_sha256'],book_sha,tuple(field_audits))

class ReaderFactory:
    read_only=node_local=True
    def __init__(self,binding_reference,registry):
        self.binding_reference=binding_reference;self.bundle=read(binding_reference);self.registry=registry
        self.data_version=VERSION;self.source_ref=reference(__file__)
        need(registry.authority=='data_line'and registry.version==VERSION,'ACTUAL_MODEL_REGISTRY')
        import importlib
        self.model_source_references=[]
        for name in('v3_data','v3_contract','v3_label_domains','v3_wire_audit','v3_sampling'):
            module=importlib.import_module('phychem_mfm.phase1.'+name);r=reference(module.__file__)
            need(r in self.bundle['source_references'],'ACTUAL_ORIGINAL_MODEL_TYPED_SOURCE_MUST_BE_PINNED')
            self.model_source_references.append(r)
    def __call__(self):return TypedReader(self)

class TypedReader:
    def __init__(self,factory):
        self.factory=factory;self.bundle=factory.bundle;self.root=self.bundle['local_root'];self.pid=os.getpid();self.closed=False
        self.db=sqlite_local(self.bundle['catalog_reference'],self.root);self.handles=OrderedDict();self.sides={}
        self.store_rows={s['name']:s for s in self.bundle['stores']}
        self.store_by_path={s['path']:s for s in self.bundle['stores']}
        self.frames={p:tuple(f)for p,f in self.bundle['local_file_frames'].items()}
        for p,f in self.frames.items():local(p,self.root);need(frame(p)==f,'LOCAL_COPY_CHANGED_AFTER_PREPARATION')
        self.targets=self.bundle['targets'];self.field_by_name=factory.registry.by_name()
        self.codes=read(self.bundle['channel_codebook_reference'])
        self.last_payload_audit=None
    def _reader(self,name):
        need(not self.closed and self.pid==os.getpid(),'WORKER_OWNED_READONLY_HANDLE')
        s=self.store_rows[name];need(frame(Path(s['path'])/'data.mdb')==self.frames[str(Path(s['path'])/'data.mdb')],'LOCAL_LMDB_CHANGED')
        if name in self.handles:r=self.handles.pop(name)
        else:
            cls,_=modules();r=cls(s['path'],expected_schema_sha256=s['schema_sha256'])
        self.handles[name]=r
        while len(self.handles)>16:self.handles.popitem(last=False)[1].close()
        return r
    def _f64(self,name,gid,meta):
        s=self.store_rows[name];r=s['f64_authority'];local(r['path'],self.root)
        need(frame(r['path'])==self.frames[r['path']],'LOCAL_F64_AUTHORITY_CHANGED')
        if name not in self.sides:self.sides[name]=sqlite_local(r,self.root)
        row=self.sides[name].execute('SELECT metadata,payload,sha FROM authority WHERE rid=?',(gid,)).fetchone()
        need(row is not None and hashlib.sha256(row['payload']).hexdigest()==row['sha']==meta['permanent_F64_sidecar_record']['payload_sha256'],
          'EXACT_COPIED_F64_AUTHORITY_NOT_ORIGINAL_SHARED_PATH')
        _,source=modules();return json.loads(row['metadata']),source.unpack(row['payload']),r
    def read_geometry(self,gid,*,for_training=False):
        """Real typed payload transport, including retained fields not in a loss."""
        import torch
        from phychem_mfm.phase1.v3_data import DecodedSample,NativeBondTransport
        from phychem_mfm.phase1.v3_contract import FieldTarget
        from phychem_mfm.phase1.v3_label_domains import ChannelCodebook,ordered_entries_from_f64,tensor6_from_f64
        from workflows.data_v1_final.export.family_export_day_v1.transport import decode_strings
        row=self.db.execute('SELECT * FROM geometries WHERE gid=?',(gid,)).fetchone();need(row is not None,'ACTUAL_EXPORTED_GEOMETRY_ONLY')
        geometry_store=row['store'];m,g=self._reader(geometry_store).get(gid);gm,g64,geometry_ref=self._f64(geometry_store,gid,m)
        need(m['export_record_id']==gid and m['geometry_sha256']==row['geometry_sha']and m['atom_order_sha256']==row['atom_sha'],'EXACT_ORIGINAL_GEOMETRY_IDENTITY')
        z=g['atomic_numbers'];pos=g['positions_A'];n=m['n_atoms']
        need(z.shape==(n,)and pos.shape==(n,3)and pos.dtype==np.dtype('<f4'),'ACTUAL_ONCE_F32_GEOMETRY')
        need(hashlib.sha256(np.asarray(z,dtype='<i8').tobytes()).hexdigest()==m['atom_order_sha256'],'EXPLICIT_SOURCE_ROW_ATOM_ORDER')
        actual_geometry_ref=self.store_rows[geometry_store]['data'];fields={};domains={};audits=[];retained={}
        for item in self.db.execute('SELECT tid,store FROM labels WHERE gid=? ORDER BY tid',(gid,)):
            tid,name=item['tid'],item['store'];t=self.targets[tid];lm,a=self._reader(name).get(gid);_,a64,f64ref=self._f64(name,gid,lm)
            need(all(lm[k]==m[k]for k in('molecule_id','export_record_id','geometry_source','effective_role','source_role','n_atoms','geometry_sha256','atom_order_sha256')),
              'FAMILY_ACTUAL_GEOMETRY_ROLE_ANCHOR_NOT_MID_ONLY_JOIN')
            model=t['target_id'];retained[model]={'source_fields':[v['field_key']for v in t['members']],
              'reason_granularity':lm['reason_granularity'][tid],'permanent_source_locators':lm['permanent_source_locators'][tid]}
            binding=self.bundle['target_bindings'][tid];frame_binding=binding['frame_binding']
            if t.get('wire_kind')=='SOURCE_ORDERED_RECORDS_V1':
                p='transport/'+tid+'/';tokens=self.codes['tokens'];need(tokens,'NO_ACTUAL_R73_CHANNEL_CODEBOOK')
                book=ChannelCodebook(tuple(tokens),self.bundle['channel_codebook_reference'])
                left=decode_strings(a[p+'basis_i_utf8'],a[p+'basis_i_offsets']);right=decode_strings(a[p+'basis_j_utf8'],a[p+'basis_j_offsets'])
                atom=np.stack([a[p+'atom_i'],a[p+'atom_j']]);channels=np.asarray([book.encode(left),book.encode(right)],dtype='<i8');count=len(left)
                cause={scope:[int(v)for v in a['reason_fields_'+scope+'/'+t['members'][0]['field_key']]]for scope in('source','new','review')}
                reasons=[];key=t['members'][0]['field_key'];ix=a['reason_leaf_index/'+key];co=a['reason_leaf_code/'+key]
                channel=decode_strings(a[p+'channel_utf8'],a[p+'channel_offsets'])
                for k in range(count):reasons.append(dict(cause,source_leaf_codes=[int(v)for i,v in zip(ix,co)if int(i)==k],
                  source_onsite_present=bool(a[p+'onsite_present'][k]),source_onsite=bool(a[p+'onsite'][k]),
                  source_channel_present=bool(a[p+'channel_present'][k]),source_channel=channel[k],
                  src_basis=left[k],dst_basis=right[k],entry_ordinal=int(a[p+'ordinal'][k])))
                numeric=binding.get('numeric_source_frame');origin=basis=None
                if numeric is not None:
                    fr=read(numeric['reference']);origin=torch.tensor([fr['origin']],dtype=torch.float32);basis=torch.tensor([fr['basis']],dtype=torch.float32)
                if for_training and model in self.field_by_name and numeric is None:
                    raise ValueError('R73_NUMERIC_FRAME_ORIGIN_BASIS_NOT_IN_NONAXIAL_SOURCE:'+model)
                target=ordered_entries_from_f64(values=torch.from_numpy(a64[p+'values'].copy()).reshape(-1,1),
                  source_valid=torch.from_numpy(a['valid/'+p].astype(bool)),atom_index=torch.from_numpy(atom.copy()).long(),
                  channel_index=torch.from_numpy(channels),entry_ordinal=torch.from_numpy(a[p+'ordinal'].copy()).long(),
                  n_atoms=n,geometry_id=gid,codebook=book,frame_binding=frame_binding,reasons=reasons,source_ref=f64ref,
                  geometry_ref=actual_geometry_ref,frame_origin=origin,frame_basis=basis)
                need(target.values.numpy().tobytes()==a[p+'values'].reshape(-1,1).tobytes(),'R73_ONE_F64_TO_F32_CAST_EXACT_WIRE_BYTES')
                fields[model]=target;domains[model]=target.inputs
            elif t['kind']=='symmetric_tensor':
                need(t['component_order']==['xx','xy','yy','xz','yz','zz'],'SOURCE_FULL6_ORDER')
                cg=lm['permanent_source_locators'][tid]['member_geometry_ids']
                target=tensor6_from_f64(values=torch.from_numpy(a64['values/'+tid].copy()).reshape(1,6),
                  component_valid=torch.from_numpy(a['valid/'+tid].astype(bool)).reshape(1,6),geometry_ids=(gid,),
                  component_geometry_ids=(tuple(cg),),reasons=(retained[model],),source_ref=f64ref)
                need(target.values.numpy().tobytes()==a['values/'+tid].reshape(1,6).tobytes(),'FULL6_SINGLE_CAST_EXACT')
                fields[model]=target # OFF: no invented Tensor6Inputs origin.
            else:
                val=a['values/'+tid];mask=a['valid/'+tid].astype(bool);width=3 if t['kind']=='vector'else 1
                pair=None;count=1 if t['level']=='molecule'else n
                if t['level']=='pair':pair=torch.from_numpy(a['pairs/'+tid].copy()).long().T.contiguous();count=pair.shape[1]
                need(val.dtype==np.dtype('<f4'),'ACTUAL_TRAIN_WIRE_FLOAT32_NOT_RECAST_FROM_APPROXIMATE_VALUE')
                rowmask=mask.reshape(count,width).all(axis=1)
                fields[model]=FieldTarget(torch.from_numpy(val.copy()).reshape(count,width),torch.from_numpy(rowmask.copy()),pair)
                audits.append(reason_audit(lm,a,t,model,rowmask))
        bonds=None;status=row['native_bond_status'];fail=row['native_bond_fail_reason']
        if status is not None:
            bonds=NativeBondTransport(torch.from_numpy(g['native_bond_index'].copy()).long(),
              torch.from_numpy(g['native_bond_order'].copy()).long(),status,fail or '')
        requested={f.name for f in self.factory.registry.fields if f.group!='S'}
        if for_training:
            for f in self.factory.registry.fields:
                if (f.level=='ordered_entry'or f.representation=='symmetric_tensor6')and f.name not in fields:
                    raise ValueError('TYPED_TARGET_NOT_PRESENT_AT_EXACT_PHYSICAL_GEOMETRY_NO_FALSE_PLACEHOLDER:'+f.name+':'+gid)
            if getattr(self.factory,'require_native_bond_status',False):
                need(status is not None,'NATIVE_BOND_LITERAL_STATUS_NOT_EXPORTED_REQUIRES_ACTUAL_SOURCE_SUPPLEMENT')
        self.last_payload_audit={'geometry_id':gid,'source_metadata':m,'retained_all_actual_targets':retained,
          'source_component_definitions':146,'native_bond_arrays_retained':True,'native_bond_status_observed':status is not None,
          'local_geometry_data_reference':actual_geometry_ref,'raw_F64_geometry_reference':geometry_ref}
        # The transport API returns every actually present physical target; the
        # training API applies its explicit Model registry, never a data filter.
        selected=fields if not for_training else {k:v for k,v in fields.items()if k in requested}
        audit=actual_audit(m,self.bundle['reason_codebook_reference']['sha256'],audits)
        return DecodedSample(m['molecule_id'],gid,{'pm7':'PM7','uff_sprime':'Sprime_UFF'}[m['geometry_source']],
          torch.from_numpy(z.copy()).long()[:,None]-1,torch.from_numpy(pos.copy()),torch.arange(n,dtype=torch.long),
          selected,bonds,audit,{k:v for k,v in domains.items()if k in selected},actual_geometry_ref)
    def read(self,choice):
        row=self.db.execute('SELECT mid,source,role,n_atoms FROM geometries WHERE gid=?',(choice.locator,)).fetchone()
        need(row is not None and row['mid']==choice.molecule_id and choice.conformer_id==choice.locator
          and {'pm7':'PM7','uff_sprime':'Sprime_UFF'}[row['source']]==choice.geometry_source
          and row['n_atoms']==choice.native_atoms,'ACTUAL_CHOICE_NATIVE_ID_SOURCE_ORDER')
        need(choice.index_sha256 in self.bundle['role_index_sha256'].values(),'ACTUAL_INDEX_IDENTITY')
        return self.read_geometry(choice.locator,for_training=True)
    def close(self):
        for r in self.handles.values():r.close()
        for d in self.sides.values():d.close()
        self.db.close();self.closed=True
