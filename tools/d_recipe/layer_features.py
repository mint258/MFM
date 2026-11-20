"""Capture registered layers during the existing development-panel forward.

Default off: invoked only with an explicit diagnostic_feature_root. Reuse the
unchanged P feature producer, its model loader, source members and atom IDs.
No extra encoder pass or probe fit is performed by this module.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import weakref

import torch


LAYERS = (3, 4, 5, 6)


def _binding(configuration, dataset):
    return {name: configuration[name] for name in ("run", "checkpoint", "store")} | {"dataset": dataset}


def _layer_payload(payload, features):
    records, cursor = [], 0
    for record in payload["records"]:
        length = len(record["h0"])
        records.append(dict(record, h0=features[cursor:cursor + length]))
        cursor += length
    if cursor != len(features):
        raise ValueError("Captured layer rows differ from native source atom rows")
    return dict(payload, records=records)


@contextmanager
def capture_existing_forward(configuration, *, evaluator, model_module, guard):
    """Serial, process-local capture around the native producer; restore hooks.

    Potential adopted wide arms may capture the already computed intermediate
    tensors before the adoption decision. Only the subsequently registered
    conditions receive diagnostic probe fits. Missing historical layer caches
    never trigger another forward here.
    """
    if configuration.get("layer", 6) != 6:
        raise ValueError("Layer capture attaches only to the original final-layer readout")
    root = Path(configuration["diagnostic_feature_root"])
    original_producer = evaluator.produce_missing_features
    original_factory = model_module.s_model

    def produce(c, dataset, view):
        binding = _binding(c, dataset)
        manifest = root / dataset / "manifest.json"
        if manifest.exists():
            saved = json.loads(manifest.read_text())
            if saved["binding"] != binding:
                raise ValueError("Layer cache belongs to a different checkpoint or native membership")
            return torch.load(saved["features"]["6"], map_location="cpu", weights_only=True)
        captured = {layer: [] for layer in LAYERS[:-1]}

        def factory(*args, **kwargs):
            model, details = original_factory(*args, **kwargs)
            encoder = weakref.ref(model.encoder)
            method = type(model.encoder).encode_atoms
            def encode(batch, **options):
                h, intermediates = method(encoder(), batch, **dict(options, return_intermediates=True))
                for layer in captured:
                    captured[layer].append(intermediates[layer - 1].detach().cpu().float())
                return h
            model.encoder.encode_atoms = encode
            return model, details

        try:
            model_module.s_model = factory
            payload = original_producer(dict(c, persist_features=False), dataset, view)
        finally:
            model_module.s_model = original_factory
        if payload is None:
            # The unchanged producer found an older final-layer file. Its
            # caller will consume that file; do not rerun its encoder for 3-5.
            return None
        destination = root / dataset
        guard.check(destination)
        destination.mkdir(parents=True, exist_ok=True)
        features = {}
        for layer in LAYERS:
            guard.check(destination)
            value = payload if layer == 6 else _layer_payload(payload, torch.cat(captured[layer], dim=0))
            path = destination / ("layer" + str(layer) + ".pt")
            temporary = path.with_suffix(".partial.pt")
            torch.save(value, temporary)
            temporary.replace(path)
            features[str(layer)] = str(path)
        temporary = manifest.with_suffix(".partial")
        temporary.write_text(json.dumps(dict(schema="D_DEV_LAYER_FEATURES_V1", binding=binding,
            features=features, layers=list(LAYERS), encoder_passes=1,
            source_producer="tools.p_recipe.evaluate.produce_missing_features"), indent=2) + "\n")
        temporary.replace(manifest)
        return payload

    try:
        evaluator.produce_missing_features = produce
        yield
    finally:
        evaluator.produce_missing_features = original_producer
        model_module.s_model = original_factory


def cached_layer_configuration(configuration, layer, *, output):
    """Point native probes at closed files, preserving all original task rows."""
    if layer not in LAYERS:
        raise ValueError("Only the existing registered layers3-6 are supported")
    root = Path(configuration["diagnostic_feature_root"])
    features = {}
    for dataset in ("expansionrx", "cyp_isoform", "qm9"):
        manifest = json.loads((root / dataset / "manifest.json").read_text())
        if manifest["binding"] != _binding(configuration, dataset):
            raise ValueError("Layer features do not match this run's source binding")
        features[dataset] = manifest["features"][str(layer)]
    result = dict(configuration, run=configuration["run"] + "__diagnostic_layer" + str(layer),
        features=features, layer=layer, output=str(output), persist_features=False)
    result.pop("diagnostic_feature_root", None)
    return result


@contextmanager
def cached_features_only(evaluator):
    """A missing diagnostic feature is explicit; never fall back to extraction."""
    original = evaluator.produce_missing_features
    def produce(c, dataset, view):
        if not evaluator.feature_path(c, dataset).is_file():
            raise FileNotFoundError("Registered diagnostic layer cache unavailable: " + dataset)
        return None
    try:
        evaluator.produce_missing_features = produce
        yield
    finally:
        evaluator.produce_missing_features = original
