"""Two separate pure metadata checks, not part of any frozen check runner."""
import unittest
from .common import fields,duration,wall


class MetadataBoundaries(unittest.TestCase):
    def test_site_colon_slash_fields_and_duplicate_rejection(self):
        raw='JobId=9 Partition=cpu AllocNode:Sid=sonmi:123 ReqNodeList=compute-0-1 CPUs/Task=16 ReqB:S:C:T=0:0:*:*'
        value=fields(raw)
        self.assertEqual(value['Partition'],'cpu')
        self.assertEqual(value['AllocNode:Sid'],'sonmi:123')
        self.assertEqual(value['CPUs/Task'],'16')
        self.assertEqual(value['ReqB:S:C:T'],'0:0:*:*')
        with self.assertRaisesRegex(ValueError,'DUPLICATE_SCONTROL_FIELD'):
            fields(raw+' Partition=other')

    def test_exact_whole_minute_finite_wall_and_days_runtime(self):
        self.assertEqual(wall(5520),'01:32:00')
        self.assertEqual(duration('1-00:00:00'),86400)
        self.assertEqual(duration(wall(172800)),172800)
        for seconds in (0,5500,172860,True):
            with self.subTest(seconds=seconds),self.assertRaises(ValueError):wall(seconds)
        for value in ('UNLIMITED','00:60:00','00:00:60','-01:00:00'):
            with self.subTest(value=value),self.assertRaises(ValueError):duration(value)


if __name__=='__main__':unittest.main()
