"""Model protocol/transport fixtures, NOT a Data release or joint ACK.

All metadata, indexes, values and authority interpreter below are synthetic
unit fixtures. They test fail-closed mechanics, not real physical acceptance.
"""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

import pytest
import torch

from phychem_mfm.phase1.v3_contract import FieldSpec, LabelRegistry, TrainNormalization, canonical_hash
from phychem_mfm.phase1.v3_data import DecodedSample
from phychem_mfm.phase1.v3_data_adapter import (ALL_A_POLICY, REQUIRED_EVIDENCE, VerifiedDataRelease,
    RealDataProvider, bound_json, make_proxy_inputs, rawref, tensor6_normalization, verify_release_binding)
from phychem_mfm.phase1.v3_label_domains import Tensor6Inputs, Tensor6Target, tensor6_from_f64
from phychem_mfm.phase1.v3_sampling import ConformerRef, InMemorySamplingIndex, MoleculeEntry, SampleChoice, UniformMoleculeSampler
from phychem_mfm.phase1.v3_structural import StructuralFieldBinding, StructuralViewConfig
from phychem_mfm.phase1.v3_trainer import PreparedV3Batch


def ref(path):
    raw = Path(path).read_bytes()
    return {"path": str(Path(path).resolve()), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False), encoding="utf-8")
    return ref(path)


def metadata_case(tmp_path):
    evidence = {}
    for key in REQUIRED_EVIDENCE:
        body = {"UNIT_FIXTURE_ONLY_NOT_A_REAL_RELEASE": True, "name": key}
        if key == "joint_contract":
            body.update(status="MODEL_DATA_JOINT_CONTRACT_FROZEN", version="3.0", model_confirmation=True, data_confirmation=True)
        if key == "d4_statistics":
            body["parameters"] = {"q": {"n": 2, "std_ddof0": 2., "winsor_lower": 1., "winsor_upper": 5., "labels_modified": False}}
        evidence[key] = write(tmp_path / (key + ".json"), body)
    source = tmp_path / "unit_interpreter.py"
    request = {"mode": "authoritative_proxy", "UNIT_FIXTURE_ONLY_NOT_A_REAL_REQUEST": True}
    projection = {
        "schema": "model_v3_verified_Data_consumption_projection_v1", "request_sha256": "",
        "evidence_sha256": canonical_hash(evidence), "data_version": "UNIT_FIXTURE_NOT_D3",
        "scope": "authoritative_proxy", "policy": deepcopy(ALL_A_POLICY),
        "TRAIN_population": "Common_intersection_effective_TRAIN",
        "heldout_base_and_all_direct_children_excluded": True,
        "validation_population_bindings": {"VAL": "a" * 64, "TRAIN_UNSEEN_CONFORMATION": "b" * 64},
        "role_index_sha256": {role: str(i + 1) * 64 for i, role in enumerate(("TRAIN", "VAL", "TRAIN_UNSEEN_CONFORMATION"))},
        "targets": {"q": {"target_id": "unit_q", "condition": "xtb_singlepoint", "unit": "au",
                              "sign": "source_signed", "frame": "source_frame_assumption", "origin_policy": "explicit_source_anchor"}},
        "reader_source": ref(Path(__file__)),
        "normalization_sha256": canonical_hash({"q": asdict(TrainNormalization((0.,), (2.,),
            evidence["d4_statistics"]["sha256"], "UNIT_FIXTURE_NOT_D3"))}),
        "D4_bindings": {"q": {"registry_id": 674, "condition": "xtb_singlepoint", "task": "xtb_singlepoint",
            "series_key": "physical/674/xtb_singlepoint/frobenius_norm", "statistics_pointer": ["parameters", "q"],
            "population_sha256": evidence["effective_train"]["sha256"],
            "heldout_exclusion_sha256": evidence["heldout_exclusion"]["sha256"],
            "series_source": ref(Path(__file__)), "statistics_source": ref(Path(__file__)),
            "quantile_probabilities": [0.001, 0.999], "statistic": "std_ddof0"}},
    }
    def interpreter(p):
        source.write_text("import json\nfrom phychem_mfm.phase1.v3_contract import canonical_hash\n"
            + "TEMPLATE=json.loads(" + repr(json.dumps(p)) + ")\n"
            + "def verify_model_v3_release_authority(request,documents):\n"
            + "    assert documents['release']['UNIT_FIXTURE_ONLY_NOT_A_REAL_RELEASE'] is True\n"
            + "    p=json.loads(json.dumps(TEMPLATE)); p['request_sha256']=canonical_hash(request); return p\n", encoding="utf-8")
        return ref(source)
    return evidence, request, projection, interpreter


def test_joint_user_choice_alone_does_not_unlock_real_release(tmp_path):
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    evidence["joint_contract"] = write(tmp_path / "joint_contract.json", {"status": "USER_ALL_A_CONFIRMED_NOT_JOINT_ACK"})
    with pytest.raises(ValueError, match="joint ACK"):
        verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))


def test_model_protocol_binds_request_all_actual_metadata_and_interpreter(tmp_path):
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    release = verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))
    assert release.request_sha256 == canonical_hash(request)
    assert tensor6_normalization(release, "q").scale == (2.,)
    # Route UUID/request changes cannot create a circular provider source hash.
    changed = replace(release, request_sha256="f" * 64,
                      projection={**release.projection, "request_sha256": "f" * 64})
    assert changed.data_sha256 == release.data_sha256 and changed.sha256 != release.sha256
    release.projection["TRAIN_population"] = "source_FULL"
    with pytest.raises(ValueError, match="mutated"): release.reverify()


@pytest.mark.parametrize("change", ["heldout", "FULL", "bool_policy", "scope", "missing_role"])
def test_unknown_or_unbound_authority_projection_is_rejected(tmp_path, change):
    evidence, request, p, interpreter = metadata_case(tmp_path)
    if change == "heldout": p["heldout_base_and_all_direct_children_excluded"] = False
    if change == "FULL": p["TRAIN_population"] = "SOURCE_FULL"
    if change == "bool_policy": p["policy"]["tensor6_center"] = False
    if change == "scope": p["scope"] = "pilot_not_final"
    if change == "missing_role": del p["role_index_sha256"]["VAL"]
    with pytest.raises(ValueError): verify_release_binding(request, evidence=evidence, verifier=interpreter(p))


def test_missing_actual_evidence_duplicate_keys_and_oversized_metadata_rejected(tmp_path):
    evidence, request, p, interpreter = metadata_case(tmp_path)
    del evidence["heldout_exclusion"]
    with pytest.raises(ValueError): verify_release_binding(request, evidence=evidence, verifier=interpreter(p))
    duplicate = tmp_path / "duplicate.json"; duplicate.write_text('{"x":1,"x":2}')
    with pytest.raises(ValueError, match="Duplicate"): bound_json(ref(duplicate))
    with pytest.raises(ValueError): rawref({"path": "/unknown", "bytes": (2 << 20) + 1, "sha256": "a" * 64})


@pytest.mark.parametrize("change", ["empty", "zero", "nonpositive_F32", "wrong_series", "wrong_population", "modified_labels", "wrong_quantile", "wrong_statistic"])
def test_tensor_d4_unknown_degenerate_or_other_population_never_gets_floor(tmp_path, change):
    evidence, request, p, interpreter = metadata_case(tmp_path)
    stats = json.loads(Path(evidence["d4_statistics"]["path"]).read_text())
    record = stats["parameters"]["q"]
    if change == "empty": record["n"] = 0
    if change == "zero": record["std_ddof0"] = 0.
    if change == "nonpositive_F32": record["std_ddof0"] = 1e-300
    if change == "modified_labels": record["labels_modified"] = True
    evidence["d4_statistics"] = write(Path(evidence["d4_statistics"]["path"]), stats)
    if change == "wrong_series": p["D4_bindings"]["q"]["series_key"] = "physical/674/other/frobenius_norm"
    if change == "wrong_population": p["D4_bindings"]["q"]["population_sha256"] = "e" * 64
    if change == "wrong_quantile": p["D4_bindings"]["q"]["quantile_probabilities"] = [0.01, 0.99]
    if change == "wrong_statistic": p["D4_bindings"]["q"]["statistic"] = "RMS"
    p["evidence_sha256"] = canonical_hash(evidence)
    release = verify_release_binding(request, evidence=evidence, verifier=interpreter(p))
    with pytest.raises(ValueError): tensor6_normalization(release, "q")


class UnitReader:
    def __init__(self, release): self.release, self.closed = release, False
    def read(self, choice):
        geometry = choice.conformer_id
        frame = {k: self.release.projection["targets"]["q"][k] for k in ("target_id", "condition", "unit", "sign", "frame", "origin_policy")}
        frame["joint_policy"] = self.release.evidence["joint_contract"]
        target = tensor6_from_f64(values=torch.tensor([[1., 2., 3., 4., 5., 6.]], dtype=torch.float64),
            component_valid=torch.ones((1, 6), dtype=torch.bool), geometry_ids=(geometry,),
            component_geometry_ids=((geometry,) * 6,), reasons=({"unit_fixture_only": True},),
            source_ref=self.release.evidence["geometry"])
        context = Tensor6Inputs(torch.tensor([[9., 8., 7.]]), (geometry,), (self.release.evidence["geometry"],), frame)
        return DecodedSample(choice.molecule_id, geometry, choice.geometry_source,
            torch.tensor([[5], [5]]), torch.tensor([[0., 0., 0.], [1., 0., 0.]]), torch.arange(2),
            {"q": target}, domain_inputs={"q": context}, geometry_ref=self.release.evidence["geometry"])
    def close(self): self.closed = True


class UnitReaderFactory:
    read_only = node_local = True
    def __init__(self, release):
        self.release, self.data_version, self.source_ref = release, release.data_version, ref(Path(__file__))
        self.instances = []
    def __call__(self):
        reader = UnitReader(self.release); self.instances.append(reader); return reader


@pytest.mark.parametrize("pilot", [False, True])
def test_provider_returns_actual_existing_batch_and_proxy_inputs_without_another_runner(tmp_path, pilot):
    evidence, request, p, interpreter = metadata_case(tmp_path)
    if pilot:
        request["mode"] = p["scope"] = "authoritative_pilot"
        p["TRAIN_population"] = "versioned_provisional_pilot_TRAIN"
    version = p["data_version"]
    fields = (FieldSpec("element", "S", "structure", "atom", kind="classification", classes=119),
              FieldSpec("noise", "S", "structure", "atom", kind="denoise_eps_mse", representation="vector"),
              FieldSpec("bond", "S", "structure", "pair", kind="classification", classes=5),
              FieldSpec("q", "P", "physics", "graph", representation="symmetric_tensor6", unit="au"))
    registry = LabelRegistry(fields, version, evidence["registry"]["sha256"], authority="data_line")
    indexes, choices = {}, {}
    for role in ("TRAIN", "VAL", "TRAIN_UNSEEN_CONFORMATION"):
        m = MoleculeEntry("m_" + role, (ConformerRef("g_" + role, 0, 2, (("PM7", "loc_" + role),)),),
                          (("S", True), ("D", True), ("P", True)), (("structure", True), ("physics", True)))
        indexes[role] = InMemorySamplingIndex((m,), version, role=role, authority="data_line")
        if role == "TRAIN":
            choices[role] = (UniformMoleculeSampler(indexes[role], seed=0, sample_budget=1).choice(0),)
        else:
            # Validation is the complete explicitly indexed population, not a
            # training draw; preserve the actual VAL/unseen index role.
            member = indexes[role].molecule_at(0)
            conformer = member.conformers[0]
            validation_order = canonical_hash({"scope": "UNIT_FIXED_VALIDATION_ORDER",
                "role": role, "index_sha256": indexes[role].content_sha256})
            choices[role] = (SampleChoice(ordinal=0, molecule_index=0,
                molecule_id=member.molecule_id, conformer_id=conformer.conformer_id,
                geometry_source="PM7", locator=conformer.locator("PM7"), native_atoms=conformer.native_atoms,
                group_mask=member.group_mask, family_mask=member.family_mask,
                index_sha256=indexes[role].content_sha256, sampler_sha256=validation_order),)
        assert indexes[role].role == role
    p["role_index_sha256"] = {role: index.content_sha256 for role, index in indexes.items()}
    validation = {role: (choices[role],) for role in ("VAL", "TRAIN_UNSEEN_CONFORMATION")}
    p["validation_population_bindings"] = {role: canonical_hash([[asdict(c) for c in batch] for batch in batches]) for role, batches in validation.items()}
    release = verify_release_binding(request, evidence=evidence, verifier=interpreter(p))
    binding = StructuralFieldBinding("element", "noise", "bond")
    factory = UnitReaderFactory(release)
    provider = RealDataProvider(release, indexes=indexes, registry=registry, reader_factory=factory,
                                structural_binding=binding, validation_choices=validation)
    norm = tensor6_normalization(release, "q")
    request["input_projection"] = {"index_sha256": indexes["TRAIN"].content_sha256,
        "registry_sha256": registry.content_sha256, "normalization_sha256": canonical_hash({"q": asdict(norm)}),
        "adapter_sha256": provider.source_sha256, "data_version": version}
    # Final request changes must pass the bound verifier again, never a caller self-seal.
    release = verify_release_binding(request, evidence=evidence, verifier=interpreter(p))
    factory = UnitReaderFactory(release)
    with pytest.raises(ValueError, match="All model normalizations"):
        make_proxy_inputs(request, release, indexes=indexes, registry=registry, reader_factory=factory,
            structural_binding=binding, normalizations={"q": replace(norm, scale=(99.,))}, validation_choices=validation)
    inputs = make_proxy_inputs(request, release, indexes=indexes, registry=registry, reader_factory=factory,
        structural_binding=binding, normalizations={"q": norm}, validation_choices=validation)
    try:
        batch = inputs.provider.prepare(choices["TRAIN"], role="TRAIN", view_config=StructuralViewConfig(),
                                        enabled_groups=("P",), enabled_fields=("q",))
        assert isinstance(batch, PreparedV3Batch) and isinstance(batch.pd_targets["q"], Tensor6Target)
        assert batch.pd_targets["q"].values.tolist() == [[1., 2., 3., 4., 5., 6.]]
        assert batch.domain_inputs["q"].origin.tolist() == [[9., 8., 7.]]
        assert batch.geometry_context["geometry_ids"] == ("g_TRAIN",)
        assert batch.geometry_context["geometry_bindings"] == (evidence["geometry"],)
        assert isinstance(batch.to("cpu").pd_targets["q"], Tensor6Target)
        count, batches = inputs.provider.validation_batches(role="VAL", view_config=StructuralViewConfig(),
                                    enabled_groups=("P",), enabled_fields=("q",))
        assert count == 1 and next(batches).role == "VAL"
        assert len(factory.instances) == 2  # independent read-only role handles
    finally:
        inputs.provider.close(); provider.close()
    assert all(reader.closed for reader in factory.instances)
    assert inputs.authority_kind == ("data_line_pilot" if pilot else "data_line_final")
    # The original scientific proxy gate still requires data_line_final plus240k.
    # These fixtures test the return protocol, never real-release acceptance.


def test_pilot_population_cannot_be_renamed_final_proxy(tmp_path):
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    projection["TRAIN_population"] = "versioned_provisional_pilot_TRAIN"
    with pytest.raises(ValueError, match="scoped TRAIN"):
        verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))


def test_typed_reader_rejects_missing_or_wrong_actual_geometry_context(tmp_path):
    from phychem_mfm.phase1.v3_data_adapter import _CheckedReader
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    release = verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))
    class Choice:
        conformer_id, molecule_id, geometry_source = "actual-g", "actual-m", "PM7"
    original = UnitReader(release)
    sample = original.read(Choice())
    class WrongReader:
        def __init__(self, value): self.value = value
        def read(self, choice): return self.value
        def close(self): pass
    with pytest.raises(ValueError):
        _CheckedReader(WrongReader(replace(sample, geometry_ref=None)), release).read(Choice())
    context = replace(sample.domain_inputs["q"], geometry_ids=("wrong-g",))
    with pytest.raises(ValueError, match="actual geometry"):
        _CheckedReader(WrongReader(replace(sample, domain_inputs={"q": context})), release).read(Choice())


@pytest.mark.parametrize("frame_mode", ["audit_only", "missing_metadata", "signed_numeric_frame"])
def test_real_ordered_reader_requires_separately_bound_numeric_source_frame(tmp_path, frame_mode):
    from phychem_mfm.phase1.v3_data_adapter import _CheckedReader
    from phychem_mfm.phase1.v3_label_domains import ChannelCodebook, ordered_entries_from_f64
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    source_frame = write(tmp_path / "source_frame.json", {
        "UNIT_FIXTURE_ONLY": True, "origin": [[.5, -1., 2.]],
        "basis": [[[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]]]})
    binding = {**projection["targets"]["q"], "target_id": "unit_r73", "condition": "pm7_B"}
    if frame_mode != "missing_metadata": binding["source_frame_metadata"] = source_frame
    projection["targets"]["r73"] = binding
    release = verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))
    frame = {k: binding[k] for k in ("target_id", "condition", "unit", "sign", "frame", "origin_policy")}
    frame.update(joint_policy=evidence["joint_contract"], source_frame_metadata=source_frame)
    numeric = {} if frame_mode == "audit_only" else {
        "frame_origin": torch.tensor([[.5, -1., 2.]]),
        "frame_basis": torch.tensor([[[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]]])}
    target = ordered_entries_from_f64(values=torch.tensor([[.25]], dtype=torch.float64),
        source_valid=torch.tensor([True]), atom_index=torch.tensor([[0], [0]]),
        channel_index=torch.tensor([[0], [1]]), entry_ordinal=torch.tensor([0]), n_atoms=2,
        geometry_id="actual-g", codebook=ChannelCodebook(("SIGMA", "PI"), evidence["codebook"]),
        frame_binding=frame, reasons=({},), source_ref=evidence["geometry"], geometry_ref=evidence["geometry"], **numeric)
    sample = DecodedSample("actual-m", "actual-g", "PM7", torch.tensor([[5], [5]]),
        torch.tensor([[0., 0., 0.], [1., 0., 0.]]), torch.arange(2), {"r73": target},
        domain_inputs={"r73": target.inputs}, geometry_ref=evidence["geometry"])
    class Reader:
        def read(self, choice): return sample
        def close(self): pass
    class Choice:
        conformer_id, molecule_id, geometry_source = "actual-g", "actual-m", "PM7"
    checked = _CheckedReader(Reader(), release)
    if frame_mode == "signed_numeric_frame":
        assert checked.read(Choice()) is sample
    else:
        with pytest.raises(ValueError): checked.read(Choice())
