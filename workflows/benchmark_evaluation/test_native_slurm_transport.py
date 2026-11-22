"""Native command placement and duplicate-submission protection with synthetic process results."""
import subprocess
import unittest
from unittest.mock import Mock
from .native_slurm_transport import native_control

class NativeSlurmTransportTests(unittest.TestCase):
    def result(self,code=0,out="501\n",err=""):
        return subprocess.CompletedProcess([],code,stdout=out,stderr=err)
    def test_readonly_accounting_keeps_exact_native_query_through_sonmi(self):
        runner=Mock(return_value=self.result(out="4537644|COMPLETED|0:0\n"))
        actual=native_control(["sacct","-j","4537644","-X","-n","-P"],runner=runner)
        self.assertEqual(actual,"4537644|COMPLETED|0:0")
        command=runner.call_args.args[0]
        self.assertEqual(command[:2],["ssh","-n"])
        self.assertEqual(command[-2:],["sonmi","sacct -j 4537644 -X -n -P"])
    def test_only_refused_readonly_query_is_retried_with_bounded_backoff(self):
        refused=self.result(255,"","ssh: connect to host sonmi port 22: Connection refused")
        runner=Mock(side_effect=[refused,refused,self.result(out="closed\n")]);sleep=Mock()
        self.assertEqual(native_control(["sacct","-j","1"],runner=runner,sleeper=sleep),"closed")
        self.assertEqual(runner.call_count,3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list],[1,2])
        runner=Mock(return_value=refused)
        with self.assertRaises(subprocess.CalledProcessError):
            native_control(["sacct","-j","1"],runner=runner,sleeper=Mock())
        self.assertEqual(runner.call_count,3)
    def test_unrelated_accounting_error_is_not_hidden_by_retry(self):
        for code,error in ((1,"invalid field"),(255,"Permission denied"),(255,"Connection timed out")):
            runner=Mock(return_value=self.result(code,"",error))
            with self.assertRaises(subprocess.CalledProcessError):
                native_control(["sacct","-j","1"],runner=runner,sleeper=Mock())
            self.assertEqual(runner.call_count,1)
    def test_held_submission_is_local_single_execution_and_returns_actual_id(self):
        args=["sbatch","--parsable","--hold","--dependency=afterany:17","/owned/group.sbatch"]
        runner=Mock(return_value=self.result(out="501\n"))
        self.assertEqual(native_control(args,runner=runner),"501")
        self.assertEqual(runner.call_args.args[0],args)
        self.assertEqual(runner.call_count,1)
    def test_release_uses_same_local_controller_once(self):
        args=["scontrol","release","501"];runner=Mock(return_value=self.result(out=""))
        self.assertEqual(native_control(args,runner=runner),"")
        self.assertEqual(runner.call_args.args[0],args)
        self.assertEqual(runner.call_count,1)
    def test_submission_and_release_errors_never_trigger_a_mutation_retry(self):
        for args in (["sbatch","--parsable","--hold","/owned/group.sbatch"],["scontrol","release","501"]):
            runner=Mock(return_value=self.result(255,"","Connection refused"));sleep=Mock()
            with self.assertRaises(subprocess.CalledProcessError):
                native_control(args,runner=runner,sleeper=sleep)
            self.assertEqual(runner.call_count,1);sleep.assert_not_called()
    def test_unregistered_or_unheld_commands_are_rejected_before_execution(self):
        for args in ([],["scancel","501"],["scontrol","hold","501"],["scontrol","release","all"],
                     ["sbatch","--parsable","/owned/group.sbatch"],["sbatch","--hold","/owned/group.sbatch"]):
            runner=Mock()
            with self.assertRaises(ValueError):native_control(args,runner=runner)
            runner.assert_not_called()
