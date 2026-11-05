"""Exactly three same-Parent synthetic methods; not actual10k source acceptance."""
import copy,json,pathlib,tempfile,unittest
import numpy as np
from . import wire as V,writer as W,domain as D,contract as C
WORKSPACE=None
class Boundaries(unittest.TestCase):
    def test_ordered_two_channels_duplicates_onsite_direction_and_original_pair_guards(self):
        from . import projection as P
        ordinary=[{'i':1,'j':0,'value':-0.0,'onsite':False},{'i':1,'j':0,'value':.25,'channel':'native'}]
        self.assertEqual(P.pairs(ordinary,2),[[1,0],[1,0]])
        self.assertEqual(ordinary[0]['i'],1);self.assertEqual(ordinary[1]['channel'],'native')
        with self.assertRaises(ValueError):P.pairs([{'i':True,'j':0,'value':1.}],2)
        with self.assertRaises(ValueError):P.nullable([None],[True])
        self.assertTrue(np.isnan(P.nullable([None],[False])[0]))
        from workflows.data_v1_final.export.family_export_day_v1.test_boundaries import compact
        from . import configuration as G
        f={'field_id':3,'field_key':'P.pm7_ENPART.r67.total','registry_id':67,'task':'pm7_ENPART','group':'P',
          'source_path':'values.enpart_pairs_eV','component':'total','level':'sparse_atom_pair'}
        records=[{'i':1,'j':0,'J_K_EE_EN_NN_C_total':[1.,2.,3.,4.,5.,6.,-0.0],'onsite':False},
          {'i':1,'j':0,'J_K_EE_EN_NN_C_total':[1.,2.,3.,4.,5.,6.,.25],'channel':'original'}]
        raw={'total_atoms':2,'values':[{'registry_id':67,'kind':8,'text':json.dumps(records)}]}
        entry={'field':f,'field_id':3,'field_key':f['field_key'],'values_float64':[-0.0,.25],'atom_indices':[None,None]}
        spec={'input_kind':'ORIGINAL_REGISTRY_CELL_PARQUET','projection_adapter':'ORIGINAL_COMPONENT_READER_EXPLICIT_PAIR_AND_NULL_IO_V1',
          'components':{f['field_key']:G.component_selector(f,{'fields':{f['field_key']:{}}})}}
        projected,_,annotation=P.prepare([entry],compact(3),spec,raw,2)
        self.assertEqual(projected['__native_pairs_3'].tolist(),[[1,0],[1,0]])
        self.assertTrue(np.signbit(projected['__native_field_3'][0]))
        retained=source_payload=bytes.fromhex(annotation['original_native_cells_binary_json']['67'])
        self.assertEqual(P.K.binary_json_loads(retained),records)
        key='P.pm7_B.r73.value';t={'target_id':'r73','wire_kind':'SOURCE_ORDERED_RECORDS_V1','family':'bonding','geometry_source':'pm7','members':[{'field_key':key,'registry_id':73}]}
        names={k:k for k in ('atom_i','basis_i','atom_j','basis_j','value','onsite')};spec={'components':{key:{'value':{'column':'entries'},'compact':{'field_id':3},'record_index_base':0,'record_fields':names,'null_value_policy':'EXPLICIT_NULL_TRANSPORT'}}}
        records=[{'atom_i':0,'basis_i':'S','atom_j':0,'basis_j':'P','value':.10000000000000003,'onsite':True},
          {'atom_i':0,'basis_i':'P','atom_j':0,'basis_j':'S','value':-0.0},
          {'atom_i':1,'basis_i':'DEL','atom_j':0,'basis_j':'DELL','value':.25},
          {'atom_i':1,'basis_i':'DEL','atom_j':0,'basis_j':'DELL','value':.25}]
        notes={};arrays=V.T.r73({'entries':records},spec,t,2,lambda _:compact(3),notes);rows=V.ordered_entries(arrays,'r73',2)
        self.assertEqual([(r['src_channel'],r['dst_channel']) for r in rows],[('S','P'),('P','S'),('DEL','DELL'),('DEL','DELL')])
        self.assertEqual([r['entry_ordinal'] for r in rows],list(range(4)));self.assertEqual([r['onsite'] for r in rows],[True,True,False,False]);self.assertIsNone(rows[1]['source_onsite'])
        self.assertEqual(rows[2]['direction'],rows[3]['direction']);self.assertEqual(np.signbit(rows[1]['value']),True)
        # Ordinary no-self/no-duplicate semantics remain the original object.
        validate=V.L['wire_v1.mapping'].validate_pairs
        with self.assertRaises(ValueError):validate(np.asarray([[0,0]],dtype='<i4'),2,{'allow_self':False,'directed':True})
        with self.assertRaises(ValueError):validate(np.asarray([[0,1],[0,1]],dtype='<i4'),2,{'allow_self':False,'directed':True})
        encoded=V.CODEC.encode_record({'synthetic':True},arrays);_,trained=V.CODEC.decode_record(encoded);V.original_cast_compare(arrays,trained)
        recovered=V.ordered_entries(trained,'r73',2);self.assertEqual([(r['direction'],r['entry_ordinal']) for r in rows],[(r['direction'],r['entry_ordinal']) for r in recovered])
        batch=V.batch_ordered([(2,recovered),(3,recovered)]);restored=V.unbatch_ordered(batch)
        self.assertEqual([r['src_atom'] for r in batch['entries'][4:]],[r['src_atom']+2 for r in recovered])
        self.assertEqual(restored,[recovered,recovered]);self.assertEqual(len(batch['entries']),8)
    def test_permanent_F64_SQLite_then_original_one_F32_codec_and_readback(self):
        from . import io as I
        plan={'node':'compute-0-8','data_references':[],'whole_output_cap_bytes':32<<30}
        request={'node':'compute-0-8','cpus':16,'wall_seconds':86400,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
          'data_references':[],'estimated_peak_output_bytes':32<<30}
        I.resource_admission(request,plan)
        for key,value in (('node','compute-0-20'),('node','compute-0-7'),('cpus',15),('cpus',16.),('wall_seconds',86399),('memory_policy','EXPLICIT_MEM')):
            with self.assertRaises(ValueError):I.resource_admission(dict(request,**{key:value}),plan)
        with self.assertRaises(ValueError):I.resource_admission(request,dict(plan,node='compute-0-9'))
        self.assertIs(I.B.Budget,I.General.I.Budget);self.assertEqual(I.Budget.__bases__,(I.B.Budget,))
        self.assertIs(I.CensusContext.record_census,I.NativeCensus.ResourceBudget.record_census)
        self.assertIs(I.require,I.B.require)
        calls=[];events=[]
        def transient(path):
            calls.append(path)
            if len(calls)<3:raise FileNotFoundError(2,'synthetic SQLite journal race',str(path/'transient-journal'))
            return 321
        synthetic_root=pathlib.Path('/synthetic/current_parent')
        self.assertEqual(I.NativeCensus.retry_whole_census(transient,synthetic_root,events.append),321)
        self.assertEqual(len(calls),3);self.assertEqual([e['status'] for e in events],
          ['WHOLE_ORIGINAL_CENSUS_FILE_NOT_FOUND','WHOLE_ORIGINAL_CENSUS_FILE_NOT_FOUND','WHOLE_ORIGINAL_CENSUS_SUCCEEDED'])
        self.assertTrue(all(e.get('missing_bytes_assumed_zero')is False for e in events[:2]))
        calls.clear();events.clear()
        def persistent(path):
            calls.append(path);raise FileNotFoundError(2,'synthetic persistent absence',str(path/'missing'))
        with self.assertRaises(FileNotFoundError):I.NativeCensus.retry_whole_census(persistent,synthetic_root,events.append)
        self.assertEqual(len(calls),3);self.assertEqual(len(events),3)
        calls.clear();events.clear()
        def invalid(path):
            calls.append(path);raise ValueError('OUTPUT_OWNER_OR_TYPE')
        with self.assertRaises(ValueError):I.NativeCensus.retry_whole_census(invalid,synthetic_root,events.append)
        self.assertEqual(len(calls),1);self.assertEqual(events,[])
        def failed_record(event):raise OSError('synthetic resource evidence write failure')
        calls.clear()
        with self.assertRaises(OSError):I.NativeCensus.retry_whole_census(persistent,synthetic_root,failed_record)
        self.assertEqual(len(calls),1)
        for original in (I.B.save,I.B.write_text,I.B.Budget.__init__,I.B.Budget._observe,I.B.Budget.check,I.B.Budget.record_quota_event):
            private=I.private_io_function(original,transient)
            self.assertIs(private.__code__,original.__code__);self.assertEqual(private.__defaults__,original.__defaults__)
            self.assertIs(private.__globals__['unique_bytes'],transient)
            self.assertIsNot(private.__globals__,original.__globals__)
        oldroot=C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_pilot_day_v1/synthetic_original'
        newroot=oldroot.parent/'synthetic_resume';parts=oldroot/'typed_coverage'
        reference=lambda p:{'path':str(p),'bytes':1,'sha256':'d'*64}
        resumed={'schema':'ROOT_REVIEWED_NATIVE55K_TERMINAL_STAGE_RESUME_V2',
          'status':'APPROVED_READONLY_COMPLETE_STAGES_NOT_OLD_D4_COMPLETE','reviewer':'root',
          'old_full_D4_complete':False,'new_parent_full_stage_revalidation_required':True,
          'original_output_root':str(oldroot),'deferred_stage_locators':{'coverage_manifest':str(parts/'manifest.json')}}
        origin={'output_directory':str(oldroot)};roots=[str(newroot),str(oldroot)]
        coverage={'original_parts_output_root':str(parts),'original_coverage_reference':reference(parts/'manifest.json'),
          'parts_catalog':reference(newroot/'typed_coverage/numeric_catalog.sqlite'),
          'current_parent_typed_origin_reference':reference(parts/'current_parent_typed_origin.json'),
          'original_actual_parent_job_id':'9900001','new_current_parent_technical_adoption_job_id':'9900002','job_id':'9900002'}
        self.assertEqual(I.resumed_parts_root(coverage,newroot,roots,resumed,origin,'9900001','9900002'),str(parts))
        for changed in (dict(coverage,original_parts_output_root=str(newroot/'typed_coverage')),
          dict(coverage,current_parent_typed_origin_reference=reference(newroot/'typed_coverage/origin.json')),
          dict(coverage,parts_catalog=reference(parts/'numeric_catalog.sqlite')),
          dict(coverage,original_actual_parent_job_id='9900003')):
            with self.assertRaises(ValueError):I.resumed_parts_root(changed,newroot,roots,resumed,origin,'9900001','9900002')
        for wrong_roots in ([str(newroot)],[str(newroot),str(oldroot.parent)],[str(newroot),str(parts)]):
            with self.assertRaises(ValueError):I.resumed_parts_root(coverage,newroot,wrong_roots,resumed,origin,'9900001','9900002')
        with self.assertRaises(ValueError):I.resumed_parts_root(coverage,newroot,roots,dict(resumed,old_full_D4_complete=True),origin,'9900001','9900002')
        with tempfile.TemporaryDirectory(prefix='source3_f64_',dir=WORKSPACE) as directory:
            values=np.asarray([.10000000000000003,-0.,np.nan],dtype='<f8');mask=np.asarray([1,1,0],dtype='|u1');arrays={'values/x':values,'valid/x':mask,'reason/x':np.asarray([0,0,2],dtype='<u2')}
            side=W.Sidecar(pathlib.Path(directory)/'authority.sqlite');m={'export_record_id':'synthetic_g','molecule_id':'synthetic_mid'};loc=side.put(m,arrays);side.commit();closed=side.finish()
            db=W.I.connect(closed['reference']['path'],True)
            try:raw=db.execute('SELECT payload,sha FROM authority WHERE rid=?',('synthetic_g',)).fetchone();restored=V.S.unpack(raw[0])
            finally:db.close()
            self.assertEqual(restored['values/x'].tobytes(),values.tobytes());self.assertEqual(raw[1],loc['payload_sha256'])
            _,wire=V.CODEC.decode_record(V.CODEC.encode_record(m,arrays));V.original_cast_compare(arrays,wire)
            self.assertEqual(wire['values/x'].dtype.str,'<f4');self.assertNotEqual(wire['values/x'].astype('<f8')[0],values[0])
            self.assertEqual(restored['values/x'][0],values[0]);self.assertEqual(wire['valid/x'].tobytes(),mask.tobytes())
            self.assertTrue(np.signbit(wire['values/x'][1]));self.assertTrue(np.isnan(wire['values/x'][2]))
    def test_partial_tensor_scale_policy_geometry_and_three_base_orders(self):
        from . import source,projection as P,configuration as G
        from . import frame_mapping as M
        policy_ref={'path':'/synthetic/native30_source_policy.json','bytes':1,'sha256':'a'*64}
        frame={'verification':M.ASSUMPTION,'independent_coordinate_check_status':'UNKNOWN',
          'source_convention_policy_reference':policy_ref,
          'source_evidence_references':[{'path':'/synthetic/actual_source.py','bytes':1,'sha256':'b'*64}]}
        before_frame=copy.deepcopy(frame);M.frame_allowed(frame,policy_ref);self.assertEqual(frame,before_frame)
        for changes in ({'verification':'UNKNOWN'},{'independent_coordinate_check_status':'VERIFIED'},
          {'source_convention_policy_reference':dict(policy_ref,sha256='c'*64)},{'source_evidence_references':[]}):
            with self.assertRaises(ValueError):M.frame_allowed(dict(frame,**changes),policy_ref)
        self.assertEqual(frame['independent_coordinate_check_status'],'UNKNOWN')
        self.assertIs(M.T,V.T);self.assertIs(M.T.WIRE,V.L['wire_v1.mapping'])
        # A real frozen Source policy is read here, never a scientific body or
        # a mocked policy. Only this exact disabled scalar gets the unit seam.
        mr={'field_id':7,'field_key':'D20.MolMR','registry_id':None,'component':'value','group':'D','task':'D20',
          'level':'molecule','source_path':'MolMR','unit':M.MOLMR_UNIT,'source_unit':M.MOLMR_UNIT,
          'status':'enabled','family_v1_final':'size','reference_frame':None}
        definition={'unit':M.MOLMR_UNIT,'unit_status':M.UNKNOWN_UNIT,'physical_policy_status':'DISABLED_UNIT_UNSPECIFIED',
          'numeric_transform':'IDENTITY_NATIVE_STORED_VALUES','reference_frame':None}
        self.assertTrue(M.molmr_unknown(mr,definition))
        for key,value in (('field_id',8),('field_id',7.),('field_key','D20.Other'),('source_unit','guessed unit'),('task','D3')):
            self.assertFalse(M.molmr_unknown(dict(mr,**{key:value}),definition))
        self.assertFalse(M.molmr_unknown(mr,dict(definition,physical_policy_status='ACTUAL_TARGET_CONDITION_SOURCE_ENABLED')))
        self.assertFalse(M.molmr_unknown(mr,dict(definition,unit_status='VERIFIED')))
        mr['bounded_physical_definition']=definition;actual_source_policy=C.Q.pin(M.POLICY)
        registry={'status':'FROZEN_SYNTHETIC_NATIVE_PILOT','fields':[mr],
          'native30_policy_reference':actual_source_policy,'bounded_order_capability':C.NATIVE_MODE}
        mt={'target_id':'synthetic_MolMR','condition':'D20','geometry_source':'pm7','group':'D','level':'molecule',
          'kind':'scalar','unit':M.MOLMR_UNIT,'unit_status':M.UNKNOWN_UNIT,'family':'size',
          'physical_loss_status':'DISABLED_UNIT_UNSPECIFIED','members':[{'field_key':'D20.MolMR','registry_id':None,
            'source_path':'MolMR','component':'value'}]}
        mapping={'status':'FROZEN','native30_policy_reference':actual_source_policy,
          'bounded_order_capability':C.NATIVE_MODE,'physical_targets':[mt]}
        compiled=M.compile_targets(registry,mapping)
        self.assertEqual(compiled['physical_targets']['synthetic_MolMR']['unit_status'],M.UNKNOWN_UNIT)
        self.assertEqual(compiled['disabled_unit_source_fields'],['D20.MolMR']);self.assertEqual(mr['unit'],M.MOLMR_UNIT)
        with self.assertRaises(ValueError):M.T.compile_targets(registry,mapping,require_final=True)
        with self.assertRaises(ValueError):M.compile_targets(dict(registry,bounded_order_capability=C.FULL_MODE),mapping)
        with self.assertRaises(ValueError):M.compile_targets(registry,dict(mapping,physical_targets=[dict(mt,physical_loss_status='ENABLED')]))
        self.assertEqual(len(source.B.TASKS),14)
        for name,code in source.B.TASKS.items():self.assertEqual(source.task_name(code),name)
        t={'target_id':'Q','kind':'symmetric_tensor','component_order':['xx','xy','yy','xz','yz','zz']}
        arrays={'values/Q':np.asarray([1.,2.,3.,4.,5.,6.],dtype='<f8'),'valid/Q':np.asarray([1,1,1,1,1,0],dtype='|u1')};before=arrays['valid/Q'].copy()
        policy={'scale_status':'ACTUAL_TRAIN_POPULATION_SHA_BOUND','scale':2.,'scale_reference':{'actual':'synthetic'},'scale_population_reference':{'actual':'synthetic'},'series_key':'physical/674/xtb_singlepoint/frobenius_norm','physical_policy_status':'ACTUAL_TARGET_CONDITION_SOURCE_ENABLED','actual_task_charge':0}
        partial=V.tensor_eligibility(t,arrays,'g',['g']*6,policy);self.assertEqual(partial['status'],'LOSS_DISABLED_INCOMPLETE_ORIGINAL_SIX');self.assertFalse(partial['eligible'])
        self.assertTrue(np.array_equal(arrays['valid/Q'],before));arrays['valid/Q'][-1]=1
        enabled=V.tensor_eligibility(t,arrays,'g',['g']*6,policy);self.assertTrue(enabled['eligible']);self.assertEqual(V.tensor_loss(arrays['values/Q'],arrays['values/Q'],enabled),0.)
        for scale in (None,0.,float('nan')):
            disabled=V.tensor_eligibility(t,arrays,'g',['g']*6,dict(policy,scale=scale));self.assertEqual(disabled['status'],V.DISABLED);self.assertNotIn('scale',disabled)
        physical=V.tensor_eligibility(t,arrays,'g',['g']*6,dict(policy,physical_policy_status='DISABLED_PENDING_ACTUAL_TARGET_REVIEW'));self.assertFalse(physical['eligible']);self.assertEqual(physical['actual_task_charge'],0)
        self.assertFalse(V.tensor_eligibility(t,arrays,'g',['g']*5+['other'],policy)['eligible'])
        ids=['base0','base1'];orders=[{'order_type':k,'rank':i,'geometry_id':g} for k in ('fixed_random','energy','diversity') for i,g in enumerate(ids)];D.order_check(ids,orders)
        with self.assertRaises(ValueError):D.order_check(ids,orders+[{'order_type':'energy','rank':2,'geometry_id':'child'}])
        native_plan={'order_capability':C.NATIVE_MODE};self.assertTrue(C.order_domain(native_plan,C.NATIVE_KEY))
        self.assertEqual(C.capabilities(native_plan)['available_orders'],['fixed_random']);self.assertFalse(C.capabilities(native_plan)['full_three_order'])
        with self.assertRaises(ValueError):C.order_domain(native_plan,'existing_sprime_pilot_general_cpu_day_v1')
        with self.assertRaises(ValueError):C.order_domain({},C.NATIVE_KEY)
        bases=[{'geometry_id':'base0','native_record_id':'original_r0','sprime_conf_idx':None},
          {'geometry_id':'base1','native_record_id':'original_r1','sprime_conf_idx':None}]
        key_to_gid={r['native_record_id']:r['geometry_id'] for r in bases}
        def no_distance(*args):raise AssertionError('SOURCE_METHOD_MUST_NOT_RUN_RMSD')
        expected=D.NativeOrders.geometry_orders([{'conformer_id':k,'energy':None} for k in key_to_gid],no_distance,'synthetic_mid','pm7')['fixed_random']
        fixed=[{'order_type':'fixed_random','rank':i,'geometry_id':key_to_gid[k]} for i,k in enumerate(expected)]
        D.native_order_check('synthetic_mid','pm7',bases,fixed)
        for invalid in ([dict(r,order_type='energy') for r in fixed],fixed+[fixed[0]],
          [dict(fixed[0],geometry_id='foreign_child'),fixed[1]],[dict(fixed[0],rank=True),fixed[1]],
          [dict(fixed[0],geometry_id=fixed[1]['geometry_id']),dict(fixed[1],geometry_id=fixed[0]['geometry_id'])]):
            with self.assertRaises(ValueError):D.native_order_check('synthetic_mid','pm7',bases,invalid)
        # The actual original decoder sees a whole NULL before any tensor index.
        members=[];entries=[];components={};order=['xx','xy','yy','xz','yz','zz']
        for fid,component in enumerate(order):
            key='P.xtb_singlepoint.r674.'+component
            f={'field_id':fid,'field_key':key,'registry_id':674,'task':'xtb_singlepoint','group':'P',
              'source_path':'values.molecular_quadrupole_traceless_au','component':component,'level':'molecule_tensor'}
            entries.append({'field':f,'field_id':fid,'field_key':key,'values_float64':[],'atom_indices':[]})
            members.append({'field_key':key,'registry_id':674,'component':component})
            components[key]={'native_projection':'ORIGINAL_TASK_COMPONENTS_V1','value':{'column':'__native_field_'+str(fid)},
              'compact':{'field_id':fid},'shape':[],'reshape':True,'null_value_policy':'masked_nan'}
        bits=(63).to_bytes(19,'little');zero=bytes(19)
        mask={'record_ordinal':1,'task_code':1,'in_scope_fields':bits,'source_valid_fields':zero,'valid_fields':zero,
          'all_leaves_valid_fields':zero,'newly_masked_fields':zero,'source_reason_groups':[{'code':2,'fields':bits}],
          'new_reason_groups':[],'review_groups':[],'leaf_exceptions':[]}
        tr={'input_kind':'ORIGINAL_REGISTRY_CELL_PARQUET','projection_adapter':'ORIGINAL_COMPONENT_READER_EXPLICIT_PAIR_AND_NULL_IO_V1','components':components}
        raw={'total_atoms':2,'values':[{'registry_id':674,'kind':0}]}
        target={'target_id':'nullQ','members':members,'kind':'symmetric_tensor','level':'molecule','storage':'symmetric6'}
        typed={'compact_mask_json':source.K.binary_json_dumps(mask)}
        arrays,note=P.projected_target(entries,typed,tr,raw,2,target)
        self.assertEqual(arrays['valid/nullQ'].tolist(),[0]*6);self.assertTrue(np.all(np.isnan(arrays['values/nullQ'])))
        self.assertEqual(len(note['_source_null_fields']),6)
        bad=dict(mask,valid_fields=bits)
        with self.assertRaises(ValueError):P.prepare(entries,bad,tr,raw,2)
        # Native target IDs are opaque deterministic identities, not ordinal heads.
        f=entries[0]['field'];a=G.target_identity([f],'ordinary');b=G.target_identity([f],'ordinary')
        self.assertEqual(a,b);self.assertNotEqual(a,G.target_identity([f],'other_condition'))
