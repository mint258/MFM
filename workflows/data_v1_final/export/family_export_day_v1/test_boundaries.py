"""Three real CPU synthetic boundaries, including Arrow->MFM3->LMDB readback."""
from __future__ import annotations
import copy,json,pathlib,sqlite3,tempfile,unittest
import numpy as np
from . import contract as C,project as P,transport as T,store as STORE,verify as V
L=C.legacy();MASK=L['pipeline_v1.masks']


def compact(fid,valid=True):
    bits=(1<<fid).to_bytes(19,'little');zero=bytes(19)
    return {'record_ordinal':1,'task_code':1,'in_scope_fields':bits,'source_valid_fields':bits if valid else zero,
        'valid_fields':bits if valid else zero,'all_leaves_valid_fields':bits if valid else zero,'newly_masked_fields':zero,
        'source_reason_groups':[] if valid else [{'code':2,'fields':bits}],'new_reason_groups':[],'review_groups':[],'leaf_exceptions':[]}


class Boundaries(unittest.TestCase):
    def test_real_arrow_r73_ordered_native_transport_and_LMDB_reopen(self):
        import pyarrow as pa,pyarrow.parquet as pq
        from wire_v1.tests import metadata
        key='r73.ordered';target={'target_id':'r73','wire_kind':'SOURCE_ORDERED_RECORDS_V1','family':'bonding','geometry_source':'pm7','members':[{'field_key':key,'registry_id':73}]}
        fields={k:k for k in ('atom_i','basis_i','atom_j','basis_j','value','channel','onsite')}
        selector={'value':{'column':'raw','decode':'json'},'compact':{'field_id':3},'record_index_base':0,'record_fields':fields,'null_value_policy':'EXPLICIT_NULL_TRANSPORT'}
        spec={'components':{key:selector}};records=[{'atom_i':0,'basis_i':'S','atom_j':0,'basis_j':'P_x','value':.1,'channel':'sigma','onsite':True},
            {'atom_i':0,'basis_i':'S','atom_j':0,'basis_j':'P_x','value':-0.0}]
        with tempfile.TemporaryDirectory(prefix='family_source_boundary_') as directory:
            root=pathlib.Path(directory);pq.write_table(pa.Table.from_pylist([{'raw':json.dumps(records)}]),root/'source.parquet')
            row=pq.read_table(root/'source.parquet').to_pylist()[0];notes={};arrays=T.r73(row,spec,target,2,lambda _:compact(3),notes)
            schema={'kind':'labels','family':'bonding','mask_encoding':'field-set+sparse-leaf-v1','compiled':{'physical_targets':{}},'ordered_record_targets':{'r73':target}}
            meta=dict(metadata(),reason_granularity=notes,source_precision={'r73':'ORIGINAL_SYNTHETIC_f64'})
            with STORE.Writer(root/'store',schema,map_bytes=16<<20) as writer:writer.write_batch([(meta,arrays)])
            with STORE.Reader(root/'store') as reader:
                header,actual=reader.get('g0');V.compare(arrays,actual);self.assertEqual(reader.records_for_molecule('m0'),['g0'])
                self.assertEqual(actual['transport/r73/ordinal'].tolist(),[0,1]);self.assertEqual(actual['transport/r73/onsite_present'].tolist(),[1,0])
                self.assertEqual(T.decode_strings(actual['transport/r73/basis_j_utf8'],actual['transport/r73/basis_j_offsets']),['P_x','P_x'])
            # Exercise the real source-staging locator query and assembly,
            # not only direct low-level Writer. This catches the R1 missing
            # source_index/RG/row SELECT columns before any scientific DATA.
            from . import writer as W
            db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
            db.executescript('CREATE TABLE selected_geometry(geometry_id TEXT PRIMARY KEY,molecule_id TEXT,geometry_source TEXT,native_record_id TEXT,sprime_conf_idx INTEGER,parent_geometry_id TEXT,view_id TEXT,effective_role TEXT,source_role TEXT);CREATE TABLE shard_members(geometry_id TEXT PRIMARY KEY);CREATE TABLE partition_members(name TEXT,geometry_id TEXT,PRIMARY KEY(name,geometry_id));CREATE TABLE exported(store_name TEXT,geometry_id TEXT,kind TEXT,parts_json TEXT,PRIMARY KEY(store_name,geometry_id));CREATE TABLE pieces('+P.E.PIECES_SCHEMA+');')
            db.execute('INSERT INTO selected_geometry VALUES(?,?,?,?,?,?,?,?,?)',('g0','m0','pm7','native0',None,None,None,'TRAIN','TRAIN'))
            db.execute('INSERT INTO shard_members VALUES(?)',('g0',));db.execute('INSERT INTO partition_members VALUES(?,?)',('locator_store','g0'))
            geom={'atomic_numbers':np.array([6,1],dtype='<i2'),'positions_A':np.array([[0.,0.,0.],[1.1,0.,0.]],dtype='<f8'),
                'native_bond_index':np.array([[0,1],[1,0]],dtype='<i8'),'native_bond_order':np.array([1,1],dtype='<i8')}
            db.execute('INSERT INTO pieces VALUES(?,?,?,?,?,?,?)',('g0','__geometry__',2,12,3,7,P.S.pack(geom,{})));db.commit()
            cfg={'partitions':[{'name':'locator_store','kind':'geometry','geometry_source':'pm7','view_id':None,'map_bytes':16<<20}],
                '_schema_authorities':{'synthetic_boundary_only':True},'_budget_check':lambda:None,'_retire':lambda _:None,
                '_field_claims_reference':{'synthetic':'NOT_AN_ACTUAL_CLAIM_AUTHORITY'},'_actual_parent_job_id':'SYNTHETIC_NOT_SLURM',
                'maximum_output_bytes':64<<20,'actual_shard_target_ids':set()}
            W.export_shard(db,root,{'physical_targets':{},'ordered_record_targets':{}},cfg)
            with STORE.Reader(root/'locator_store') as reader:
                header,actual=reader.get('g0');V.compare(geom,actual)
                self.assertEqual(header['permanent_float64_source_locators'],[{'source_index':12,'row_group':3,'row_number':7,'part':'__geometry__'}])
            db.close()
            raw,offset=T.strings(['S','P']);bad=offset.copy();bad[-1]+=1
            with self.assertRaises(ValueError):T.decode_strings(raw,bad)
            with self.assertRaises(ValueError):T.exact_int64([.5],(1,))
            null={};empty={};T.r73({'raw':'null'},spec,target,2,lambda _:compact(3,False),null);T.r73({'raw':'[]'},spec,target,2,lambda _:compact(3),empty)
            self.assertIsNone(null['r73']['source_record_count']);self.assertEqual(empty['r73']['source_record_count'],0)

    def test_r674_one_tensor_partial_masks_and_raw_native_bond_order(self):
        from wire_v1.tests import metadata,fixture_mapping
        registry,mapping,_=fixture_mapping('symmetric_tensor',name='quad');t=mapping['physical_targets'][0]
        for f in registry['fields']:f['registry_id']=674
        for m in t['members']:m['registry_id']=674
        registry['pprime']={'computed_labels_available':True};pp=copy.deepcopy(t);pp.update(target_id='quad_Pprime',condition='Pprime',geometry_source='uff_sprime')
        mapping['physical_targets'].append(pp)
        compiled=T.compile_targets(registry,mapping);self.assertEqual(set(compiled['physical_targets']),{'quad','quad_Pprime'});target=compiled['physical_targets']['quad'];values={m['field_key']:np.asarray(i+.1,dtype='<f8') for i,m in enumerate(t['members'])}
        tensor=L['wire_v1.mapping'].assemble_target(target,values);mask=np.ones((3,3),dtype='|u1');mask[0,1]=mask[1,0]=0
        arrays={'values/quad':tensor,'valid/quad':mask,'reason/quad':np.where(mask,0,2).astype('<u2')}
        schema=T.family_schema(compiled,'multipole','pm7',{'quad'})
        with tempfile.TemporaryDirectory(prefix='family_tensor_boundary_') as directory:
            root=pathlib.Path(directory)
            with STORE.Writer(root/'tensor',schema,map_bytes=16<<20) as writer:writer.write_batch([(metadata(),arrays)])
            with STORE.Reader(root/'tensor') as reader:
                _,out=reader.get('g0');V.compare(arrays,out);self.assertEqual(set(out),set(arrays));self.assertEqual(out['values/quad'].shape,(3,3))
            geom={'atomic_numbers':np.array([6,1],dtype='<i2'),'positions_A':np.array([[0.,0.,0.],[1.1,0.,0.]],dtype='<f8'),
                'native_bond_index':np.array([[0,1,0],[1,0,1]],dtype='<i8'),'native_bond_order':np.array([1,1,1],dtype='<i8')}
            with STORE.Writer(root/'geometry',{'kind':'geometry'},map_bytes=16<<20) as writer:writer.write_batch([(metadata(),geom)])
            with STORE.Reader(root/'geometry') as reader:_,out=reader.get('g0');V.compare(geom,out);self.assertEqual(out['native_bond_index'].shape,(2,3))

    def test_same_task_fields_bind_distinct_geometry_without_task_fallback(self):
        db=sqlite3.connect(':memory:');P.claim_schema(db)
        cell={'source_path':'/synthetic/source.parquet','source_bytes':100,'source_sha':'a'*64,'physical_row_index':0,
            'record_id':'r0','molecule_id':'m0','group_key':'actual_owner','record_ordinal':7,'task_code':3,'input_bundle_sha':'b'*64,'input_file_sha_json':'{}'}
        P.add_claims(db,cell,[(1,'actual_base','c'*64,{'actual':'base doublehash'}),(2,'actual_child','d'*64,{'actual':'child doublehash'})])
        self.assertEqual(P.mask_claim_for(db,'actual_owner',7,3,1)['geometry_id'],'actual_base')
        self.assertEqual(P.mask_claim_for(db,'actual_owner',7,3,2)['geometry_id'],'actual_child')
        with self.assertRaises(ValueError):P.mask_claim_for(db,'actual_owner',7,3,0)
        with self.assertRaises(ValueError):P.add_claims(db,dict(cell,physical_row_index=1),[(1,'a','e'*64,{}),(1,'b','f'*64,{})])
        db.rollback();db.close()
        parents={'allowed_base':None,'allowed_child':'allowed_base','held_base':None,'new_child':'held_base','cycle_a':'cycle_b','cycle_b':'cycle_a'}
        lookup=lambda gid:(gid in parents,parents.get(gid))
        self.assertEqual(P.assert_diagnostic_lineage([{'geometry_id':'allowed_child','parent_geometry_id':'allowed_base'}],lambda gid:gid=='held_base',lookup),1)
        for gid,parent in [('new_child','held_base'),('held_base',None),('cycle_a','cycle_b'),('missing',None)]:
            with self.subTest(lineage=gid),self.assertRaises(ValueError):P.assert_diagnostic_lineage([{'geometry_id':gid,'parent_geometry_id':parent}],lambda v:v=='held_base',lookup)
        # Pure small-header authority checks. These synthetic dictionaries are
        # not represented as C0/proofs and no Source/DATA locator is opened.
        values=publication_headers();C.assert_publication_links(*values)
        for position,key,value in [(1,'reviewer',None),(1,'stores_catalogue_reference','SUBSTITUTED'),(5,'reviewer',None),(5,'exact_outputs',{})]:
            bad=copy.deepcopy(values);bad[position][key]=value
            with self.subTest(authority=(position,key)),self.assertRaises(ValueError):C.assert_publication_links(*bad)

def publication_headers():
    outputs={key:'SYNTHETIC_'+key for key in ('registry_reference','mapping_reference','normalization_reference','mask_release_reference','size_rho_reference')}
    candidate={'schema':'FINAL_LABEL_RELEASE_CANDIDATE_V1','status':'COMPLETE_EXACT_FINAL_CANDIDATE_REQUIRES_ACTUAL_PARENT_C0_AND_ROOT_SEAL',
        'current_parent_C0_claimed':False,'joint_policy_reference':'SYNTHETIC_JOINT','release_scope':'BOUNDED_D3_50K_TRAIN_5K_ROUTINE_VAL',**outputs}
    parents={'candidate':'SYNTHETIC_CANDIDATE'};inline=dict(candidate,candidate_reference=parents['candidate'])
    receipt={'inline_final_label_candidate':inline,**{key:'SYNTHETIC_'+key for key in ('stores_catalogue_reference','verification_reference','selection_reference','source_release_reference')}}
    before={'schema':'FAMILY_EXPORT_EXTERNAL_SEAL_CANDIDATE_V1','status':'PENDING_INDEPENDENT_ROOT_C0_AND_EXACT_FINAL_LABEL_RELEASE_REVIEW',
        'actual_closure_references':{'synthetic':'NO_ACTUAL_C0'},**receipt,'joint_policy_reference':'SYNTHETIC_JOINT'}
    release={'schema':'ROOT_ACCEPTED_FAMILY_EXPORT_RELEASE_V1','status':'BOUNDED_D3_50K_TRAIN_5K_VAL_FROZEN_NOT_FULL','consumer_release':True,
        'purpose':'pilot55k','training_ready':False,'actual_closure_references':before['actual_closure_references'],
        **{key:receipt[key] for key in ('stores_catalogue_reference','verification_reference','selection_reference','source_release_reference')},
        'final_label_release_reference':'SYNTHETIC_LABEL_RELEASE','joint_policy_reference':'SYNTHETIC_JOINT'}
    review={'schema':'ROOT_FAMILY_EXPORT_PUBLICATION_REVIEW_V1','status':'APPROVED_EXACT_ACTUAL_C0_AND_SAME_OBJECTS','reviewer':'root',
        'stores_catalogue_reference':release['stores_catalogue_reference'],'final_label_release_reference':release['final_label_release_reference']}
    labels={'schema':'ROOT_FINAL_LABEL_RELEASE_V1','status':'BOUNDED_DIAGNOSTIC_P_D_RELEASE_NOT_FULL_V1','final_consumer_release':True,
        'candidate_reference':parents['candidate'],'actual_parent_references':parents,'joint_policy_reference':'SYNTHETIC_JOINT',
        'release_scope':candidate['release_scope'],'training_ready':False,**outputs}
    label_review={'schema':'ROOT_FINAL_LABEL_PUBLICATION_REVIEW_V1','status':'APPROVED_EXACT_ACTUAL_C0_RELEASE','reviewer':'root','exact_outputs':outputs,'joint_policy_reference':'SYNTHETIC_JOINT'}
    label_before={'schema':'FINAL_LABEL_POST_C0_ROOT_REVIEW_CANDIDATE_V1','status':'PENDING_INDEPENDENT_ROOT_FINAL_REVIEW',
        'actual_parent_references':parents,'exact_outputs':outputs}
    return [release,review,before,receipt,labels,label_review,label_before,candidate]