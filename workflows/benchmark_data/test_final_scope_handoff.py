"""Terminal scope evidence must include both producers, without data replay."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from .final_scope_handoff import closed_scope, target_definition_readiness

class FinalScopeHandoffTests(unittest.TestCase):
    def scope(self, root):
        geometry=root/"geometry/shared_v1";geometry.mkdir(parents=True)
        pp=root/"labels/Pprime/shared_v1";pp.mkdir(parents=True)
        gm=geometry/"producer_geometry.json"
        gm.write_text(json.dumps(dict(job="GEOMETRY",status="ALL_QUEUED_MOLECULES_TERMINAL",
                                      states={"SPRIME_AND_D_READY":2,"SOURCE_FAILED":1})))
        ga=dict(immutable=True,cross_node_read_allowed=True,publishing_uid=os.getuid(),
                source_producer_manifest=str(gm),producer_job="GEOMETRY")
        (geometry/"access.json").write_text(json.dumps(ga))
        pm=pp/"producer_quantum.json"
        pm.write_text(json.dumps(dict(job="QUANTUM",status="ALL_QUEUED_PPRIME_TERMINAL",
            source_all_geometry_complete=True,
            states={"PPRIME_READY":3,"PPRIME_PARTIAL_WITH_RECORDED_OUTCOMES":1})))
        pa=dict(immutable=True,writers_closed=True,cross_node_read_allowed=True,
                publishing_uid=os.getuid(),producer_job="QUANTUM",producer_manifest=str(pm))
        (pp/"access.json").write_text(json.dumps(pa))
        return geometry,pp

    def test_partial_scientific_outcomes_can_close_without_becoming_all_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.scope(root);seen=[]
            out=closed_scope(root,native=lambda job:seen.append(job) or {"source":"synthetic fixture"})
            self.assertEqual(seen,["GEOMETRY","QUANTUM"])
            self.assertTrue(out["production_closed"])
            self.assertFalse(out["Pprime"]["all_ready"])

    def test_pending_geometry_or_active_quantum_is_not_final(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);geometry,pp=self.scope(root)
            source=geometry/"producer_geometry.json";initial=source.read_text()
            report=json.loads(initial);report["states"]["PENDING"]=1;source.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,"Geometry terminal"):
                closed_scope(root,native=lambda job:{})
            source.write_text(initial)
            source=pp/"access.json";report=json.loads(source.read_text())
            report["writers_closed"]=False;source.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,"remains active"):
                closed_scope(root,native=lambda job:{})

    def test_failed_native_evidence_cannot_be_replaced_by_a_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.scope(root)
            def not_closed(job):
                raise RuntimeError("Native producer remains RUNNING")
            with self.assertRaisesRegex(RuntimeError,"RUNNING"):
                closed_scope(root,native=not_closed)

    def test_candidate_site_proposal_does_not_mark_all_work_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);nmr=root/"nmr.json";atomic=root/"atomic.json"
            nmr.write_text(json.dumps(dict(all_test_spectrum_counts_match=True,
                                           all_test_unique_molecule_counts_match=True)))
            prep=dict(NMR2018_published_test_count_reconciliation=str(nmr),
                      pKa_atomic_targets=str(atomic))
            atomic.write_text(json.dumps(dict(single_site_definition_frozen=False,
                atomic_mechanism_ready=False,eligibility_status="PROPOSED")))
            self.assertFalse(target_definition_readiness(prep)["all_required_work_complete"])
            atomic.write_text(json.dumps(dict(single_site_definition_frozen=True,
                atomic_mechanism_ready=True,user_definition_authority="SYNTHETIC_USER_DECISION")))
            self.assertTrue(target_definition_readiness(prep)["all_required_work_complete"])

    def test_final_publication_reports_both_scopes_but_keeps_unapproved_targets_pending(self):
        from . import final_scope_handoff as module
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);nmr=root/"counts.json"
            nmr.write_text(json.dumps(dict(all_test_spectrum_counts_match=True,
                                           all_test_unique_molecule_counts_match=True)))
            progress=root/"progress.json"
            prep=dict(NMR2018_published_test_count_reconciliation=str(nmr),
                      NMR2018_targets="original_NMR_targets.json",
                      pKahub_macro_targets="original_macro_targets.json",
                      uniform_scope_ready=False)
            progress.write_text(json.dumps(dict(directive19_data_preparation=prep)))
            output=root/"delivery/final_fixture"
            def available_handoff(argv, capacity_check):
                self.assertIs(capacity_check,module.final_capacity)
                output.mkdir(parents=True)
                (output/"manifest.json").write_text(json.dumps(dict(directive19_resolutions={})))
            argv=["final","--root",str(root),"--progress",str(progress),
                  "--attempt","final_fixture","--quota-snapshot",str(root/"quota")]
            with mock.patch("sys.argv",argv),mock.patch.object(module,"closed_scope",
                    return_value={"production_closed":True}),mock.patch.object(module,"final_capacity"),\
                    mock.patch.object(module.handoff,"main",side_effect=available_handoff):
                module.main()
            result=json.loads((output/"manifest.json").read_text())
            self.assertEqual(set(result["production_scopes"]),
                             {"original","directive19_uniform_Sprime"})
            self.assertFalse(result["all_required_production_complete"])
            self.assertFalse(result["all_required_work_complete"])
            self.assertTrue(result["directive19_data_preparation"]["uniform_scope_ready"])
            self.assertNotIn("pKahub_atomic",result["active_target_manifests"])
