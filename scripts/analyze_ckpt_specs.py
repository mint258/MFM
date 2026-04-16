import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import torch


def _safe_torch_load(path: Path, *, weights_only: Optional[bool]) -> Any:
    kwargs = {"map_location": "cpu"}
    if weights_only is not None:
        kwargs["weights_only"] = weights_only
    try:
        return torch.load(path, **kwargs)
    except TypeError:
        # Backward compatibility for torch versions without weights_only.
        kwargs.pop("weights_only", None)
        return torch.load(path, **kwargs)


def _to_scalar(x: Any) -> Any:
    if isinstance(x, torch.Tensor):
        if x.numel() == 1:
            return x.item()
        return None
    return x


def _layer_count_from_prefix(keys: Iterable[str], prefix: str) -> Optional[int]:
    idxs = set()
    for key in keys:
        if not key.startswith(prefix):
            continue
        rest = key[len(prefix) :]
        token = rest.split(".", 1)[0]
        if token.isdigit():
            idxs.add(int(token))
    if not idxs:
        return None
    return max(idxs) + 1


def _first_tensor_shape(sd: Dict[str, Any], key: str) -> Optional[Tuple[int, ...]]:
    tensor = sd.get(key)
    if isinstance(tensor, torch.Tensor):
        return tuple(int(x) for x in tensor.shape)
    return None


def _analyze_ae_dict(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    cfg = payload.get("cfg", {}) if isinstance(payload.get("cfg"), dict) else {}
    backbone_cfg = cfg.get("backbone_config", {}) if isinstance(cfg.get("backbone_config"), dict) else {}
    model_state = payload.get("model_state", {})
    if not isinstance(model_state, dict):
        model_state = {}

    backbone_layers = _layer_count_from_prefix(model_state.keys(), "backbone.layers.")
    atom_emb_shape = _first_tensor_shape(model_state, "backbone.atom_emb.weight")
    hidden_from_emb = atom_emb_shape[1] if atom_emb_shape and len(atom_emb_shape) == 2 else None

    return {
        "family": "AE_Transformer_MoE",
        "layer_counts": {
            "backbone_layers": backbone_layers,
            "expert_real_layers": cfg.get("expert_real_layers"),
            "expert_int_layers": cfg.get("expert_int_layers"),
        },
        "hidden_dims": {
            "backbone_hidden_channels": backbone_cfg.get("hidden_channels", hidden_from_emb),
            "atom_embedding_dim": backbone_cfg.get("atom_embedding_dim", hidden_from_emb),
        },
        "extra": {
            "n_atom_types": cfg.get("n_atom_types"),
            "backbone_heads": backbone_cfg.get("bb_heads"),
            "backbone_ff_mult": backbone_cfg.get("bb_ff_mult"),
            "expert_heads": cfg.get("expert_heads"),
            "expert_ff_mult": cfg.get("expert_ff_mult"),
        },
        "load_mode": "weights_only",
        "file": str(path),
    }


def _analyze_egnn_dict(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    cfg = payload.get("cfg", {}) if isinstance(payload.get("cfg"), dict) else {}
    backbone_cfg = cfg.get("backbone_config", {}) if isinstance(cfg.get("backbone_config"), dict) else {}
    moe_state = payload.get("moe_state", {})
    if not isinstance(moe_state, dict):
        moe_state = {}

    interaction_blocks = _layer_count_from_prefix(moe_state.keys(), "backbone.interaction_blocks.")
    atom_emb_shape = _first_tensor_shape(moe_state, "backbone.emb_z.emb.weight")
    hidden_from_emb = atom_emb_shape[1] if atom_emb_shape and len(atom_emb_shape) == 2 else None

    return {
        "family": "EGNN_MoE",
        "layer_counts": {
            "interaction_blocks": interaction_blocks,
            "backbone_num_layers_cfg": backbone_cfg.get("num_layers"),
            "expert_layers": cfg.get("expert_layers"),
        },
        "hidden_dims": {
            "hidden_channels": backbone_cfg.get("hidden_channels", hidden_from_emb),
            "atom_embedding_dim": backbone_cfg.get("atom_embedding_dim", hidden_from_emb),
            "middle_channels": backbone_cfg.get("middle_channels"),
            "latent_bottleneck_dim": cfg.get("latent_bottleneck_dim"),
        },
        "extra": {
            "n_atom_types": cfg.get("n_atom_types"),
            "n_experts_energy": cfg.get("n_experts_energy"),
            "n_experts_charge": cfg.get("n_experts_charge"),
            "n_experts_elem": cfg.get("n_experts_elem"),
            "n_experts_geom": cfg.get("n_experts_geom"),
        },
        "load_mode": "weights_only",
        "file": str(path),
    }


def _analyze_chemeleon_dict(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    hp = payload.get("hyper_parameters", {}) if isinstance(payload.get("hyper_parameters"), dict) else {}
    state = payload.get("state_dict", {}) if isinstance(payload.get("state_dict"), dict) else {}
    w_h_shape = _first_tensor_shape(state, "W_h.weight")
    d_h_from_state = w_h_shape[0] if w_h_shape and len(w_h_shape) == 2 else None

    return {
        "family": "CheMeleon_MessagePassing",
        "layer_counts": {
            "message_passing_depth": hp.get("depth"),
        },
        "hidden_dims": {
            "d_h": hp.get("d_h", d_h_from_state),
        },
        "extra": {
            "d_v": hp.get("d_v"),
            "d_e": hp.get("d_e"),
            "dropout": hp.get("dropout"),
            "activation": hp.get("activation"),
            "undirected": hp.get("undirected"),
        },
        "load_mode": "weights_only",
        "file": str(path),
    }


def _analyze_unimol_dict(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    model = payload.get("model", {})
    if not isinstance(model, dict):
        model = {}

    n_layers = _layer_count_from_prefix(model.keys(), "encoder.layers.")
    out_proj_shape = _first_tensor_shape(model, "encoder.layers.0.self_attn.out_proj.weight")
    fc1_shape = _first_tensor_shape(model, "encoder.layers.0.fc1.weight")
    fc2_shape = _first_tensor_shape(model, "encoder.layers.0.fc2.weight")
    token_shape = _first_tensor_shape(model, "embed_tokens.weight")

    encoder_dim = None
    if out_proj_shape and len(out_proj_shape) == 2:
        encoder_dim = out_proj_shape[0]
    elif fc2_shape and len(fc2_shape) == 2:
        encoder_dim = fc2_shape[0]
    elif token_shape and len(token_shape) == 2:
        encoder_dim = token_shape[1]

    ffn_dim = fc1_shape[0] if fc1_shape and len(fc1_shape) == 2 else None

    return {
        "family": "UniMol_Pretrain",
        "layer_counts": {
            "encoder_layers": n_layers,
        },
        "hidden_dims": {
            "encoder_dim": encoder_dim,
            "ffn_dim": ffn_dim,
        },
        "extra": {
            "vocab_size": token_shape[0] if token_shape and len(token_shape) == 2 else None,
            "state_dict_keys": len(model),
        },
        "load_mode": "weights_only",
        "file": str(path),
    }


def _analyze_mace_model(path: Path, obj: Any) -> Dict[str, Any]:
    state = obj.state_dict() if hasattr(obj, "state_dict") else {}
    if not isinstance(state, dict):
        state = {}

    num_interactions = _to_scalar(state.get("num_interactions"))
    if num_interactions is None:
        num_interactions = _layer_count_from_prefix(state.keys(), "interactions.")

    product_blocks = _layer_count_from_prefix(state.keys(), "products.")
    readout_blocks = _layer_count_from_prefix(state.keys(), "readouts.")

    node_hidden = None
    readout_hidden = None
    if hasattr(obj, "node_embedding") and hasattr(obj.node_embedding, "linear"):
        linear = obj.node_embedding.linear
        if hasattr(linear, "irreps_out") and hasattr(linear.irreps_out, "dim"):
            node_hidden = int(linear.irreps_out.dim)
    if hasattr(obj, "readouts") and len(obj.readouts) > 1 and hasattr(obj.readouts[1], "linear_1"):
        l1 = obj.readouts[1].linear_1
        if hasattr(l1, "irreps_out") and hasattr(l1.irreps_out, "dim"):
            readout_hidden = int(l1.irreps_out.dim)

    return {
        "family": "MACE",
        "layer_counts": {
            "interaction_blocks": num_interactions,
            "product_blocks": product_blocks,
            "readout_blocks": readout_blocks,
        },
        "hidden_dims": {
            "node_hidden_dim": node_hidden,
            "nonlinear_readout_hidden_dim": readout_hidden,
        },
        "extra": {
            "r_max": _to_scalar(state.get("r_max")),
            "num_elements": (
                int(obj.node_embedding.linear.irreps_in.dim)
                if hasattr(obj, "node_embedding")
                and hasattr(obj.node_embedding, "linear")
                and hasattr(obj.node_embedding.linear, "irreps_in")
                and hasattr(obj.node_embedding.linear.irreps_in, "dim")
                else None
            ),
            "class_name": obj.__class__.__name__,
        },
        "load_mode": "full_pickle",
        "file": str(path),
    }


def _analyze_payload(path: Path, payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        keys = set(payload.keys())
        if {"cfg", "model_state"}.issubset(keys):
            return _analyze_ae_dict(path, payload)
        if {"cfg", "moe_state"}.issubset(keys):
            return _analyze_egnn_dict(path, payload)
        if {"hyper_parameters", "state_dict"}.issubset(keys):
            return _analyze_chemeleon_dict(path, payload)
        if keys == {"model"} and isinstance(payload.get("model"), dict):
            return _analyze_unimol_dict(path, payload)
        return {
            "family": "Unknown_Dict",
            "layer_counts": {},
            "hidden_dims": {},
            "extra": {"top_keys": list(payload.keys())[:20]},
            "load_mode": "weights_only",
            "file": str(path),
        }

    class_name = payload.__class__.__name__
    module_name = payload.__class__.__module__
    if "mace" in module_name.lower() or "mace" in class_name.lower():
        return _analyze_mace_model(path, payload)

    return {
        "family": "Unknown_Object",
        "layer_counts": {},
        "hidden_dims": {},
        "extra": {"class_name": class_name, "module_name": module_name},
        "load_mode": "full_pickle",
        "file": str(path),
    }


def _flatten_for_csv(rec: Dict[str, Any]) -> Dict[str, Any]:
    row = {
        "file": rec.get("file"),
        "size_bytes": rec.get("size_bytes"),
        "status": rec.get("status"),
        "family": rec.get("family"),
        "load_mode": rec.get("load_mode"),
        "error": rec.get("error"),
    }
    for k, v in (rec.get("layer_counts") or {}).items():
        row[f"layers.{k}"] = v
    for k, v in (rec.get("hidden_dims") or {}).items():
        row[f"hidden.{k}"] = v
    for k, v in (rec.get("extra") or {}).items():
        row[f"extra.{k}"] = v
    return row


def analyze_one(path: Path, *, allow_unsafe_pickle: bool) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "file": str(path),
        "size_bytes": int(path.stat().st_size),
        "status": "ok",
        "family": None,
        "load_mode": None,
        "layer_counts": {},
        "hidden_dims": {},
        "extra": {},
        "error": None,
    }

    try:
        payload = _safe_torch_load(path, weights_only=True)
        parsed = _analyze_payload(path, payload)
    except Exception as first_exc:
        if allow_unsafe_pickle:
            try:
                # Required by some serialized model objects, e.g., MACE .model.
                import mace  # noqa: F401

                payload = _safe_torch_load(path, weights_only=False)
                parsed = _analyze_payload(path, payload)
            except Exception as second_exc:
                record["status"] = "error"
                record["error"] = f"weights_only_error={first_exc!r}; full_pickle_error={second_exc!r}"
                return record
        else:
            record["status"] = "error"
            record["error"] = repr(first_exc)
            return record

    record.update(
        {
            "family": parsed.get("family"),
            "load_mode": parsed.get("load_mode"),
            "layer_counts": parsed.get("layer_counts", {}),
            "hidden_dims": parsed.get("hidden_dims", {}),
            "extra": parsed.get("extra", {}),
            "error": None,
        }
    )
    return record


def analyze_dir(
    ckpt_dir: Path,
    *,
    extensions: Sequence[str],
    allow_unsafe_pickle: bool,
) -> List[Dict[str, Any]]:
    ext_set = {e.lower() for e in extensions}
    files = sorted(p for p in ckpt_dir.rglob("*") if p.is_file() and p.suffix.lower() in ext_set)
    out: List[Dict[str, Any]] = []
    for path in files:
        out.append(analyze_one(path, allow_unsafe_pickle=allow_unsafe_pickle))
    return out


def save_json(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def save_csv(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_flatten_for_csv(r) for r in records]
    all_cols = set()
    for r in rows:
        all_cols.update(r.keys())
    base = ["file", "size_bytes", "status", "family", "load_mode", "error"]
    remain = sorted(c for c in all_cols if c not in base)
    cols = base + remain
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def print_summary(records: List[Dict[str, Any]]) -> None:
    ok = sum(1 for r in records if r.get("status") == "ok")
    err = sum(1 for r in records if r.get("status") != "ok")
    print(f"Analyzed files: {len(records)} | ok={ok} | error={err}")
    for r in records:
        file_name = Path(str(r.get("file"))).name
        fam = r.get("family")
        status = r.get("status")
        layers = r.get("layer_counts", {})
        hidden = r.get("hidden_dims", {})
        print(f"- {file_name} | {status} | {fam} | layers={layers} | hidden={hidden}")
        if r.get("error"):
            print(f"  error: {r['error']}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("Analyze checkpoint model specs (layers + hidden dims)")
    p.add_argument("--ckpt_dir", type=str, default="ckpt")
    p.add_argument("--output_json", type=str, default="ckpt/model_specs_summary.json")
    p.add_argument("--output_csv", type=str, default="ckpt/model_specs_summary.csv")
    p.add_argument(
        "--extensions",
        nargs="+",
        default=[".pt", ".pth", ".ckpt", ".model"],
        help="File extensions to scan.",
    )
    p.add_argument("--allow_unsafe_pickle", dest="allow_unsafe_pickle", action="store_true")
    p.add_argument("--no_allow_unsafe_pickle", dest="allow_unsafe_pickle", action="store_false")
    p.set_defaults(allow_unsafe_pickle=True)
    return p


def main() -> None:
    args = build_parser().parse_args()
    ckpt_dir = Path(args.ckpt_dir).expanduser().resolve()
    if not ckpt_dir.exists():
        raise FileNotFoundError(f"ckpt_dir not found: {ckpt_dir}")

    records = analyze_dir(
        ckpt_dir,
        extensions=args.extensions,
        allow_unsafe_pickle=bool(args.allow_unsafe_pickle),
    )
    save_json(Path(args.output_json), records)
    save_csv(Path(args.output_csv), records)
    print_summary(records)
    print(f"JSON saved to: {Path(args.output_json).resolve()}")
    print(f"CSV saved to: {Path(args.output_csv).resolve()}")


if __name__ == "__main__":
    main()
