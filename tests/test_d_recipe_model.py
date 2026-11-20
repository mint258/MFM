"""D model facade and loss wiring tests; no training or real-loader acceptance."""
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "current"))
sys.path.insert(0, str(ROOT / "tools" / "d_recipe"))
from model import BLOCK_ALIASES, DRecipeModel
from phychem_mfm.phase1.v31_training import V31PDModel, torch_affine


GRAPH, MOL, ATOM = "D20.example", "D3.PMI1", "D3.SASA_atom_A2"


class TinyEncoder(nn.Module):
    latent_dim = 512
    accepts_coordinates = True

    def __init__(self):
        super().__init__()
        self.anchor = nn.Parameter(torch.zeros(1))


def fixture_view():
    fields = []
    for name, level, block, center, scale in ((GRAPH, "molecule", "graph_2d", 2., 2.),
                                             (MOL, "molecule", "molecule_3d", 0., 1.),
                                             (ATOM, "atom", "atom_sasa", 0., 1.)):
        fields.append(dict(name=name, group="P", source_group="D", family=block,
                           d_block=block, level=level, representation="scalar", target_id=name,
                           selectors=[[23 if level == "molecule" else 24, 0, "labels"]],
                           unit="source_test_unit", normalization=dict(center=[center], scale=[scale])))
    return SimpleNamespace(fields=fields, normalizations={}, schema={"columns": {},
                           "source_D3_reference": {"sha256": "a" * 64}})


def fixture_samples():
    result = []
    for atoms in (1, 3):
        targets = {}
        for name in (GRAPH, MOL, ATOM):
            count = atoms if name == ATOM else 1
            targets[name] = SimpleNamespace(values=np.zeros((count, 1), dtype=np.float32),
                                             valid=np.ones((count, 1), dtype=bool),
                                             raw=np.zeros((count, 1), dtype=np.float32))
        result.append(dict(Z=np.ones(atoms, dtype=np.int64), targets=targets))
    return result


def fixture_predictions():
    return {GRAPH: torch.tensor([[4.], [4.]], requires_grad=True),
            MOL: torch.tensor([[2.], [2.]], requires_grad=True),
            ATOM: torch.tensor([[1.], [3.], [3.], [3.]], requires_grad=True)}


class DRecipeModelTests(unittest.TestCase):
    def model(self, **options):
        configuration = dict(block_weights=dict(graph_2d=.6, molecule_3d=.3, atom_sasa=.1),
                             scientific_binding=dict(seed=0, samples=3000000, library="D20",
                                                     normalization="frozen_11_07"))
        configuration.update(options)
        return DRecipeModel(TinyEncoder(), fixture_view(), d_recipe=configuration)

    def test_default_facade_aggregates_and_explicit_real_fields_stay_distinct(self):
        model = self.model()
        aliases = tuple(BLOCK_ALIASES.values())
        self.assertEqual(tuple(field.name for field in model.registry.enabled(("P",))), aliases)
        self.assertEqual(tuple(field.name for field in model.registry.enabled(("P",), [MOL])), (MOL,))
        self.assertEqual(set(model.heads.registry.by_name()), {GRAPH, MOL, ATOM})
        self.assertFalse(set(aliases) & set(model.heads.keys))
        families = {field.name: field.family for field in model.head_registry.fields
                    if field.name in {model.selections[name][0] for name in aliases}}
        self.assertEqual(families, {alias: block for block, alias in BLOCK_ALIASES.items()})
        self.assertEqual(set(model.by_name), {GRAPH, MOL, ATOM})

    def test_predict_expands_aggregate_names_before_original_real_head_prediction(self):
        model = self.model()
        sentinel = object()
        with patch.object(V31PDModel, "predict", return_value=sentinel) as original:
            actual = model.predict([], fields=[BLOCK_ALIASES["graph_2d"], BLOCK_ALIASES["atom_sasa"]])
        self.assertIs(actual, sentinel)
        self.assertEqual(original.call_args.kwargs["fields"], (GRAPH, ATOM))
        self.assertEqual(original.call_args.kwargs["groups"], ("P",))

    def test_loss_is_frozen_weight_sum_and_sasa_is_mean_of_molecule_means(self):
        model = self.model()
        result = model.loss(fixture_predictions(), fixture_samples())
        expected = {BLOCK_ALIASES["graph_2d"]: .5, BLOCK_ALIASES["molecule_3d"]: 1.5,
                    BLOCK_ALIASES["atom_sasa"]: 1.5}
        for name, value in expected.items():
            self.assertAlmostEqual(result.fields[name].item(), value, places=6)
            self.assertEqual(result.counts[name], 2)
        self.assertAlmostEqual(result.total.item(), .9, places=6)
        loop_total = sum(result.fields[name] * weight for name, weight in model.field_loss_multipliers.items())
        torch.testing.assert_close(loop_total, result.total, rtol=1e-6, atol=1e-7)
        # Original field metadata remains available for original_predictions.
        restored = model.original_predictions(fixture_predictions(), fixture_samples())
        self.assertEqual(set(restored), {GRAPH, MOL, ATOM})
        self.assertEqual(model.definitions[ATOM]["unit"], "source_test_unit")

    def test_empty_sasa_still_keeps_its_block_denominator_without_rescaling(self):
        model = self.model()
        samples = fixture_samples()
        for sample in samples:
            sample["targets"][ATOM].valid[:] = False
        result = model.loss(fixture_predictions(), samples)
        self.assertEqual(result.fields[BLOCK_ALIASES["atom_sasa"]].item(), 0.)
        self.assertEqual(result.counts[BLOCK_ALIASES["atom_sasa"]], 2)
        self.assertAlmostEqual(result.total.item(), .75, places=6)

    def test_deleted_3d_blocks_do_not_change_graph_weight(self):
        model = self.model(include_3d=False)
        result = model.loss(fixture_predictions(), fixture_samples())
        self.assertAlmostEqual(result.total.item(), .3, places=6)
        self.assertEqual(result.fields[BLOCK_ALIASES["molecule_3d"]].item(), 0.)
        self.assertEqual(result.fields[BLOCK_ALIASES["atom_sasa"]].item(), 0.)

    def test_k1_rng_replays_from_extra_state_and_does_not_touch_global_rng(self):
        model = self.model(graph_mask_enabled=True, mask_seed=123)
        initial = deepcopy(model.get_extra_state())
        global_state = torch.get_rng_state().clone()
        model.loss(fixture_predictions(), fixture_samples())
        dropped = model.last_masks["graph_2d"].random_dropped.clone()
        self.assertTrue(torch.equal(global_state, torch.get_rng_state()))
        self.assertFalse(torch.equal(initial["mask_rng"], model.get_extra_state()["mask_rng"]))
        model.set_extra_state(initial)
        model.loss(fixture_predictions(), fixture_samples())
        self.assertTrue(torch.equal(dropped, model.last_masks["graph_2d"].random_dropped))
        model.eval()
        state = model.get_extra_state()["mask_rng"].clone()
        model.loss(fixture_predictions(), fixture_samples())
        self.assertFalse(model.last_masks["graph_2d"].random_dropped.any())
        self.assertTrue(torch.equal(state, model.get_extra_state()["mask_rng"]))

    def test_checkpoint_binding_rejects_a_different_condition(self):
        model = self.model()
        state = deepcopy(model.get_extra_state())
        state["binding"]["library"] = "L2"
        with self.assertRaisesRegex(ValueError, "scientific binding differs"):
            model.set_extra_state(state)
        self.assertEqual(model.get_extra_state()["binding"]["library"], "D20")

    def test_existing_pma_router_uses_real_molecular_d_heads_and_keeps_atom_head(self):
        model = DRecipeModel(TinyEncoder(), fixture_view(),
                             block_weights=dict(graph_2d=.6, molecule_3d=.3, atom_sasa=.1),
                             binding=dict(seed=0, library="D20"), p_recipe=dict(pma_pooling=True))
        for name in (GRAPH, MOL):
            head = model.heads.field_heads[model.heads.keys[name]]
            self.assertEqual(head.in_features, model.p_recipe_pma.representation_dim)
        atom = model.heads.field_heads[model.heads.keys[ATOM]]
        self.assertEqual(atom[0].in_features, model.encoder.latent_dim)
        self.assertEqual(model.heads.registry.by_name()[ATOM].level, "atom")

    def test_wide_shared_heads_pma_and_post_init_rng_match_native_without_encoder_changes(self):
        native_view = fixture_view()
        wide_view = deepcopy(native_view)
        extra_name = "L1.new_descriptor"
        extra = deepcopy(wide_view.fields[0])
        extra.update(name=extra_name, target_id=extra_name)
        # Shift every shared head's initialization position deliberately.
        wide_view.fields.insert(0, extra)
        wide_view.d_initialization_reference = native_view
        encoder = TinyEncoder()
        with torch.no_grad():
            encoder.anchor.fill_(3.25)
        encoder_before = {key: value.clone() for key, value in encoder.state_dict().items()}
        options = dict(block_weights=dict(graph_2d=.6, molecule_3d=.3, atom_sasa=.1),
                       binding=dict(seed=941, library="fixture"),
                       p_recipe=dict(pma_pooling=True, shared_projector=True))
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(941)
            entry_rng = torch.get_rng_state().clone()
            native = DRecipeModel(encoder, native_view, **options)
            native_rng = torch.get_rng_state().clone()
            torch.set_rng_state(entry_rng)
            wide = DRecipeModel(encoder, wide_view, **options)
            self.assertTrue(torch.equal(native_rng, torch.get_rng_state()))
            native_state, wide_state = native.state_dict(), wide.state_dict()
            for name, value in native_state.items():
                if torch.is_tensor(value):
                    self.assertIn(name, wide_state)
                    self.assertTrue(torch.equal(value, wide_state[name]), name)
            # Check library-only weights retain the actual wide construction,
            # rather than being replaced with an arbitrary native head.
            torch.set_rng_state(entry_rng)
            uncorrected_wide = V31PDModel(encoder, wide_view, p_recipe=options["p_recipe"])
            extra_key = "heads.field_heads." + wide.heads.keys[extra_name] + ".weight"
            self.assertTrue(torch.equal(wide_state[extra_key], uncorrected_wide.state_dict()[extra_key]))
            self.assertIn(extra_name, wide.heads.registry.by_name())
            self.assertNotEqual(native_state["heads._extra_state"], wide_state["heads._extra_state"])
            self.assertEqual(wide_state["heads._extra_state"], wide.heads.get_extra_state())
        for key, value in encoder_before.items():
            self.assertTrue(torch.equal(value, encoder.state_dict()[key]), key)
        self.assertIs(native.encoder, encoder)
        self.assertIs(wide.encoder, encoder)

    def test_native_d20_path_keeps_original_model_tensor_and_rng_initialization(self):
        encoder, view = TinyEncoder(), fixture_view()
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(1701)
            entry_rng = torch.get_rng_state().clone()
            original = V31PDModel(encoder, view, p_recipe=dict(pma_pooling=True))
            original_rng = torch.get_rng_state().clone()
            torch.set_rng_state(entry_rng)
            wrapped = DRecipeModel(encoder, view, p_recipe=dict(pma_pooling=True),
                                   block_weights=dict(graph_2d=.6, molecule_3d=.3, atom_sasa=.1),
                                   binding=dict(seed=1701, library="D20"))
            self.assertTrue(torch.equal(original_rng, torch.get_rng_state()))
            wrapped_state = wrapped.state_dict()
            for key, value in original.state_dict().items():
                if torch.is_tensor(value):
                    self.assertTrue(torch.equal(value, wrapped_state[key]), key)

    def test_molecular_vector_pack_preserves_mixed_affines_missing_masks_and_selected_order(self):
        view = fixture_view()
        second = deepcopy(view.fields[0])
        second_name = "D20.second"
        second.update(name=second_name, target_id=second_name,
                      normalization=dict(center=[-3.75], scale=[.125]))
        view.fields.append(second)
        options = dict(block_weights=dict(graph_2d=.6, molecule_3d=.3, atom_sasa=.1),
                       binding=dict(seed=0, library="D20"))
        model = DRecipeModel(TinyEncoder(), view, **options)
        samples, predictions = fixture_samples(), fixture_predictions()
        predictions[GRAPH] = torch.tensor([[4.], [float("nan")]], dtype=torch.float64)
        predictions[second_name] = torch.tensor([[1.125], [2.25]], dtype=torch.float32)
        samples[1]["targets"][GRAPH].valid[:] = False
        samples[1]["targets"][GRAPH].values[:] = np.nan
        for sample, value, valid in zip(samples, (np.nan, 2.), (False, True)):
            sample["targets"][second_name] = SimpleNamespace(
                values=np.array([[value]], dtype=np.float64),
                valid=np.array([[valid]], dtype=bool), raw=np.array([[value]]))
        selected = {second_name, GRAPH, MOL, ATOM}
        packed, target, mask = model._pack(predictions, samples, selected)
        expected = torch.cat([torch_affine(predictions[name].float(),
                                           model.definitions[name]["normalization"])
                              for name in (GRAPH, second_name)], dim=1)
        torch.testing.assert_close(packed["graph_2d"], expected, rtol=0., atol=0., equal_nan=True)
        torch.testing.assert_close(target["graph_2d"], torch.tensor([[0., float("nan")],
                                                                     [float("nan"), 2.]]),
                                   rtol=0., atol=0., equal_nan=True)
        self.assertTrue(torch.equal(mask["graph_2d"], torch.tensor([[True, False], [False, True]])))
        subset, _, _ = model._pack(predictions, samples, {second_name})
        torch.testing.assert_close(subset["graph_2d"], expected[:, 1:], rtol=0., atol=0.)
        self.assertEqual(tuple(subset["molecule_3d"].shape), (2, 0))
        self.assertTrue(torch.isfinite(model.loss(predictions, samples).total))
        normalized = DRecipeModel(TinyEncoder(), view, output_parameterization="normalized", **options)
        packed_normalized, _, _ = normalized._pack(predictions, samples, {GRAPH, second_name})
        torch.testing.assert_close(packed_normalized["graph_2d"],
                                   torch.cat([predictions[name].float() for name in (GRAPH, second_name)], dim=1),
                                   rtol=0., atol=0., equal_nan=True)

    def test_checkpoint_cannot_change_the_head_output_units(self):
        options = dict(block_weights=dict(graph_2d=.6, molecule_3d=.3, atom_sasa=.1),
                       binding=dict(seed=0, library="D20"))
        raw = DRecipeModel(TinyEncoder(), fixture_view(), **options)
        normalized = DRecipeModel(TinyEncoder(), fixture_view(), output_parameterization="normalized", **options)
        with self.assertRaisesRegex(ValueError, "scientific binding"):
            normalized.set_extra_state(raw.get_extra_state())


if __name__ == "__main__":
    unittest.main()
