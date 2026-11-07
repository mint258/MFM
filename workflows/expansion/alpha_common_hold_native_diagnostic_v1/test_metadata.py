"""Pure metadata boundaries; actual chemistry is separately native-diagnostic."""
import unittest
from .science import capture
from .contracts import actual_c0


class Metadata(unittest.TestCase):
    def test_original_exception_type_message_and_trace_retained(self):
        class OriginalFailure(ValueError):pass
        def original():raise OriginalFailure('unchanged original failure')
        value,event=capture(original)
        self.assertIsNone(value);self.assertEqual(event['exception_type'],'OriginalFailure')
        self.assertEqual(event['message'],'unchanged original failure')
        self.assertIn('OriginalFailure: unchanged original failure',event['exact_traceback'])
        self.assertEqual(event['frames'][-1]['function'],'original')
        self.assertEqual(capture(lambda:'same original value')[1],{'status':'PASS','result':'same original value'})

    def test_running_or_main_cannot_supply_original_alpha_c0(self):
        parent=dict(JobIDRaw='1885169',State='RUNNING',ExitCode='0:0',UID='1264',endpoint='218.192.171.238:22')
        with self.assertRaises(ValueError):actual_c0({'actual_parents':[parent]},'1885169')
        parent.update(State='COMPLETED');self.assertEqual(actual_c0({'actual_parents':[parent]},'1885169'),parent)
        with self.assertRaises(ValueError):actual_c0({'actual_parent':{**parent,'UID':'1278','endpoint':'202.38.247.57:22'}},'1885169')


if __name__=='__main__':unittest.main()
