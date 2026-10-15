from __future__ import annotations

import argparse
from pathlib import Path

import torch

try:
    from .utils import write_json
except ImportError:
    from utils import write_json


def _load_payload(path: str):
    return torch.load(path, map_location="cpu")


def _average_model_states(payloads: list[dict]) -> tuple[dict, list[str], list[str]]:
    if not payloads:
        raise ValueError("No checkpoints were provided.")

    base_state = payloads[0]["model_state"]
    averaged_state = {}
    averaged_keys: list[str] = []
    skipped_keys: list[str] = []

    for key, value in base_state.items():
        if not isinstance(value, torch.Tensor):
            averaged_state[key] = value
            skipped_keys.append(key)
            continue

        compatible_tensors = []
        compatible = True
        for payload in payloads:
            other = payload["model_state"].get(key)
            if not isinstance(other, torch.Tensor) or other.shape != value.shape or other.dtype != value.dtype:
                compatible = False
                break
            compatible_tensors.append(other.detach().cpu())

        if not compatible:
            averaged_state[key] = value
            skipped_keys.append(key)
            continue

        if value.is_floating_point():
            averaged_state[key] = torch.stack(compatible_tensors, dim=0).mean(dim=0)
            averaged_keys.append(key)
        else:
            averaged_state[key] = value
            skipped_keys.append(key)

    return averaged_state, averaged_keys, skipped_keys


def main() -> None:
    parser = argparse.ArgumentParser("Average same-structure MFM pretrain checkpoints")
    parser.add_argument("--checkpoints", nargs="+", required=True, help="Checkpoint paths to average.")
    parser.add_argument("--output", required=True, help="Output checkpoint path.")
    args = parser.parse_args()

    checkpoint_paths = [str(Path(path).resolve()) for path in args.checkpoints]
    payloads = [_load_payload(path) for path in checkpoint_paths]
    averaged_state, averaged_keys, skipped_keys = _average_model_states(payloads)

    output_payload = dict(payloads[0])
    output_payload["checkpoint_kind"] = "averaged"
    output_payload["model_state"] = averaged_state
    output_payload["optimizer_state"] = None
    output_payload["scheduler_state"] = None
    output_payload["metadata"] = {
        **dict(payloads[0].get("metadata") or {}),
        "averaged_from": checkpoint_paths,
        "averaged_checkpoint_count": len(checkpoint_paths),
        "averaged_parameter_count": len(averaged_keys),
        "skipped_parameter_count": len(skipped_keys),
        "is_ema": False,
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(output_payload, output_path)
    write_json(
        Path(str(output_path) + ".meta.json"),
        {
            "checkpoint_kind": "averaged",
            "output_path": str(output_path),
            "averaged_from": checkpoint_paths,
            "averaged_parameter_count": len(averaged_keys),
            "skipped_parameter_count": len(skipped_keys),
            "first_averaged_keys": averaged_keys[:20],
            "first_skipped_keys": skipped_keys[:20],
        },
    )
    print(f"Saved averaged checkpoint to {output_path}")
    print(f"Averaged floating-point tensors: {len(averaged_keys)}")
    print(f"Skipped tensors: {len(skipped_keys)}")


if __name__ == "__main__":
    main()
