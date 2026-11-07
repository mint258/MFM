"""Three CPU synthetic boundaries. Never initialize or invoke a native engine."""
import copy,hashlib,pathlib,struct,unittest
from . import contract as C,io as I,worker,source_boundary
WORKSPACE=None

class Boundaries(unittest.TestCase):
    def test_precision_scope_cannot_promote_diagnostics_and_owned_scratch_only(self):
        ref=lambda name:{'path':'/synthetic/'+name,'bytes':1,'sha256':hashlib.sha256(name.encode()).hexdigest()}
        plan={'prepared2000_reference':ref('prepared'),'original_protocol_reference':ref('original'),
          'candidate_protocol_reference':ref('candidate'),'node':'compute-0-18','precision_mode':'TIGHTER_ONLY_THREE_FIELDS'}
        review={'original2000_formal_pilot_scope_authorized':True,'maximum_native_invocations':24000,
          'minimum_record_success_rate':.995,'maximum_allocated_core_seconds_per_requested_record':11.7,
          'full_submission_authorized':False,'precision_mode':plan['precision_mode'],
          'allocated_core_hours_overrun_action':'REPORT_AND_CONTINUE_QUALITY_UNCHANGED',
          'WP5_record_cost_overrun_action':'REPORT_AND_HOLD_FULL_NO_SCIENTIFIC_PASS'}
        with self.assertRaises(ValueError):C.precision(plan,review)
        decision={'schema':'USER_AUTHORIZED_PPRIME2000_TIGHTER_PILOT_V1','status':'USER_AUTHORIZED',
          'prepared2000_reference':plan['prepared2000_reference'],'original_protocol_reference':plan['original_protocol_reference'],
          'candidate_protocol_reference':plan['candidate_protocol_reference'],'requested_records':2000,
          'maximum_native_invocations':24000,'timeout_seconds':900,'cpus':16,'maximum_wall_seconds':86400,
          'output_cap_bytes':C.CAP,'only_three_frozen_protocol_differences':True,'other9_tasks_and_quality_thresholds_unchanged':True,
          'automatic_retry_authorized':False,'full_submission_authorized':False,
          'authorization_basis':'EXPLICIT_USER_MESSAGE_FOR_THIS_2000_PILOT','diagnostic15_1200_frame30_authorizations_do_not_apply':True}
        self.assertIs(C.user_decision_fields(decision,plan),decision)
        for change in ({'schema':'USER_AUTHORIZED_STRICT15_V1'},{'requested_records':20},
                       {'prepared2000_reference':ref('different')},{'synthetic_fixture_only':True},
                       {'other9_tasks_and_quality_thresholds_unchanged':False}):
            with self.assertRaises(ValueError):C.user_decision_fields(dict(decision,**change),plan)
        protocol={'timeout_seconds':900,'tasks':[{'name':'synthetic','keywords':'unchanged'}],'scratch_base':'/tmp'}
        actual=copy.deepcopy(protocol);actual['scratch_base']='/tmp/synthetic-owned'
        worker.original_protocol_with_owned_scratch(actual,protocol,pathlib.Path(actual['scratch_base']))
        actual['tasks'][0]['keywords']='different'
        with self.assertRaises(ValueError):worker.original_protocol_with_owned_scratch(actual,protocol,pathlib.Path(actual['scratch_base']))

    def test_original_once_codec_and_exclusive_claim_reopen(self):
        root=pathlib.Path(WORKSPACE)/'synthetic_once';root.mkdir();store=I.Store(root,4<<20)
        ref={'path':'/synthetic/original','bytes':1,'sha256':'1'*64}
        pair={'molecule_id':'syntheticMID','conformer':{'sprime_conf_idx':8},'uff_coordinate_sha256':'2'*64}
        key=C.record_once_key(pair,ref)
        self.assertEqual(key,C.record_once_key(dict(pair,output='different',precision_mode='TIGHTER_ONLY_THREE_FIELDS'),ref))
        changed=copy.deepcopy(pair);changed['conformer']['sprime_conf_idx']=9
        self.assertNotEqual(key,C.record_once_key(changed,ref))
        path=root/(key+'.json');first=I.claim_create(path,{'record_once_key':key,'synthetic_only':True},store)
        self.assertEqual(C.Q.pin(path),first)
        with self.assertRaises(FileExistsError):I.claim_create(path,{'replacement':True},store)
        original={'finite':-0.0,'nonfinite':float('nan'),'none':None,'nested':[1.25]}
        restored=C.O.read_staging(C.O.staging_bytes(original))
        self.assertEqual(struct.pack('<d',original['finite']),struct.pack('<d',restored['finite']))
        self.assertEqual(struct.pack('<d',original['nonfinite']),struct.pack('<d',restored['nonfinite']))
        self.assertIsNone(restored['none'])
        # These are real original function objects, imported without initialize.
        objects=source_boundary.objects()
        self.assertEqual(pathlib.Path(objects['compute_pair'].__code__.co_filename).absolute(),
          C.Q.REPO/'workflows/data_v1_final/pprime/engine_adapter.py')
        # Use the actual old assess object and real boundary accounting fields.
        # No new cost/scientific formula or native mock is supplied.
        result={'runtime':{'job_id':'4242000','node':'compute-0-18'},'completed_records':2000,
          'status':'PPRIME_PILOT_COMPUTE_CLOSED_AWAITING_PARENT_ACCOUNTING','failures':[],
          'all_workers_joined':True,'record_success_rate':1.0}
        account={'JobIDRaw':'4242000','User':'zixiao','NodeList':'compute-0-18','AllocCPUS':'16',
          'ElapsedRaw':'1462','State':'COMPLETED','ExitCode':'0:0'}
        config={'minimum_success_rate':.995,'maximum_allocated_core_seconds_per_conformer':11.7}
        within=objects['assess'](result,[account],config)
        over=objects['assess'](result,[dict(account,ElapsedRaw='1463')],config)
        self.assertTrue(all(C.pilot_gate_state(within).values()))
        self.assertFalse(C.pilot_gate_state(over)['allocated_seconds_within_1_5x_wp5'])
        self.assertFalse(all(C.pilot_gate_state(over).values()))
        with self.assertRaises(ValueError):C.pilot_gate_state({'gates':{'other':True}})

    def test_role_unknown_reservation_and_raw_return_not_durability_claim(self):
        roles=I.Roles()
        for i in range(16):roles.start(str(i))
        self.assertFalse(roles.can_start());before=roles.bound();roles.settle('0',0,False)
        self.assertEqual(roles.bound(),before);self.assertIn('0',roles.unknown)
        with self.assertRaises(ValueError):roles.start('0')
        class Refusal:
            def __call__(self,raw):raise OSError('synthetic durable sink write refused')
        sink=worker.Sink(Refusal(),pathlib.Path(WORKSPACE))
        with self.assertRaises(OSError):sink({'record_id':'synthetic','calc_type':'synthetic','execution_id':'synthetic',
          'status':'FAILED','source_status':'FAILED'})
        self.assertEqual(len(sink.calls),1)
        self.assertIsNone(sink.calls[0]['raw_ref'])
        self.assertTrue(sink.calls[0]['native_return_observed_by_original_raw_sink'])
        # It records an already-returned synthetic packet, never a successful
        # durable raw call, scientific success or permission to retry.
        self.assertNotIn('raw_call_durable',sink.calls[0])
