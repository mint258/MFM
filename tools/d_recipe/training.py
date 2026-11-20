"""D adapters around the existing P sample-clock/optimizer/checkpoint loop.

No P source is copied or modified. Installation affects only this invoking
process and is restored on success or error; spawned readers use this module's
explicit D initializer. This is not a scheduler or a grant to launch training.
"""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path


BLOCK_ALIASES = {"graph_2d": "D_BLOCK_GRAPH_2D", "molecule_3d": "D_BLOCK_MOLECULE_3D",
                 "atom_sasa": "D_BLOCK_ATOM_SASA"}
ARMS = {"D-R0", "D-R1", "D-L1", "D-L2", "D-G1", "D-K1", "9M-D-R0", "9M-D-final"}


class ResultRoot:
    """Redirect only the reused loop's P-report prefix to this D worktree."""
    def __init__(self, root):
        self.root = Path(root)

    def __truediv__(self, relative):
        text = str(relative)
        if text == "results/p_recipe" or text.startswith("results/p_recipe/"):
            text = "results/d_recipe" + text[len("results/p_recipe"):]
        return self.root / text


def prepare_runtime(configuration):
    c = deepcopy(configuration)
    d = c["d_recipe"]
    if c.get("condition") != "D" or c.get("arm") not in ARMS:
        raise ValueError("Use only taskbook D conditions and registered arms")
    confirmation = c["arm"].startswith("9M-")
    if c.get("samples") != (9_000_000 if confirmation else 3_000_000):
        raise ValueError("D screening/confirmation budgets must remain 3M/9M")
    if c.get("seed") not in (0, 1) or (confirmation and c["seed"] != 0):
        raise ValueError("At most seed0/seed1; all 9M runs use seed0")
    if (c.get("batch_size"), c.get("microbatch_size"), c.get("lr"),
            c.get("weight_decay"), tuple(c.get("betas", ())), c.get("warmup_fraction")) != (
            32, 32, 3e-4, .01, (.9, .95), .02):
        raise ValueError("Keep the registered common D training settings")
    if c.get("mean_labels", False) or c.get("activation_checkpointing", False):
        raise ValueError("D uses one sampled conformer and no layer recomputation")
    if c.get("distance_bias") != "C1-0" or c.get("schedule") != "cosine":
        raise ValueError("Use C1-0 and the full-budget cosine schedule")
    if c.get("fields") is not None:
        raise ValueError("D physical field selection belongs to its frozen data/library manifest")
    if d.get("library") not in ("D20", "L1", "L2"):
        raise ValueError("Use a registered D target library")
    if c["arm"] in ("D-R0", "D-R1", "D-G1", "9M-D-R0") and d["library"] != "D20":
        raise ValueError("Native/transfer/3D-deletion arms use D20")
    if c["arm"] in ("D-L1", "D-L2") and d["library"] != c["arm"][2:]:
        raise ValueError("Wide arm and library differ")
    if c["arm"] == "D-K1" and (d["library"] == "D20" or not d.get("adopted_wide")):
        raise ValueError("D-K1 requires an adopted wide library")
    if d.get("graph_mask_enabled", False) and c["arm"] not in ("D-K1", "9M-D-final"):
        raise ValueError("Random target masks belong only to the conditional/final arms")
    if not d.get("include_3d", True) and c["arm"] not in ("D-G1", "9M-D-final"):
        raise ValueError("Only the registered deletion/final configuration may disable D3")
    if c["arm"] == "D-G1" and d.get("include_3d", True):
        raise ValueError("D-G1 must disable both 3D losses without rescaling 2D")
    if c["arm"] == "D-K1" and not d.get("graph_mask_enabled", False):
        raise ValueError("D-K1 must enable the one fixed 85% masking rule")
    clip = c.get("clip_calibration", {})
    if (clip.get("calibration_samples"), clip.get("window_start_samples"),
            clip.get("initial_clip"), clip.get("quantile")) != (150000, 60000, 281.7, .99):
        raise ValueError("Keep each arm's registered 60k-150k p99 calibration")
    weights = d["block_weights"]
    if set(weights) != set(BLOCK_ALIASES) or abs(sum(weights.values()) - 1.) > 1e-12:
        raise ValueError("Supply the frozen three D-R0 block weights")
    recipe = c.setdefault("p_recipe", {})
    if recipe.get("uncertainty_weighting") or recipe.get("family_equal"):
        raise ValueError("D block totals cannot be changed by P-specific weighting")
    recipe["field_loss_multipliers"] = {BLOCK_ALIASES[key]: value for key, value in weights.items()}
    d["pma_compatibility"] = True
    # Keep the existing reader path: the P prepared-target metadata has not
    # been extended to the D aggregate aliases or wide targets.
    overhead = c.setdefault("step_overhead", dict(grouped_fields=True, head_checkpointing=False,
        distance_tiling=True, prepared_input=False))
    if overhead.get("prepared_input", False):
        raise ValueError("D bridge uses the unchanged ordinary ordered reader path")
    c["activation_checkpointing"] = False
    c["checkpoint_samples"] = list(range(1_000_000, c["samples"] + 1, 1_000_000))
    binding = d.setdefault("scientific_binding", {})
    identity = {name: c.get(name) for name in ("arm", "seed", "samples", "source",
        "normalizations", "corpus", "training_view", "distance_bias", "components")}
    identity.update(library=d["library"], wide_manifest=d.get("wide_manifest"),
        label_parameters=d.get("label_parameters", c.get("label_parameters")),
        transferred_recipe={key: value for key, value in recipe.items() if key != "field_loss_multipliers"})
    for key, value in identity.items():
        if key in binding and binding[key] != value:
            raise ValueError("Scientific checkpoint binding contradicts configuration: " + key)
        binding[key] = deepcopy(value)
    return c


def init_reader(configuration, mean_labels):
    if mean_labels:
        raise ValueError("D taskbook does not average conformer labels")
    import torch
    from .dataset import DRecipeDataset
    global WORKER_DATA
    torch.set_num_threads(1)
    WORKER_DATA = DRecipeDataset(**configuration)


def read_choice(choice):
    return WORKER_DATA.read(*choice)


@contextmanager
def installed_bridge(configuration, *, module=None, model_class=None, dataset_class=None):
    if module is None:
        from phychem_mfm.phase1 import p_recipe_training as module
    if model_class is None:
        from .model import DRecipeModel as model_class
    if dataset_class is None:
        from .dataset import DRecipeDataset as dataset_class
    names = ("V31PDModel", "PRecipeDataset", "dataset_configuration", "init_reader", "read_choice", "REPO")
    original = {name: getattr(module, name) for name in names}
    held = {}

    def build_model(*args, **kwargs):
        held["model"] = model_class(*args, d_recipe=configuration["d_recipe"], **kwargs)
        return held["model"]

    def reader_config(c, *, validation=False):
        result = original["dataset_configuration"](c, validation=validation)
        result["d_recipe"] = deepcopy(c["d_recipe"])
        return result

    try:
        module.V31PDModel = build_model
        module.PRecipeDataset = dataset_class
        module.dataset_configuration = reader_config
        module.init_reader, module.read_choice = init_reader, read_choice
        module.REPO = ResultRoot(Path(__file__).resolve().parents[2])
        yield held
    finally:
        for name, value in original.items():
            setattr(module, name, value)


def train(configuration, *, module=None):
    if module is None:
        from phychem_mfm.phase1 import p_recipe_training as module
    if not configuration.get("d_recipe", {}).get("enabled", False):
        return module.train(configuration)
    c = prepare_runtime(configuration)
    import torch
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    # The Root submitter checks the frozen preregistration, P freeze/9M
    # dependency and conditional seed/arm decisions before scheduling this API.
    # This adapter itself schedules nothing and creates no acceptance record.
    with installed_bridge(c, module=module) as held:
        summary = module.train(c)
        model = held.pop("model", None)
        if model is not None:
            summary["D_mask_counts"] = getattr(model, "mask_counts", {})
        del model
    summary["D_training_adapter"] = "existing_P_loop_with_D_data_model_and_loss_adapters"
    return summary
