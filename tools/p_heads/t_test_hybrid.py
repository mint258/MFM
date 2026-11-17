"""Only T thin-adapter routing/ledger/affinity/lock ownership tests; no training."""
import fcntl,json,os,pathlib,tempfile,types,unittest
from unittest import mock
import t_hybrid as h
import t_native as n

class HybridTests(unittest.TestCase):
    def test_prepare_creates_missing_control_parents(self):
        # Real filesystem fixture: its owned control parents do not exist.
        with tempfile.TemporaryDirectory(prefix='T_hybrid_missing_parent_',dir=h.CONTROL) as directory:
            root=pathlib.Path(directory);request=root/'control/request.json';ack=root/'control/ack.json'
            configuration=root/'fixture.json'
            configuration.write_text(json.dumps(dict(run='missing_parent_fixture',stage=2,round=3,
                output=str(root/'training'),handoff_request=str(request),handoff_ack=str(ack))))
            self.assertFalse(request.parent.exists())
            old=(h.ledger.C,h.protocol.C,h.protocol.REPO,h.protocol.requested_cpus,h.protocol.guarded_run)
            try:
                with mock.patch.object(h,'CONTROL',root),mock.patch.object(h,'HYBRID',root/'hybrid'),mock.patch.object(h,'guard') as capacity:
                    task,launch=h.prepare(str(configuration),'compute-0-22','GPU-fixture','python')
                    self.assertTrue(request.parent.is_dir());self.assertTrue(ack.parent.is_dir())
                    self.assertFalse(request.exists());self.assertFalse(ack.exists())
                    # The original writer can now create its atomic .tmp file.
                    h.ledger.write(request,dict(action='fixture_only'))
                    self.assertEqual(json.loads(request.read_text())['action'],'fixture_only')
                    self.assertTrue(task.is_file());self.assertTrue(launch.is_file())
                    self.assertGreaterEqual(capacity.call_count,2)
            finally:
                h.ledger.C,h.protocol.C,h.protocol.REPO,h.protocol.requested_cpus,h.protocol.guarded_run=old
    def test_replace_terminal_standby_only_before_handoff(self):
        # Real owned control/ledger fixture; only Slurm controller replies mocked.
        with tempfile.TemporaryDirectory(prefix='T_hybrid_replace_',dir=h.CONTROL) as directory:
            root=pathlib.Path(directory);control=root/'control';control.mkdir();hybrid=root/'hybrid';hybrid.mkdir()
            config=root/'fixture.json';state=root/'native.json';handoff=root/'handoff.json';taskpath=root/'task.json'
            request=control/'request.json';ack=control/'ack.json';name='replace_fixture';key=name+'_standby'
            config.write_text(json.dumps(dict(run=name,handoff_request=str(request),handoff_ack=str(ack))))
            actual=n.identity(os.getpid());state.write_text(json.dumps(dict(actual,status='RUNNING')))
            taskpath.write_text(json.dumps(dict(node='compute-0-22',configuration=str(config),native_state=str(state),handoff_state=str(handoff),reservation_key=key)))
            baseline=dict(runs={name:dict(standby_job_id=901)},reservations={key:dict(job_id=901,native_run=name,state='SUBMITTED',phase='WAITING_FOR_ALLOCATION')})
            def reset():h.ledger.write(hybrid/'study_execution.json',json.loads(json.dumps(baseline)))
            def book():return json.loads((hybrid/'study_execution.json').read_text())
            terminal=types.SimpleNamespace(returncode=0,stdout='JobId=901 JobState=FAILED',stderr='')
            missing=types.SimpleNamespace(returncode=1,stdout='',stderr='slurm_load_jobs error: Invalid job id specified')
            running=types.SimpleNamespace(returncode=0,stdout='JobId=901 JobState=RUNNING',stderr='')
            unknown=types.SimpleNamespace(returncode=1,stdout='',stderr='Connection refused')
            old=(h.ledger.C,h.protocol.C,h.protocol.REPO,h.protocol.requested_cpus,h.protocol.guarded_run)
            try:
                with mock.patch.object(h,'CONTROL',root),mock.patch.object(h,'HYBRID',hybrid),mock.patch.object(h,'guard'),mock.patch.object(h.subprocess,'check_output',return_value='JobId=902 JobState=PENDING ReqNodeList=compute-0-22'):
                    for observed in (terminal,missing):
                        with self.subTest(allowed=observed.returncode):
                            reset()
                            with mock.patch.object(h.subprocess,'run',return_value=observed):h.register(str(taskpath),902,901)
                            b=book();r=b['reservations'][key]
                            self.assertEqual(r['job_id'],902);self.assertEqual(b['runs'][name]['standby_job_id'],902)
                            self.assertEqual(r['terminal_replacements'][0]['old_job_id'],901)
                            self.assertEqual(r['terminal_replacements'][0]['source_identity'],actual)
                            self.assertFalse(request.exists());self.assertFalse(ack.exists());self.assertFalse(handoff.exists())
                    for observed,error in ((running,ValueError),(unknown,RuntimeError)):
                        with self.subTest(rejected=observed.stdout or observed.stderr):
                            reset()
                            with mock.patch.object(h.subprocess,'run',return_value=observed),self.assertRaises(error):h.register(str(taskpath),902,901)
                            self.assertEqual(book(),baseline)
                    reset()
                    with mock.patch.object(h.subprocess,'run',side_effect=h.subprocess.TimeoutExpired('scontrol',15)),self.assertRaises(h.subprocess.TimeoutExpired):h.register(str(taskpath),902,901)
                    self.assertEqual(book(),baseline)
                    for started in (request,ack,handoff):
                        with self.subTest(already_started=started.name):
                            reset();started.write_text('{}')
                            with mock.patch.object(h.subprocess,'run',return_value=terminal),self.assertRaises(ValueError):h.register(str(taskpath),902,901)
                            self.assertEqual(book(),baseline);started.unlink()
            finally:
                h.ledger.C,h.protocol.C,h.protocol.REPO,h.protocol.requested_cpus,h.protocol.guarded_run=old
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