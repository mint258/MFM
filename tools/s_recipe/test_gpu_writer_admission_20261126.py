"""Refused new work must not change the running writer's live forecast."""
import json
from pathlib import Path
import tempfile
import unittest
from gpu_writer_admission_20261126 import register_after_admission


class ProspectiveWriter(unittest.TestCase):
    def test_refusal_keeps_the_live_file_and_input_unchanged(self):
        current=dict(entries=[dict(id='running',node='compute-0-20',kind='node_ram',bytes=64)])
        extra=[dict(id='new',node='compute-0-20',kind='node_ram',bytes=64)]
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'forecast.json'
            original=json.dumps(current)
            path.write_text(original)
            def refuse(_):raise RuntimeError('prospective RAM unavailable')
            with self.assertRaises(RuntimeError):
                register_after_admission(current,extra,refuse,lambda value:path.write_text(json.dumps(value)))
            self.assertEqual(path.read_text(),original)
            self.assertEqual(current,dict(entries=[dict(id='running',node='compute-0-20',kind='node_ram',bytes=64)]))

    def test_success_publishes_once_and_preserves_existing_entries(self):
        current=dict(entries=[dict(id='running',bytes=64)])
        extra=[dict(id='new',bytes=64)]
        publications=[]
        result=register_after_admission(current,extra,lambda rows:dict(admitted=rows==extra),publications.append)
        self.assertTrue(result['admitted'])
        self.assertEqual(publications,[dict(entries=[dict(id='running',bytes=64),dict(id='new',bytes=64)])])
        self.assertEqual(current,dict(entries=[dict(id='running',bytes=64)]))
