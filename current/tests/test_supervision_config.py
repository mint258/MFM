import pytest

from phychem_mfm.supervision import Objective, SupervisionConfig, SupervisionVariant


@pytest.mark.parametrize(
    ("variant", "expected"),
    [
        ("S", {"element", "geometry", "bond"}),
        ("P", {"energy", "charge"}),
        ("D", {"graph_descriptor", "charge_descriptor", "element_descriptor"}),
        ("SP", {"element", "geometry", "bond", "energy", "charge"}),
        ("SD", {"element", "geometry", "bond", "graph_descriptor", "charge_descriptor", "element_descriptor"}),
        ("SPD", {item.value for item in Objective}),
    ],
)
def test_variant_objective_mapping(variant, expected):
    config = SupervisionConfig.from_variant(variant)
    assert config.variant is SupervisionVariant(variant)
    assert {item.value for item in config.objectives} == expected


def test_descriptor_ramp_removes_only_descriptor_objectives():
    config = SupervisionConfig.from_variant("SPD")
    active = config.objectives_at_descriptor_scale(0.0)
    assert Objective.ENERGY in active
    assert Objective.GRAPH_DESCRIPTOR not in active
