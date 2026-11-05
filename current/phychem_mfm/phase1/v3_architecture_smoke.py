"""Stage5 D3 wiring only: true pilot inputs, fifty effective updates, no selection.

This module supplies Model metadata/overlays. It creates no Data authority and
does not replace the original 2000-update pilot or D5 scientific preparation.
"""
from copy import deepcopy
from pathlib import Path

from .v3_sample_budget_events import read_bound, require, write_once

PURPOSE = "architecture_wiring_smoke"
LIMIT = 50


def wiring_specs():
    """The original 6+4+9+1 design with declared wiring anchors only."""
    rows = []
    for distance in ("C1-0", "C1-a", "C1-b"):
        for group in ("S", "P"):
            rows.append(dict(name="C1_" + distance[3:] + "_" + group, group=group,
                             distance=distance, views="three", head="H1", pooling="registry_fixed",
                             anchor_only=False))
    for views in ("two", "three"):
        for group in ("S", "SDP"):
            rows.append(dict(name="C3_v" + ("2" if views == "two" else "3") + "_" + group,
                             group=group, distance="C1-0", views=views, head="H1",
                             pooling="registry_fixed", anchor_only=True))
    for head in ("H1", "H2", "H3"):
        for group in ("P", "D", "SDP"):
            rows.append(dict(name="H_" + head + "_" + group, group=group, distance="C1-0",
                             views="three", head=head, pooling="registry_fixed", anchor_only=True))
    rows.append(dict(name="H_H1_P_learned_pooling", group="P", distance="C1-0",
                     views="three", head="H1", pooling="learned_mixer", anchor_only=True))
    return tuple(rows)


def wiring_spec(name):
    rows = [row for row in wiring_specs() if row["name"] == name]
    require(len(rows) == 1, "One of the original twenty first-seed trials is required")
    return deepcopy(rows[0])


def wiring_contract(name):
    spec = wiring_spec(name)
    return dict(schema="model_v3_architecture_wiring_smoke_v1", purpose=PURPOSE,
                trial_name=name, optimizer_update_limit=LIMIT, pretraining_seed=0,
                anchor_only=spec["anchor_only"], status="NOT_SELECTED_NOT_SCIENTIFIC",
                r674=dict(loss="LOSS_DISABLED", retain_prediction_head=True,
                          additional_diagnostics=False))


def validate_architecture_wiring_smoke(request, configuration):
    """Validate metadata only; validate_request/bind_inputs still grant all authority."""
    contract = configuration.get(PURPOSE)
    declared = request.get("purpose") == PURPOSE
    require(declared is (contract is not None), "Wiring purpose and sealed configuration must agree")
    if not declared:
        return None
    require(type(contract) is dict and type(contract.get("optimizer_update_limit")) is int
            and type(contract.get("pretraining_seed")) is int and type(contract.get("anchor_only")) is bool
            and type(contract.get("r674")) is dict
            and type(contract["r674"].get("retain_prediction_head")) is bool
            and type(contract["r674"].get("additional_diagnostics")) is bool
            and contract == wiring_contract(contract.get("trial_name")),
            "Exact fifty-update original-trial wiring contract required")
    require(request.get("mode") == "authoritative_pilot" and request.get("scope") == "pilot_smoke"
            and configuration.get("engineering_only") is False
            and configuration.get("experiment_scope") == "AUTHORITATIVE_PILOT_SMOKE",
            "Wiring smoke must use the actual authoritative pilot, never synthetic/proxy/full/grid")
    require(configuration["pilot_smoke"]["optimizer_update_cap"] == 2000
            and "engineering_update_cap" not in configuration,
            "The original global pilot 2000-update contract remains unchanged")
    require("training_execution" not in configuration
            and "performance_execution_v1" not in configuration["model"],
            "Bias-free C wiring uses the supported plain path; no optimized fallback")
    require(type(configuration["seed"]) is int and configuration["seed"] == 0,
            "The first-seed wiring design is seed0")
    spec = wiring_spec(contract["trial_name"])
    backbone = configuration["model"]["backbone"]
    require(backbone["dim"] == 512 and backbone["layers"] == 6 and backbone.get("heads", 8) == 8
            and backbone.get("ff_mult", 2) == 2 and backbone.get("n_atom_types", 119) == 119
            and backbone.get("distance_bias_projection_bias") is False
            and not backbone.get("use_radius_mask", False),
            "Original six-by-512 global C bias-free architecture required")
    require(backbone.get("v3_architecture", {}).get("distance_bias", "C1-0") == spec["distance"],
            "Wiring distance differs from its declared trial/anchor")
    c = configuration["proxy_contract"]
    require(c["groups"] == {"S": ["S"], "P": ["P"], "D": ["D"], "SDP": ["S", "D", "P"]}[spec["group"]]
            and c["views"] == c["validation"]["views"] == spec["views"]
            and c["heads"]["forms"] == spec["head"] and c["heads"].get("hidden_dim", 64) == 64
            and configuration["model"]["head"]["profile"] == "phase1"
            and configuration["model"]["head"]["geometry_head"] == "equivariant_noise",
            "Wiring groups/views/head differ from the fixed original trial")
    overrides = c["heads"].get("pooling_overrides", {})
    require((type(overrides) is dict and bool(overrides) and set(overrides.values()) == {"learned"})
            if spec["pooling"] == "learned_mixer" else not overrides,
            "Only the original H1/P pooling comparison may use learned mixing")
    require(c["precision"] == {"mode": "fp32", "matmul_tf32": False,
            "cudnn_tf32": False, "matmul_precision": "highest"},
            "Wiring is the original plain FP32 path; C4 acceptance is FP64 mathematics")
    return deepcopy(contract)


def wiring_update_limit(request, configuration, original_limit):
    value = validate_architecture_wiring_smoke(request, configuration)
    if value is None:
        return original_limit
    require(original_limit == 2000, "The original pilot global cap must remain 2000")
    return LIMIT


def wiring_result(request, configuration, result):
    """Relabel only this scoped result; fifty updates never close the 2000 pilot."""
    if validate_architecture_wiring_smoke(request, configuration) is None:
        return result
    require(result["optimizer_update_cap"] == LIMIT
            and type(result["actual_optimizer_updates"]) is int
            and 0 <= result["actual_optimizer_updates"] <= LIMIT,
            "Wiring must use the committed effective-update counter")
    out = deepcopy(result)
    complete = result["actual_optimizer_updates"] == LIMIT
    out.update(purpose=PURPOSE, pilot_global_optimizer_update_cap=2000,
               status=("ARCHITECTURE_WIRING_50_COMPLETE_NOT_SELECTION_NOT_PILOT_2000" if complete
                       else "ARCHITECTURE_WIRING_PAUSED_NOT_COMPLETE"),
               pilot_2000_complete=False, Stage5_scientific_trial_complete=False,
               architecture_selected=False, scientific_acceptance=False)
    return out


def prepare_wiring_request(base_request_reference, trial_name, output):
    """Consume a real admitted D3 pilot base; emit a fresh UNADMITTED successor."""
    from .v3_proxy_run import validate_request, bind_inputs, identity
    from ..model.v3_architecture import ArchitectureOptions, source_s_architecture_configuration
    base = read_bound(base_request_reference)
    require(base.get("mode") == "authoritative_pilot" and base.get("purpose") is None,
            "A real ordinary admitted D3 pilot base is required")
    template, _, _ = validate_request(base, input_kind="authoritative_pilot")
    inputs = bind_inputs(base, template)  # Original release/reader/ACK/role checks; no bypass.
    try:
        require(inputs.authority_kind == "data_line_pilot" and inputs.release_accepted is True,
                "An actual accepted bounded D3 pilot release is required")
        registry = inputs.registry
    finally:
        inputs.provider.close()
    spec = wiring_spec(trial_name)
    cfg = deepcopy(template)
    require("training_execution" not in cfg and cfg["proxy_contract"]["fields"] is None,
            "Use the original plain all-field pilot base, not a subset/optimized fallback")
    cfg["seed"] = 0
    model = cfg["model"]
    model["backbone"].pop("v3_architecture", None)
    model["backbone"]["distance_bias_projection_bias"] = False
    cfg["model"] = source_s_architecture_configuration(
        model, ArchitectureOptions(distance_bias=spec["distance"]))
    c = cfg["proxy_contract"]
    c["groups"] = {"S": ["S"], "P": ["P"], "D": ["D"], "SDP": ["S", "D", "P"]}[spec["group"]]
    c["views"] = c["validation"]["views"] = spec["views"]
    c["heads"]["forms"] = spec["head"]
    c["heads"]["hidden_dim"] = 64
    c["heads"].pop("pooling_overrides", None)
    if spec["pooling"] == "learned_mixer":
        overrides = {f.name: "learned" for f in registry.fields
                     if f.group == "P" and f.level == "graph" and f.representation == "scalar"}
        require(overrides, "The actual unchanged registry has no P scalar graph pooling targets")
        c["heads"]["pooling_overrides"] = overrides
    cfg[PURPOSE] = wiring_contract(trial_name)
    request = deepcopy(base)
    request.update(purpose=PURPOSE, registrations={}, Root_admission=None)
    validate_architecture_wiring_smoke(request, cfg)
    root = Path(output)
    require(not root.exists(), "Fresh wiring preparation output required")
    root.mkdir(parents=True)
    cfgref = write_once(root / "configuration.json", cfg)
    request["configuration"] = cfgref
    request["architecture_wiring_preparation"] = {
        "base_request": deepcopy(base_request_reference), "trial_name": trial_name,
        "configuration_identity_sha256": identity(cfg), "status": "UNADMITTED_NOT_SELECTED"}
    reqref = write_once(root / "request.UNADMITTED.json", request)
    return write_once(root / "PREPARED.json", {
        "schema": "model_v3_architecture_wiring_prepared_v1", "status": "WIRING_CONFIG_UNADMITTED",
        "configuration": cfgref, "request": reqref, "effective_update_limit": LIMIT,
        "pilot_global_update_cap": 2000, "anchor_only": spec["anchor_only"],
        "requires_fresh_Root_admission_and_real_D3": True, "scientific_selection": False})
