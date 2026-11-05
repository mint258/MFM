"""Three new synthetic controls; no scheduler, source data or science calls."""
import ast,inspect,textwrap,unittest
from unittest import mock
from . import controller as N
from . import recovery as R
from .recovery import complete


class RecoveryBoundaries(unittest.TestCase):
    def test_frozen_command_account_submission_capacity_and_transition_methods_are_same_objects(self):
        for name in ('event','command','sacct','account','registration','persist_terminal_costs','owned_pending',
                     'transition','_transition_after_resource_gate','snapshot','run'):
            self.assertIs(getattr(N.Controller,name),getattr(N.V.Controller,name),name)
        self.assertIs(N.C,N.V.C);self.assertIs(N.CG,N.V.CG)
        plain={key:{'synthetic':key} for key in R.FIELDS}
        historical=dict(plain,batch_id='batch-00001',stage='prepare')
        with mock.patch.object(R,'exact',return_value={}):
            self.assertEqual(R.registration(plain),plain)
            self.assertEqual(R.registration(historical,'batch-00001','prepare'),historical)
            for record,bid,stage in ((historical,None,None),(historical,'batch-00002','prepare'),
                                     (historical,'batch-00001','run'),(dict(plain,batch_id='batch-00001'),'batch-00001','prepare')):
                with self.assertRaises(ValueError):R.registration(record,bid,stage)

    def test_discover_has_only_inverse_proven_actual_plan_selector_delta(self):
        old=inspect.getsource(N.V.Controller.discover);new=inspect.getsource(N.Controller.discover)
        needle="report['plan']==self.report_plan(bid)"
        self.assertEqual(new.count(needle),1)
        inverse=new.replace(needle,"report['plan']==PLAN")
        self.assertEqual(inverse,old)
        self.assertEqual(ast.dump(ast.parse(textwrap.dedent(inverse)),include_attributes=False),
                         ast.dump(ast.parse(textwrap.dedent(old)),include_attributes=False))
        owner=object.__new__(N.Controller);owner.recovery=type('R',(),{'plan_reference':{'synthetic':'new96'}})()
        self.assertEqual(owner.report_plan('batch-00096'),{'synthetic':'new96'})
        for bid in ('batch-00001','batch-00095','batch-00097','batch-00179'):
            self.assertEqual(owner.report_plan(bid),N.PLAN)

    def test_no_old_zero_packet_unstarted_or_unknown_report_can_be_adopted_as_new_complete96(self):
        plan={'path':'synthetic_plan'};prepared={'path':'synthetic_prepared'}
        good={'schema':'SPRIME_FORMAL_CPU_CLOSED_BATCH_V3','status':'ACTUAL_TERMINAL_BATCH_CLASSIFIED',
          'batch_id':'batch-00096','actual_parent_job_id':'999','plan':plan,'prepared':prepared,
          'valid_packets':500,'consumed_outcomes':500,'execution_unresolved':0,'unstarted_count':0,'errors':[],
          'consumed_elsewhere':[]}
        complete(good,'batch-00096','999',plan,prepared)
        for field,value in [('valid_packets',0),('unstarted_count',500),('execution_unresolved',1),
                            ('errors',['unknown']),('plan',{'path':'wrong'}),('actual_parent_job_id','4521922')]:
            with self.assertRaises(ValueError):complete(dict(good,**{field:value}),'batch-00096','999',plan,prepared)


if __name__=='__main__':unittest.main()
