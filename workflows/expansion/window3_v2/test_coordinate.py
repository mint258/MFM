import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import coordinate


class Tests(unittest.TestCase):
    def test_full_submission_requires_all_10000_pilot_molecules(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'pilot').mkdir()
            (root/'pilot/summary.json').write_text(json.dumps({'counts':{'molecules':9999},'streams':{'R':5000,'N':4999}}))
            with patch.object(coordinate,'wait'), patch.object(coordinate.subprocess,'check_output') as submit:
                with self.assertRaisesRegex(RuntimeError,'Complete 10k'):coordinate.run(root,'1')
                submit.assert_not_called()

    def test_cancelled_parent_keeps_outputs_and_requires_continuation(self):
        with patch.object(coordinate,'parents',return_value={'1':['CANCELLED+','0:15']}), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'preserve its outputs'):coordinate.wait(['1'])


if __name__=='__main__':unittest.main()
