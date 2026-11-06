"""New coordinator metadata and shell generation, without submitting science."""
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from .stereo_coordinate import choose_nodes, job_script


class CoordinatorTests(unittest.TestCase):
    def test_shell_and_embedded_preflight_compile_without_replacing_env_names(self):
        script=job_script(Path('/shared/new'),'/runtime','/venv/bin/python',Path('/shared/new/c.json'),
                          'compute-0-1','cpu',64,'full_0','workflows.expansion.window3_v2.producer')
        result=subprocess.run(['bash','-n'],input=script,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('PYTHONDONTWRITEBYTECODE=1',script)
        self.assertNotIn('/pythonDONTWRITEBYTECODE',script)
        code=script.split("<<'PY'\n",1)[1].split('\nPY\n',1)[0]
        compile(code,'synthetic-node-preflight','exec')
        self.assertIn('planned_bytes=512*1024**3',code)
        self.assertIn('interval_seconds=5',code)

    def test_idle_cpu_nodes_are_preferred_and_cpu_assignments_are_distinct(self):
        text='compute-0-1|cpu*|0/64/0/64\ncompute-0-1|all|0/64/0/64\ncompute-0-2|all|0/32/0/32\ncompute-0-8|all|0/48/0/48\nsonmi1|cpu*|0/16/0/16\n'
        with patch('subprocess.check_output',return_value=text):
            actual=choose_nodes()
        self.assertEqual(actual,[('compute-0-1','cpu',64),('compute-0-2','all',32),
                                 ('compute-0-8','all',48),('sonmi1','cpu',16)])


if __name__ == '__main__':
    unittest.main()
