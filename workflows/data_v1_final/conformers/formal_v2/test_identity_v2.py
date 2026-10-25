"""Nine small identity fixtures; no UFF, large scans, or actual submission."""
import ast
import json
import os
from pathlib import Path
import tempfile
import unittest
from identity_v2 import (IO,INT64_MAX,append_generated,attempt_binding,fixed_random_ids,
                         old_identity,random_identity_contract)


class IdentityTests(unittest.TestCase):
    def generated(self,cid=0,key="a"*64):
        return {"task_key":key,"seed":7,"candidate_id":cid,"geometry_sha256":"fixture",
                "kernel_sprime_conf_idx":1,"origin":"data_v1_fill_10N"}
    def test_old_gapped_ids_remain_exactly_physical_ids(self):
        self.assertEqual([old_identity(i)["canonical_sprime_conf_idx"] for i in [2,6,9]],[2,6,9])
    def test_append_skips_failed_attempt_range_and_original_N(self):
        self.assertEqual(append_generated([self.generated()],10,6)[0]["sprime_conf_idx"],10)
        self.assertEqual(append_generated([self.generated()],2,99)[0]["sprime_conf_idx"],100)
        self.assertEqual(append_generated([self.generated()],3,None)[0]["sprime_conf_idx"],3)
    def test_generated_identity_assignment_is_input_order_invariant(self):
        rows=[self.generated(8),self.generated(2)]
        left=append_generated(rows,10,5);right=append_generated(list(reversed(rows)),10,5)
        self.assertEqual(left,right);self.assertEqual([(r["candidate_id"],r["sprime_conf_idx"]) for r in left],[(2,10),(8,11)])
    def test_original_fixed_random_two_and_perturb_record_ids_unchanged(self):
        for mid,ids in [("molecule_01200493",[2,6]),("molecule_01201800",[2,9]),("fixture",[0,3,7,11])]:
            physical=[old_identity(i)["canonical_sprime_conf_idx"] for i in ids]
            self.assertEqual(fixed_random_ids(mid,ids)[:2],fixed_random_ids(mid,physical)[:2])
            self.assertEqual([f"pprime:{mid}:{i}" for i in fixed_random_ids(mid,ids)[:2]],
                             [f"pprime:{mid}:{i}" for i in fixed_random_ids(mid,physical)[:2]])
    def test_no_inferred_taskkey_or_duplicate_provenance_and_no_overflow(self):
        with self.assertRaisesRegex(ValueError,"ACTUAL_ONCE"):append_generated([self.generated(key="guess")],1,0)
        with self.assertRaisesRegex(ValueError,"DUPLICATE_NEW"):append_generated([self.generated(),self.generated()],1,0)
        with self.assertRaisesRegex(ValueError,"OVERFLOW"):append_generated([self.generated()],1,INT64_MAX)
    def test_random_contract_declares_int64_physical_identity_and_algorithm_sha(self):
        contract=random_identity_contract()
        self.assertEqual(contract["random_identity_basis"],"canonical_sprime_conf_idx")
        self.assertTrue(contract["order_rank_contiguous_zero_based"])
        self.assertEqual(contract["random_order_algorithm"]["sha256"],"41f21f5586c06f3c6fd7cfa9712623adc8091da996c72f6d71170dd4b716e2cb")
    def test_actual_pilot_import_ledger_bound_not_guessed(self):
        with tempfile.TemporaryDirectory(prefix="sprime_id_v2_") as tmp:
            root=Path(tmp);(root/"ledger").mkdir();source={"path":"fixture.gz","bytes":1,"sha256":"x"}
            key="b"*64;packet={"molecule_id":"m","source":source,"formal_start":None}
            imported={"molecule_id":"m","source":source,"task_key":key}
            ledger={"schema":"SPRIME_PILOT_ATTEMPT_IMPORTED_V1","molecule_id":"m","task_key":key,"source":source}
            (root/"ledger"/(key+".json")).write_text(json.dumps(ledger))
            binding=attempt_binding(packet,{"external_output_root":str(root),"attempt_ledger_root":str(root/"ledger")},{"m":imported})
            self.assertEqual(binding["task_key"],key)
            with self.assertRaisesRegex(ValueError,"ACTUAL_FORMAL_START"):
                attempt_binding(packet,{"external_output_root":str(root),"attempt_ledger_root":str(root/"ledger")},{})
    def test_consumer_physical_id_may_have_gaps_but_rank_stays_dense(self):
        import sqlite3
        db=sqlite3.connect(":memory:")
        db.execute("CREATE TABLE g(sprime_conf_idx INTEGER PRIMARY KEY)")
        db.executemany("INSERT INTO g VALUES(?)",[(2,),(6,),(12,)])
        ranks=list(enumerate(fixed_random_ids("m",[2,6,12])))
        self.assertEqual([r for r,_ in ranks],[0,1,2])
        self.assertEqual(db.execute("SELECT sprime_conf_idx FROM g ORDER BY sprime_conf_idx").fetchall(),[(2,),(6,),(12,)])
        db.close()
    def test_actual_v2_scalar_sql_preserves_old_ids_and_failed_range(self):
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
        # Execute literal SQL from the production v2 finalizer against 3 rows.
        source=Path(__file__).with_name("finalize_common_v2.py").read_text()
        literals=[node.value for node in ast.walk(ast.parse(source)) if isinstance(node,ast.Constant) and isinstance(node.value,str)]
        def sql(prefix):return next(value for value in literals if value.startswith(prefix))
        with tempfile.TemporaryDirectory(prefix="sprime_v2_sql_") as tmp:
            path=Path(tmp)/"old.parquet"
            pq.write_table(pa.table({"molecule_id":["m"]*3,"sprime_conf_idx":[0,1,5],
                "uff_energy_kcal_mol":[1.,2.,3.],"atom_order_sha256":["z"]*3,
                "source_record_id":["anchor"]*3,"seed":[7]*3,
                "status":["SUCCESS","UFF_NOT_CONVERGED","SUCCESS"],"converged":[True,False,True]}),path)
            db=duckdb.connect()
            db.execute(sql("CREATE TABLE all_old_attempts").replace("PATHS","['"+str(path)+"']"))
            db.execute(sql("CREATE TABLE old AS"))
            db.execute(sql("CREATE VIEW attempted_bounds AS"))
            db.execute("CREATE TABLE p AS SELECT 'm' AS molecule_id,6::BIGINT AS S_conformers")
            db.execute("CREATE TABLE old_file_pins AS SELECT ?::VARCHAR AS source_path,'hash' AS source_sha256,1::BIGINT AS source_bytes",[str(path)])
            db.execute(sql("CREATE TABLE uff_keys AS"))
            observed=db.execute("SELECT sprime_conf_idx,canonical_sprime_conf_idx,kernel_sprime_conf_idx,source_row_index,source_attempt_max_sprime_conf_idx,original_N FROM uff_keys ORDER BY sprime_conf_idx").fetchall()
            self.assertEqual(observed,[(0,0,0,0,5,6),(5,5,1,2,5,6)])
            self.assertEqual(append_generated([self.generated()],6,5)[0]["sprime_conf_idx"],6)
            db.close()


if __name__=="__main__":unittest.main()
