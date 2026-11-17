"""Only T thin-adapter routing/ledger/affinity/lock ownership tests; no training."""
import fcntl,os,pathlib,types,unittest
from unittest import mock
import t_hybrid as h
import t_native as n

class HybridTests(unittest.TestCase):
    def test_protocol_reused_with_isolated_ledger_and15cpus(self):
        old=(h.ledger.C,h.protocol.C,h.protocol.REPO,h.protocol.requested_cpus,h.protocol.guarded_run)
        original_main=h.protocol.main;original_handoff=h.protocol.handoff
        try:
            p=h.bind_protocol()
            self.assertIs(p.main,original_main);self.assertIs(p.handoff,original_handoff)
            self.assertEqual(h.ledger.C,h.CONTROL/'hybrid');self.assertEqual(p.C,h.CONTROL/'hybrid')
            self.assertEqual(p.REPO,h.REPO);self.assertEqual(p.requested_cpus({'workers':14},{'cpu_overhead':2}),15)
        finally:
            h.ledger.C,h.protocol.C,h.protocol.REPO,h.protocol.requested_cpus,h.protocol.guarded_run=old
    def test_takeover_routes_once_to_T_entry_not_recipe_or_evaluation(self):
        launch=dict(command=['python','-B','-u','tools/p_recipe/train.py','--configuration','resumed.json'],execution='Slurm')
        with mock.patch.object(h,'native_run',return_value=0) as runner:
            self.assertEqual(h.guarded_run(launch),0)
            runner.assert_called_once();c=runner.call_args.args[0]
        command=n.training_command(c['python'],c['configuration'])
        self.assertEqual(command[-1],'resumed.json')
        self.assertTrue(command[3].endswith('tools/p_heads/t_train.py'))
        self.assertNotIn('tools/p_recipe/train.py',command)
    def test_native_identity_mask_no_fake_slurm_and_no_outer_GPU_lock(self):
        child=mock.Mock();child.pid=987654;child.poll.return_value=0;child.wait.return_value=0
        bound=dict(pid=child.pid,uid=os.getuid(),start_ticks=321,pgid=child.pid)
        c=dict(node='compute-0-22',run='test_adapter_only',gpu_uuid='GPU-fixture',python='python',
            configuration='fixture.json',state_path='fixture_state.json')
        records=[];popen=[]
        def affinity(pid):return set(range(20 if pid==0 else 15))
        def spawn(*args,**kw):popen.append((args,kw));kw['preexec_fn']();return child
        with mock.patch.object(n,'guard'),mock.patch.object(n,'read',return_value={}),mock.patch.object(n,'write',side_effect=lambda p,v:records.append(dict(v))),mock.patch.object(n.socket,'gethostname',return_value='compute-0-22'),mock.patch.object(n.os,'sched_getaffinity',side_effect=affinity),mock.patch.object(n.os,'sched_setaffinity') as pin,mock.patch.object(n,'identity',return_value=bound),mock.patch.object(n,'wait_own_tree') as tree,mock.patch.object(n.subprocess,'Popen',side_effect=spawn),mock.patch.object(fcntl,'flock',side_effect=AssertionError('Outer GPU flock forbidden')),mock.patch.dict(os.environ,{'SLURM_JOB_ID':'should_be_removed','SLURM_CPUS_PER_TASK':'99'}):
            self.assertEqual(n.run(c),0)
            pin.assert_called_once_with(0,list(range(15)));tree.assert_called_once_with(bound,{})
        self.assertEqual(len(popen),1);env=popen[0][1]['env']
        self.assertFalse(any(k.startswith('SLURM_') for k in env));self.assertEqual(env['CUDA_VISIBLE_DEVICES'],'GPU-fixture')
        self.assertNotIn('job_id',records[0]);self.assertEqual(records[0]['cpu_mask'],list(range(15)))
        self.assertEqual(records[0]['start_ticks'],321);self.assertEqual(records[-1]['exit_code'],0)
        self.assertTrue(records[-1]['worker_tree_exited'])
if __name__=='__main__':unittest.main()