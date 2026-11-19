"""Deferred statistics run once after GPU completion, including SSH twins."""
from contextlib import contextmanager
import json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/p_recipe'))
import cpu_statistics as cpu
import scheduled_run


class CPUStatisticsTests(unittest.TestCase):
 def fixture(self,directory):
  output=Path(directory);(output/'readout').mkdir()
  c=dict(run='registered_fixture',samples=3000000,output=str(output),statistics_backend='slurm_cpu')
  cpu.write(output/'summary.json',dict(status=cpu.WAITING,samples=3000000,training_and_gpu_readout_seconds=10.))
  cpu.write(output/'readout/predictions.json',dict(run=c['run'],samples=3000000,files={}))
  return c

 def test_finalize_never_repeats_completed_bootstrap_or_probe(self):
  with tempfile.TemporaryDirectory() as directory:
   c=self.fixture(directory);calls=[]
   def original_score(candidate,reference,destination):
    calls.append(candidate)
    result={key:dict(complete=True,bootstrap_samples=1000,bootstrap_defined=1000) for key in ('R1','R3')}
    cpu.write(Path(candidate).parent/'scores.json',result)
   with patch.object(cpu,'admit'),patch.dict(sys.modules,{'evaluate':types.SimpleNamespace(score=original_score)}):
    first=cpu.finalize(c);second=cpu.finalize(c)
   self.assertEqual(len(calls),1)
   self.assertEqual(first['newly_scored_samples'],[3000000])
   self.assertEqual(second['newly_scored_samples'],[])
   self.assertTrue(cpu.read(Path(directory)/'summary.json')['statistics_complete'])

 def test_queue_requires_actual_gpu_success_and_submits_once(self):
  with tempfile.TemporaryDirectory() as directory:
   c=self.fixture(directory);configuration=Path(directory)/'configuration.json';cpu.write(configuration,c)
   record=dict(state='RUNNING',exit_code='0:0');ledger=dict(runs={c['run']:record})
   @contextmanager
   def locked():yield ledger
   with patch.object(cpu,'locked_ledger',locked),patch.object(cpu,'write'),\
        patch.object(cpu,'cpu_destination',return_value='compute-0-10'),\
        patch.object(cpu.subprocess,'check_output',return_value='12345\n') as submit:
    plan=dict(configurations=[str(configuration)])
    self.assertEqual(cpu.queue(plan),[]);submit.assert_not_called()
    record['state']='COMPLETED'
    self.assertEqual(len(cpu.queue(plan)),1)
    self.assertEqual(cpu.queue(plan),[])
    self.assertEqual(submit.call_count,1)
    self.assertIn('--nodelist=compute-0-10',submit.call_args.args[0])
    self.assertIn('--cpus-per-task=1',submit.call_args.args[0])

 def test_finished_ssh_waiting_cpu_is_never_restarted_by_standby(self):
  with tempfile.TemporaryDirectory() as directory:
   c=self.fixture(directory);c['handoff_ack']=str(Path(directory)/'no_ack.json')
   configuration=Path(directory)/'configuration.json';native=Path(directory)/'native.json'
   cpu.write(configuration,c);cpu.write(native,dict(exit_code=0))
   task=dict(configuration=str(configuration),native_state=str(native))
   with patch.object(scheduled_run,'write') as request,patch.object(scheduled_run,'identity') as identity:
    self.assertIsNone(scheduled_run.handoff(task,99))
   request.assert_not_called();identity.assert_not_called()

 def test_uncertain_submission_does_not_submit_another_statistics_job(self):
  with tempfile.TemporaryDirectory() as directory:
   c=self.fixture(directory);configuration=Path(directory)/'configuration.json';cpu.write(configuration,c)
   ledger=dict(runs={c['run']:dict(state='COMPLETED',exit_code='0:0')})
   @contextmanager
   def locked():yield ledger
   with patch.object(cpu,'locked_ledger',locked),patch.object(cpu,'write'),\
        patch.object(cpu,'cpu_destination',return_value='compute-0-10'),\
        patch.object(cpu.subprocess,'check_output',side_effect=cpu.subprocess.TimeoutExpired('sbatch',30)) as submit:
    plan=dict(configurations=[str(configuration)])
    self.assertEqual(cpu.queue(plan),[])
    self.assertEqual(cpu.queue(plan),[])
   self.assertEqual(submit.call_count,1)
   self.assertEqual(ledger['cpu_statistics'][c['run']]['state'],'SUBMISSION_OBSERVATION_UNCERTAIN')

 def test_busy_cpu_pool_queues_one_node_instead_of_requesting_every_node(self):
  with tempfile.TemporaryDirectory() as directory:
   c=self.fixture(directory);configuration=Path(directory)/'configuration.json';cpu.write(configuration,c)
   ledger=dict(runs={c['run']:dict(state='COMPLETED',exit_code='0:0')})
   @contextmanager
   def locked():yield ledger
   with patch.object(cpu,'locked_ledger',locked),patch.object(cpu,'write'),\
        patch.object(cpu,'cpu_destination',return_value=None),\
        patch.object(cpu.subprocess,'check_output',return_value='12346\n') as submit:
    self.assertEqual(len(cpu.queue(dict(configurations=[str(configuration)]))),1)
   command=submit.call_args.args[0]
   self.assertIn('--nodes=1',command);self.assertIn('--cpus-per-task=1',command)
   self.assertIn('--exclude=compute-0-[0-7,14,18,20-22]',command)
   self.assertFalse(any(arg.startswith('--nodelist=') for arg in command))


if __name__=='__main__':unittest.main()
