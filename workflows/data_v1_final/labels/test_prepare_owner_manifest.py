"""Small semantic tests for whole-molecule selection and native atom-order proof."""
from __future__ import annotations

import unittest

from prepare_owner_manifest import atom_order_sha, pick_whole_molecules, validate_geometry_row


def molecule(mid,n,job=7):
    return {"molecule_id":mid,"records":n,"S_conformers":n,"job_id":job}


class OwnerPreparationTests(unittest.TestCase):
    def test_keeps_complete_molecules_and_stops_at_target(self):
        rows=[molecule(str(i),10) for i in range(30)]
        got=pick_whole_molecules(rows,64,32,128)
        self.assertEqual(sum(x["records"] for x in got),70)
        self.assertEqual(len(got),7)

    def test_large_molecule_is_kept_whole_within_cap(self):
        got=pick_whole_molecules([molecule("a",100),molecule("b",10)],64,32,128)
        self.assertEqual([(x["molecule_id"],x["records"]) for x in got],[("a",100)])

    def test_skips_whole_molecule_that_would_breach_cap(self):
        got=pick_whole_molecules([molecule("a",20),molecule("b",120),molecule("c",30)],64,32,128)
        self.assertEqual([(x["molecule_id"],x["records"]) for x in got],[("a",20),("c",30)])

    def test_too_small_job_is_not_promoted_to_pilot(self):
        self.assertEqual(pick_whole_molecules([molecule("a",20)],64,32,128),[])

    def test_mixed_owner_jobs_rejected(self):
        with self.assertRaisesRegex(ValueError,"ONE_CANONICAL_OWNER_JOB"):
            pick_whole_molecules([molecule("a",20,7),molecule("b",30,8)],64,32,128)

    def test_missing_source_conformers_rejected(self):
        row=molecule("a",50)
        row["S_conformers"]=49
        with self.assertRaisesRegex(ValueError,"COUNT_INVALID"):
            pick_whole_molecules([row],64,32,128)

    def test_native_atom_order_and_payload_must_match(self):
        owner={"record_id":"r","molecule_id":"m","attempt_id":1,"job_id":7,"task_id":"t","total_atoms":3,"record_payload_sha256":"payload"}
        base={k:owner[k] for k in ("record_id","molecule_id","attempt_id","job_id","task_id")}
        base.update(atomic_numbers=[6,8,1],geometry_status="ORIGINAL_PM7_GEOMETRY",
            native_atom_order_sha256=atom_order_sha([6,8,1]),source_payload_sha256="payload")
        self.assertEqual(validate_geometry_row(base,owner),[6,8,1])
        base["atomic_numbers"]=[8,6,1]
        with self.assertRaisesRegex(ValueError,"ATOM_ORDER_SHA"):
            validate_geometry_row(base,owner)
        base["atomic_numbers"]=[6,8,1]
        base["source_payload_sha256"]="other"
        with self.assertRaisesRegex(ValueError,"PAYLOAD_SHA"):
            validate_geometry_row(base,owner)

    def test_source_atom_count_mismatch_rejected(self):
        owner={"record_id":"r","molecule_id":"m","attempt_id":1,"job_id":7,"task_id":"t","total_atoms":2,"record_payload_sha256":"payload"}
        base={**owner,"atomic_numbers":[6,8,1],"geometry_status":"ORIGINAL_PM7_GEOMETRY"}
        with self.assertRaisesRegex(ValueError,"ATOM_COUNT"):
            validate_geometry_row(base,owner)


if __name__=="__main__":
    unittest.main(verbosity=2)
