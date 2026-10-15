from __future__ import annotations

from copy import deepcopy
from typing import Mapping

from .model.routes import TaskRouteConfig
from .model.shared import SharedBackboneMFM


def task_routes_from_preset(preset: str, per_task: Mapping[str, str] | None = None) -> TaskRouteConfig:
    if per_task:
        return TaskRouteConfig.from_mapping(per_task)
    preset = str(preset).lower()
    if preset in {"shared_light", "light", "light_all"}:
        return TaskRouteConfig.light_all()
    if preset in {"shared_expert", "expert", "expert_main"}:
        return TaskRouteConfig.expert_main()
    if preset in {"hybrid_g", "g"}:
        return TaskRouteConfig.hybrid_g()
    if preset in {"hybrid_qg", "qg"}:
        return TaskRouteConfig.hybrid_qg()
    raise ValueError(f"Unknown architecture preset: {preset}")


def build_model(config: Mapping[str, object], *, preset: str | None = None) -> SharedBackboneMFM:
    payload = deepcopy(dict(config))
    architecture = dict(payload["architecture"])
    selected_preset = preset or architecture.get("preset", "shared_light")
    per_task = architecture.get("task_route_per_task") if preset is None else None
    routes = task_routes_from_preset(str(selected_preset), per_task)
    return SharedBackboneMFM(
        payload["backbone"],
        task_routes=routes,
        expert_config=payload.get("expert", {}),
        head_config=payload.get("head", {}),
    )
