"""Tiny typed-parquet → canonical masks → exact tails → moments replay fixture.

No synthetic object is presented to the production FROZEN-authority gate. This
test invokes real lower-level stages with explicitly named fixture-only inputs.
"""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import threading
import unittest

from runtime import (canonical_bytes, legacy, load, ref, require, save)
from compact import arrow_schema, encode
from reader import atom_order, observations
from run import (advance_tails, check_mass, final_statistics, mass_signature,
                 merge_models, quantile_results)
from runtime import initial_queries
from series import inventory
import worker


class ReaderPipelineTests(unittest.TestCase):
    def test_typed_parquet_to_rebuilt_final_statistics_excludes_val(self):
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
        # This small immutable source config supplies code pins, not scientific label bodies.
        repository = Path(__file__).resolve().parents[4]
        source_cfg = load(repository / "configs/data_v1/labels/streaming_v1.json")
        common, masks = legacy(source_cfg)
        fields = [{"field_id": i, "field_key": "fixture.D20." + name, "task": "D20",
            "registry_id": None, "source_path": name, "component": "value", "level": "molecule",
            "unit": "fixture_only", "element_reference_eligible": False,
            "physical_range": {"lower":None,"upper":None,"lower_exclusive":False}}
            for i, name in enumerate(common.D20_NAMES)]
        with tempfile.TemporaryDirectory(prefix="final_fit_reader_fixture_") as tmp:
            root=Path(tmp); owner_rows=[]; base_rows=[]; label_rows=[]; mask_rows=[]
            for i, role in enumerate(("TRAIN", "VAL")):
                base={"record_id":"fixture-r"+str(i),"molecule_id":"fixture-m"+str(i),
                      "attempt_id":"fixture-attempt","job_id":7,"task_id":2}
                payload="fixture-payload"+str(i); numbers=[6,8]
                owner_rows.append({**base,"record_ordinal":i,"total_atoms":2,"heavy_atoms":2,"lane":"fixture-lane",
                    "record_payload_sha256":payload,"geometry_source":"pm7","geometry_id":"opaque / "+str(i),
                    "effective_role":role,"common_population":True,"fit_eligible":role=="TRAIN",
                    "fit_reason":"FIT_TRAIN_COMMON_NOT_DIAGNOSTIC" if role=="TRAIN" else "ROLE_VAL"})
                base_rows.append({**base,"atomic_numbers":numbers,"native_atom_order_sha256":atom_order(numbers),
                    "source_payload_sha256":payload,"geometry_status":"ORIGINAL_PM7_GEOMETRY"})
                row={**base,"status":"SUCCESS","values_float64":[float(k+i*1000000) for k in range(20)],
                    "valid_mask":[True]*20,"descriptor_names":common.D20_NAMES}
                label_rows.append(row)
                decoded={**row,"total_atoms":2,"calc_type":"D20"}; entries=[]
                for f,values,indices,reason in common.task_components(decoded,"D20",fields):
                    _,sm,vm,sr,nr,rv=masks.source_value_mask(f,decoded,values,reason)
                    entries.append({"field_id":f["field_id"],"source_path":f["source_path"],
                        "values_float64":values,"source_value_mask":sm,"value_mask":vm,
                        "source_reasons":sr,"new_reasons":nr,"review_reasons":rv})
                masks.add_cross_field_checks(entries,decoded)
                mask_rows.append(encode(i,0,entries))
            for name,rows in (("side",owner_rows),("base",base_rows),("labels",label_rows)):
                pq.write_table(pa.Table.from_pylist(rows),root/(name+".parquet"))
            pq.write_table(pa.Table.from_pylist(mask_rows,schema=arrow_schema()),root/"D20_000.mask.parquet")
            source={**ref(root/"labels.parquet"),"family":"D20"}
            group={"group_index":0,"source_job_id":7,"base_files":[ref(root/"base.parquet")],"label_files":[source],"expected_records":2}
            side={"side_table":ref(root/"side.parquet"),"fit_records":1,"records":2}
            manifest=save(root/"fixture_input.json",{"fixture_only":True,"never_a_production_FROZEN_authority":True})
            item={"manifest":manifest,"dataset":{"dataset_id":"fixture","label_group":"P_D","geometry_source":"pm7",
                "allowed_geometry_status":["ORIGINAL_PM7_GEOMETRY"]},"fields":fields,
                "plan":{"element_basis":[6,8],"task_codes":{"D20":0}},
                "mask_receipts":{0:{"outputs":[ref(root/"D20_000.mask.parquet")]}}}
            got=list(observations(item,group,side,source_cfg,hash_sources=True))
            self.assertEqual(len(got),1);self.assertEqual(got[0][0]["effective_role"],"TRAIN")
            self.assertEqual([e["values_float64"][0] for e in got[0][2]],list(map(float,range(20))))
            catalog,physical=inventory(item)
            payload={"catalogs":{"fixture":catalog},"physical":{"fixture":physical}}
            cfg={"output_cap_bytes":64<<20,"worker_serialized_buffer_cap_bytes":4<<20,
                 "worker_rss_stop_bytes":2<<30,"worker_histogram_row_cap":10000,"source_config":{"fixture_only":True}}
            job={"item":item,"group":group,"side":side,"work_index":16}
            def pass_run(phase,index):
                out=root/("pass"+str(index));out.mkdir()
                worker.initialize(cfg,source_cfg,None,threading.Event(),phase,payload,str(out))
                return load(require(worker.run(job)))
            energy=pass_run("energy",0);mass=mass_signature([energy]);payload["models"]=merge_models([energy],[item])
            payload["queries"]={"fixture":{"lower":initial_queries(catalog,"lower_tail",probability="0.001"),
                                              "upper":initial_queries(catalog,"upper_tail",probability="0.999")}}
            finished={"fixture":{"lower":[],"upper":[]}};index=1;db=duckdb.connect();db.execute("SET threads=1")
            while any(q["fields"] for q in payload["queries"]["fixture"].values()):
                r=pass_run("quantiles",index);check_mass([r],mass)
                payload["queries"]=advance_tails(db,[r],payload["queries"],finished);index+=1
                self.assertLessEqual(index,8)
            quantiles=quantile_results(payload["catalogs"],finished);payload["quantiles"]=quantiles
            del payload["queries"]
            first=pass_run("moments",index);second=pass_run("moments",index+1)
            check_mass([first],mass);check_mass([second],mass)
            authority={"authority":{"fixture_only":True},"diagnostic_geometry_key_sha256":"fixture_only"}
            args=(payload,quantiles,[item],[{"dataset_id":"missing_fixture_pprime","status":"PENDING"}],
                  {"fixture":{"fit_records":1}},authority,mass,cfg)
            a=final_statistics([first],*args);b=final_statistics([second],*args)
            self.assertEqual(canonical_bytes(a),canonical_bytes(b))
            self.assertEqual([s["mean"] for s in a["datasets"]["fixture"]["series"]],
                             [float(int(s["key"].split("/")[0])) for s in catalog])
            self.assertTrue(all(s["n"]==1 and s["std_ddof0"]==0 for s in a["datasets"]["fixture"]["series"]))
            self.assertFalse(a["D4_published"]);self.assertEqual(len(a["pending_datasets"]),1)
            db.close()
