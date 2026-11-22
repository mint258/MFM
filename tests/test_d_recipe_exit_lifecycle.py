from tools.d_recipe import exit_lifecycle as m
import dataclasses,os,signal,subprocess,sys,time,unittest
SCOPE=None
if sys.platform.startswith('linux') and os.environ.get('SLURM_JOB_ID'):
 try:SCOPE=m.slurm_scope(os.environ['SLURM_JOB_ID'])
 except RuntimeError:pass
CMD=lambda code:[sys.executable,'-I','-S','-B','-c',code]
QUIET=lambda event:None
@unittest.skipIf(SCOPE is None,'Live ownership tests require an actual Linux Slurm step')
class ExitLifecycleTests(unittest.TestCase):
 def tearDown(self):
  self.assertEqual(m.children(os.getpid()),set(),"worker/adopted child not reaped")
 def test_minimum_real_cleanup_reservation(self):
  with self.assertRaises(ValueError):m.cleanup_seconds(179)
  self.assertEqual(m.cleanup_seconds(180),180)
 def test_management_uid_is_not_a_userworker(self):
  rec=m.Identity(100,20,(0,1278,0,1278),SCOPE,'D')
  self.assertFalse(m.owned_scope(rec,1278,SCOPE))
 def test_changed_start_ticks_never_signal(self):
  p=subprocess.Popen(CMD('import time;time.sleep(3)'))
  try:
   rec=m.identity(p.pid)
   wrong=dataclasses.replace(rec,start_ticks=rec.start_ticks+1)
   self.assertFalse(m.signal_owned(wrong,signal.SIGTERM,uid=os.getuid(),scope=SCOPE))
   self.assertIsNone(p.poll())
   self.assertTrue(m.signal_owned(rec,signal.SIGTERM,uid=os.getuid(),scope=SCOPE))
  finally:p.wait(timeout=5)
 def test_normal_nonzero_exit_is_preserved(self):
  self.assertEqual(m.supervise(CMD('raise SystemExit(7)'),end_epoch=None,scope=SCOPE,report=QUIET,poll_seconds=.01),7)
 def test_deadline_stops_at_reserved_window_and_reaps(self):
  self.assertEqual(m.supervise(CMD('import time;time.sleep(5)'),end_epoch=time.time()+180.05,scope=SCOPE,grace_seconds=180,report=QUIET,poll_seconds=.01),75)
 def test_no_work_starts_inside_cleanup_window(self):
  with self.assertRaises(RuntimeError):
   m.supervise(CMD('raise RuntimeError("must not start")'),end_epoch=time.time()+179,scope=SCOPE,grace_seconds=180,report=QUIET)
 def test_orphan_is_adopted_and_cleaned_on_normal_exit(self):
  code='import os,time\np=os.fork()\nif p==0:time.sleep(5)\nelse:os._exit(0)'
  self.assertEqual(m.supervise(CMD(code),end_epoch=None,scope=SCOPE,report=QUIET,poll_seconds=.01),0)
 def test_stopped_child_consumes_term_then_is_reaped(self):
  code='import os,signal,time\nos.kill(os.getpid(),signal.SIGSTOP)\ntime.sleep(5)'
  self.assertEqual(m.supervise(CMD(code),end_epoch=time.time()+180.1,scope=SCOPE,grace_seconds=180,report=QUIET,poll_seconds=.01),75)
 def test_callback_exception_still_reaps_owned_tree(self):
  def fail():raise ValueError('request publication failed')
  with self.assertRaisesRegex(ValueError,'request publication failed'):
   m.supervise(CMD('import time;time.sleep(5)'),end_epoch=time.time()+180.05,scope=SCOPE,grace_seconds=180,request_stop=fail,report=QUIET,poll_seconds=.01)
 def test_usr1_requests_a_clean_noncompletion_exit(self):
  code='import os,signal,time\nos.kill(os.getppid(),signal.SIGUSR1)\ntime.sleep(5)'
  self.assertEqual(m.supervise(CMD(code),end_epoch=None,scope=SCOPE,report=QUIET,poll_seconds=.01),75)

if __name__=='__main__':unittest.main()

