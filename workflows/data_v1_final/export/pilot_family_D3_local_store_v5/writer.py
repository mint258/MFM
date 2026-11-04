"""Original MFM3 writer plus permanent pre-cast float64 sidecar, no new codec."""
import collections,hashlib,json,pathlib,sqlite3
import numpy as np
from . import contract as C,io as I,wire as V
from workflows.data_v1_final.export.family_export_day_v1 import store as B,transport as T,project as P
L=C.F.legacy();S=L['pipeline_v1.source'];CODEC=L['wire_v1.codec']
class Sidecar:
    def __init__(self,path):
        self.path=pathlib.Path(path);C.need(not self.path.exists(),'FRESH_PERMANENT_F64_SIDECAR_NO_OVERWRITE');self.db=I.connect(path)
        self.db.execute('CREATE TABLE authority(rid TEXT PRIMARY KEY,metadata TEXT,payload BLOB,sha TEXT)');self.count=0
    def put(self,metadata,arrays):
        C.need(all(a.dtype.itemsize==8 for a in arrays.values() if a.dtype.kind=='f'),'PERMANENT_AUTHORITY_FLOAT64_BEFORE_ORIGINAL_ENCODER')
        raw=S.pack(arrays);sha=hashlib.sha256(raw).hexdigest();rid=metadata['export_record_id']
        self.db.execute('INSERT INTO authority VALUES(?,?,?,?)',(rid,CODEC.canonical_json(metadata).decode(),raw,sha));self.count+=1
        return {'schema':'PERMANENT_F64_SIDECAR_RECORD_V1','file_name':self.path.name,'record_id':rid,'payload_sha256':sha,'source_dtype':'float64','training_casts':1}
    def commit(self):self.db.commit()
    def finish(self):
        self.db.commit();self.db.close();self.db=None;ref=I.pin(self.path);db=I.connect(self.path,True)
        try:
            count=0
            for raw,sha in db.execute('SELECT payload,sha FROM authority'):
                C.need(hashlib.sha256(raw).hexdigest()==sha,'PERMANENT_F64_PAYLOAD_READBACK_SHA');S.unpack(raw);count+=1
            C.need(count==self.count,'ALL_F64_SIDECAR_RECORDS_CLOSED')
        finally:db.close()
        return {'reference':ref,'records':count,'dtype':'float64','immutable':True}
    def close(self):
        if self.db is not None:self.db.close();self.db=None
class Reader(B.Reader):
    def ordered(self,rid,tid):
        metadata,arrays=self.get(rid);C.need(tid in self.schema.get('ordered_record_targets',{}),'ACTUAL_ORDERED_DOMAIN_TARGET_NOT_ORDINARY_PAIR')
        return V.ordered_entries(arrays,tid,metadata['n_atoms'],self.schema['ordered_record_targets'][tid]['members'][0]['field_key'])
    def get_f64(self,rid,sidecar_reference):
        with I.F.held(sidecar_reference,[sidecar_reference],lambda:None):pass
        db=I.connect(sidecar_reference['path'],True)
        try:
            row=db.execute('SELECT metadata,payload,sha FROM authority WHERE rid=?',(rid,)).fetchone();C.need(row is not None,'EXACT_F64_AUTHORITY_RECORD')
            m,a=self.get(rid);C.need(m['permanent_F64_sidecar_record']['payload_sha256']==row['sha'] and hashlib.sha256(row['payload']).hexdigest()==row['sha'],'LMDB_TO_ACTUAL_F64_AUTHORITY_BINDING')
            return json.loads(row['metadata']),S.unpack(row['payload'])
        finally:db.close()
def metadata(db,g):
    role=db.execute('SELECT role,source_role FROM molecules WHERE mid=?',(g['molecule_id'],)).fetchone()
    return {'molecule_id':g['molecule_id'],'export_record_id':g['geometry_id'],'geometry_source':g['geometry_source'],
      'effective_role':role[0],'source_role':role[1],'n_atoms':len(g['atomic_numbers']),'parent_geometry_id':g['parent_geometry_id'],'view_id':g['view_id'],
      'geometry_sha256':g['geometry_sha256'],'atom_order_sha256':g['atom_order_sha256'],'actual_input_bundle_sha256':g.get('actual_input_bundle_sha256'),
      'actual_input_file_sha256':json.loads(g['source_provenance_json']).get('original_input_file_sha256'),
      'native_record_id':g['native_record_id'],'sprime_conf_idx':g['sprime_conf_idx'],
      'actual_geometry_provenance':{k:v for k,v in g.items() if k not in ('atomic_numbers','positions_A')},
      'input_view_not_ordinary_N':g.get('view_id')=='actual_wp5_unperturbed_program_input_view_v1'}
def geometry_arrays(db,g):
    if g['geometry_source']=='pm7' and g['parent_geometry_id'] is None:pointer=json.loads(g['source_provenance_json'])
    else:
        anchor=g.get('native_record_id') if g['geometry_source']=='pm7' else g.get('native_anchor_record_id');C.need(type(anchor) is str and anchor,'ACTUAL_ORIGINAL_NATIVE_GRAPH_ANCHOR_REQUIRED')
        row=db.execute('SELECT g.row FROM native_bases b JOIN geometries g ON g.gid=b.gid WHERE b.rid=?',(anchor,)).fetchone();C.need(row is not None,'ANCHOR_IN_ACTUAL_SELECTED_NATIVE_COHORT')
        from workflows.data_v1_final.export.lossless_sqlite_io_v1 import codec as W
        pointer=json.loads(W.decode(row[0])['source_provenance_json'])
    arrays={'atomic_numbers':np.asarray(g['atomic_numbers'],dtype='<i2'),'positions_A':np.asarray(g['positions_A'],dtype='<f8')}
    arrays.update(T.native_bonds(pointer,g['atomic_numbers']));return arrays
def write(db,root,compiled,policy,plan,proof,budget):
    from workflows.data_v1_final.export.lossless_sqlite_io_v1 import codec as W
    root=pathlib.Path(root);config=policy['export_configuration'];size=config['molecules_per_shard'];C.need(type(size) is int and 1<=size<=5000,'WHOLE_MID_INTERNAL_SHARDS_ONLY')
    all_stores=[];index=0;last='';eligibility=collections.Counter()
    db.execute('CREATE TABLE partitions(name TEXT,gid TEXT,kind TEXT,src TEXT,view TEXT,family TEXT,targets TEXT,PRIMARY KEY(name,gid))')
    while True:
        mids=[r[0] for r in db.execute('SELECT mid FROM molecules WHERE mid>? ORDER BY mid LIMIT ?',(last,size))]
        if not mids:break
        budget.check();db.execute('DELETE FROM partitions')
        for mid in mids:
            for gid,src,view in db.execute('SELECT gid,src,view FROM geometries WHERE mid=? AND selected=1 ORDER BY gid',(mid,)):
                domains=[('geometry',None,())];byfamily={}
                for (tid,) in db.execute('SELECT part FROM pieces WHERE gid=? ORDER BY part',(gid,)):
                    t=compiled['ordered_record_targets'].get(tid) or compiled['physical_targets'][tid];byfamily.setdefault(t['family'],[]).append(tid)
                domains.extend(('labels',family,tuple(tids)) for family,tids in sorted(byfamily.items()))
                for kind,family,tids in domains:
                    key=(index,kind,src,view,family,tids);name='pilot_'+str(index).zfill(6)+'_'+hashlib.sha256(CODEC.canonical_json(key)).hexdigest()[:24]
                    db.execute('INSERT INTO partitions VALUES(?,?,?,?,?,?,?)',(name,gid,kind,src,view,family,json.dumps(tids)))
        db.commit()
        for row in db.execute('SELECT DISTINCT name,kind,src,view,family,targets FROM partitions ORDER BY name').fetchall():
            name,kind,src,view,family,tids=row;tids=json.loads(tids);schema={'kind':'geometry'} if kind=='geometry' else T.family_schema(compiled,family,src,tids)
            schema.update(contract_version='v3.0',bounded_pilot_acceptance_reference=plan['pilot_acceptance_reference'],bounded_source_projection_reference=plan['bounded_export_review_reference'],
              D1_design_policy_reference=plan['D1_design_policy_reference'],D1_five_layer_reference=plan['D1_five_layer_reference'],actual_parent_job_id=str(proof['job_id']),
              exact_codec_source_references=plan['codec_source_references'],full_Common_D6_release=False,Model_ACK=False,**C.capabilities(plan))
            path=root/name;side=Sidecar(root/(name+'.authority_f64.sqlite'));writer=B.Writer(path,schema,map_bytes=config['map_bytes_per_store']);buffer=[];buffer_bytes=0
            try:
                for (gid,) in db.execute('SELECT gid FROM partitions WHERE name=? ORDER BY gid',(name,)).fetchall():
                    budget.check();g=W.decode(db.execute('SELECT row FROM geometries WHERE gid=?',(gid,)).fetchone()[0]);m=metadata(db,g);arrays={};notes={};locators={}
                    if C.native_mode(plan):
                        ranks={r[0]:r[1] for r in db.execute('SELECT kind,rank FROM orders WHERE gid=?',(gid,))}
                        C.need(set(ranks)<={'fixed_random'},'NO_UNAVAILABLE_NATIVE_ORDER_METADATA')
                        m.update(**C.capabilities(plan),available_base_order_ranks=ranks,
                          ordered_base_only=g['parent_geometry_id'] is None and db.execute('SELECT aux FROM geometries WHERE gid=?',(gid,)).fetchone()[0]==0,
                          unavailable_order_request='REFUSE_ENERGY_DIVERSITY_OR_LOWEST_ENERGY_RANK0_NOT_RELEASED')
                    if kind=='geometry':arrays=geometry_arrays(db,g)
                    else:
                        for tid in tids:
                            p=db.execute('SELECT payload,source_locator FROM pieces WHERE gid=? AND part=?',(gid,tid)).fetchone();C.need(p is not None,'ALL_ACTUAL_PARTITION_TARGETS_PRESENT')
                            a=S.unpack(p[0]);C.need(not set(arrays)&set(a),'NO_OVERLAPPING_FAMILY_ARRAYS');arrays.update(a);notes.update(S.reason_annotations(p[0]));locators[tid]=json.loads(p[1])
                        m.update(group_exposure_mask=config['group_exposure_mask'],family_exposure_mask=config['family_exposure_mask'],reason_granularity=notes,
                          reason_codebook_sha256=policy['reason_codebook_reference']['sha256'],permanent_source_locators=locators,
                          source_missing_positions={t:v['typed_missing_positions'] for t,v in locators.items()},source_precision=policy['source_precision_policy'])
                        target_policy={}
                        for tid in tids:
                            target_policy[tid]=dict(policy['target_policy'].get(tid,{}),actual_task_charge=locators[tid]['actual_task_charge'])
                        m=V.annotate(m,arrays,schema,target_policy,{t:locators[t]['member_geometry_ids'] for t in tids})
                        if C.native_mode(plan):
                            disabled={tid:{'status':'DISABLED_UNIT_UNSPECIFIED','eligible':False,'numeric_mask_changed':False,
                              'unit_status':'UNKNOWN_ORIGINAL_SOURCE_SCHEMA','original_values_exported':True}
                              for tid in tids if any(x['field_key']=='D20.MolMR' for x in compiled['physical_targets'].get(tid,{}).get('members',[]))}
                            if disabled:
                                C.need(all(target_policy[tid]['physical_policy_status']=='DISABLED_UNIT_UNSPECIFIED' for tid in disabled),
                                  'MOLMR_UNKNOWN_UNIT_ALWAYS_PHYSICAL_LOSS_OFF_NOT_VALUE_MASK_OR_FIELD_DELETE')
                                m['target_loss_exposure']=disabled
                        for tid,state in m['loss_eligibility'].items():eligibility[tid+'/'+m['effective_role']+'/'+state['status']]+=1
                    m['actual_geometry_manifest_reference']=plan['actual_geometry_manifest_reference']
                    m['actual_field_geometry_claims_reference']=policy['actual_cell_binding_reference']
                    original_m=dict(m);m['permanent_F64_sidecar_record']=side.put(original_m,arrays);buffer.append((m,arrays));buffer_bytes+=sum(a.nbytes for a in arrays.values())
                    if len(buffer)>=64 or buffer_bytes>=128<<20:
                        side.commit();writer.write_batch(buffer);buffer=[];buffer_bytes=0
                    db.execute('INSERT INTO exported VALUES(?,?,?,?)',(name,gid,kind,json.dumps(tids)))
                if buffer:side.commit();writer.write_batch(buffer)
                f64=side.finish();receipt=writer.finish()
            finally:side.close();writer.close()
            manifest={'name':name,'path':str(path),'kind':kind,'geometry_source':src,'view_id':view,'family':family,
              'manifest_reference':I.pin(path/'manifest.json'),'f64_authority':f64,**receipt,**C.capabilities(plan)}
            ref=I.save(root/(name+'.closed_store.json'),manifest);db.execute('INSERT INTO stores VALUES(?,?,?)',(name,str(path),json.dumps(ref)));db.commit();all_stores.append(ref)
        I.append(root/'shard_checkpoints.jsonl',{'index':index,'first_mid':mids[0],'last_mid':mids[-1],'molecules':len(mids),'all_stores_and_f64_closed':True,'parent_job_id':str(proof['job_id'])})
        last=mids[-1];index+=1
    C.need(db.execute('SELECT count(*) FROM geometries WHERE selected=1 AND gid NOT IN(SELECT gid FROM exported WHERE kind=\'geometry\')').fetchone()[0]==0,'ALL_SELECTED_BASE_CHILD_AND_INPUT_VIEW_GEOMETRY_STORED')
    return all_stores,dict(eligibility)
