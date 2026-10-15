import pytest

from phychem_mfm.model.adaptation import set_backbone_adaptation


@pytest.mark.parametrize("mode", ("frozen", "last1", "last2", "full"))
def test_backbone_adaptation_semantics(small_model, mode):
    result = set_backbone_adaptation(small_model, mode)
    names = set(result["trainable_names"])
    if mode == "frozen":
        assert not names
    elif mode == "last1":
        assert names and all(name.startswith("layers.0.") or name.startswith("out_norm.") for name in names)
    elif mode == "last2":
        # The test model has one block, so the generic implementation safely selects all available blocks.
        assert names and all(name.startswith("layers.0.") or name.startswith("out_norm.") for name in names)
    else:
        assert any(name.startswith("atom_emb.") for name in names)
        assert result["trainable_parameter_count"] == result["total_parameter_count"]
