#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass


N_ATOM_TYPES = 95
BB_HEADS = 4
BB_FF_MULT = 2


@dataclass(frozen=True)
class ModelSpec:
    name: str
    hidden_channels: int
    bb_layers: int
    expert_real_layers: int
    expert_number_E: int = 1
    expert_number_Q: int = 1
    expert_number_Z: int = 1
    expert_number_G: int = 1


PRESETS = (
    ModelSpec("dense_h64_b3_er1", hidden_channels=64, bb_layers=3, expert_real_layers=1),
    ModelSpec("dense_h64_b4_er1", hidden_channels=64, bb_layers=4, expert_real_layers=1),
    ModelSpec("dense_h64_b3_er2", hidden_channels=64, bb_layers=3, expert_real_layers=2),
    ModelSpec("dense_h96_b3_er1", hidden_channels=96, bb_layers=3, expert_real_layers=1),
    ModelSpec("dense_h96_b4_er1", hidden_channels=96, bb_layers=4, expert_real_layers=1),
    ModelSpec("dense_h128_b3_er1", hidden_channels=128, bb_layers=3, expert_real_layers=1),
    ModelSpec(
        "moe2_top2_h64_b3_er1",
        hidden_channels=64,
        bb_layers=3,
        expert_real_layers=1,
        expert_number_E=2,
        expert_number_Q=2,
        expert_number_Z=2,
        expert_number_G=2,
    ),
)


def _attention_params(dim: int, nheads: int = BB_HEADS) -> int:
    # qkv + proj + distance bias MLP
    return 4 * dim * dim + dim * nheads + 6 * dim + nheads


def _ffn_params(dim: int, ff_mult: int = BB_FF_MULT) -> int:
    # Linear(dim, ff) + Linear(ff, dim)
    return 2 * ff_mult * dim * dim + (ff_mult + 1) * dim


def _real_layer_params(dim: int, nheads: int = BB_HEADS, ff_mult: int = BB_FF_MULT) -> int:
    # attention + FFN + 2x LayerNorm
    return _attention_params(dim, nheads) + _ffn_params(dim, ff_mult) + 4 * dim


def _backbone_params(dim: int, bb_layers: int, n_atom_types: int = N_ATOM_TYPES) -> int:
    # atom embedding + transformer layers + output LayerNorm
    return n_atom_types * dim + bb_layers * _real_layer_params(dim) + 2 * dim


def _expert_params(dim: int, real_layers: int) -> int:
    # only real expert stack is used in the current search configs
    return real_layers * _real_layer_params(dim) + 2 * dim


def _gates_params(dim: int, spec: ModelSpec) -> int:
    return (
        (dim * spec.expert_number_E + spec.expert_number_E)
        + (dim * spec.expert_number_Q + spec.expert_number_Q)
        + (dim * spec.expert_number_Z + spec.expert_number_Z)
        + (dim * spec.expert_number_G + spec.expert_number_G)
    )


def _heads_params(dim: int) -> int:
    # CoordinateDecoder + charge head + element head + energy head
    coord = 2 * dim * dim + 9 * dim + 3
    charge = 5 * dim + 5
    elem = 229 * dim + 229
    energy = dim * dim + 35 * dim + 32
    return coord + charge + elem + energy


def estimate_total_params(spec: ModelSpec) -> int:
    dim = spec.hidden_channels
    total_experts = (
        spec.expert_number_E
        + spec.expert_number_Q
        + spec.expert_number_Z
        + spec.expert_number_G
    )
    return (
        _backbone_params(dim, spec.bb_layers)
        + total_experts * _expert_params(dim, spec.expert_real_layers)
        + _gates_params(dim, spec)
        + _heads_params(dim)
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estimate parameter counts for the current MultiTaskMoE family without importing torch."
    )
    parser.add_argument("--list-presets", action="store_true", help="List built-in candidate configurations")
    parser.add_argument("--preset", type=str, default=None, help="Name of a built-in preset")
    parser.add_argument("--hidden_channels", type=int, default=None)
    parser.add_argument("--bb_layers", type=int, default=None)
    parser.add_argument("--expert_real_layers", type=int, default=None)
    parser.add_argument("--expert_number_E", type=int, default=1)
    parser.add_argument("--expert_number_Q", type=int, default=1)
    parser.add_argument("--expert_number_Z", type=int, default=1)
    parser.add_argument("--expert_number_G", type=int, default=1)
    return parser


def _spec_from_args(args: argparse.Namespace) -> ModelSpec:
    if args.preset is not None:
        for spec in PRESETS:
            if spec.name == args.preset:
                return spec
        raise SystemExit(f"unknown preset: {args.preset}")

    required = ("hidden_channels", "bb_layers", "expert_real_layers")
    missing = [name for name in required if getattr(args, name) is None]
    if missing:
        raise SystemExit(f"missing required args for custom spec: {', '.join(missing)}")

    return ModelSpec(
        name="custom",
        hidden_channels=args.hidden_channels,
        bb_layers=args.bb_layers,
        expert_real_layers=args.expert_real_layers,
        expert_number_E=args.expert_number_E,
        expert_number_Q=args.expert_number_Q,
        expert_number_Z=args.expert_number_Z,
        expert_number_G=args.expert_number_G,
    )


def main() -> None:
    args = _build_parser().parse_args()

    if args.list_presets:
        print("name\thidden\tbb_layers\texpert_real_layers\texperts(E,Q,Z,G)\tparams\tparams_M")
        for spec in PRESETS:
            total = estimate_total_params(spec)
            experts = (
                f"{spec.expert_number_E},"
                f"{spec.expert_number_Q},"
                f"{spec.expert_number_Z},"
                f"{spec.expert_number_G}"
            )
            print(
                f"{spec.name}\t{spec.hidden_channels}\t{spec.bb_layers}\t"
                f"{spec.expert_real_layers}\t{experts}\t{total}\t{total / 1e6:.3f}"
            )
        return

    spec = _spec_from_args(args)
    total = estimate_total_params(spec)
    print(f"name={spec.name}")
    print(f"hidden_channels={spec.hidden_channels}")
    print(f"bb_layers={spec.bb_layers}")
    print(f"expert_real_layers={spec.expert_real_layers}")
    print(
        "experts="
        f"{spec.expert_number_E},{spec.expert_number_Q},{spec.expert_number_Z},{spec.expert_number_G}"
    )
    print(f"params={total}")
    print(f"params_M={total / 1e6:.3f}")


if __name__ == "__main__":
    main()
