"""Physical source and effective FP32 runtime identity for frozen H0 caches."""
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import inspect
import os
from pathlib import Path
import platform
import re
import subprocess


def physical_source_binding(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("An ordinary physical implementation source is required")
    return {"path": str(path.absolute()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def h0_runtime_fingerprint(encoder, device):
    import torch
    device = torch.device(device)
    if device.type not in {"cpu", "cuda"} or torch.get_default_dtype() != torch.float32:
        raise ValueError("Frozen development H0 export requires the explicit FP32 CPU/CUDA policy")
    floats = [value for value in (*encoder.parameters(), *encoder.buffers()) if value.is_floating_point()]
    if any(value.dtype != torch.float32 for value in floats):
        raise ValueError("Frozen H0 parameters and buffers must already be FP32; implicit casts are forbidden")
    try:
        source = inspect.getsourcefile(type(encoder))
    except (OSError, TypeError):
        source = None
    if source is None or not Path(source).is_file():
        raise ValueError("The encoder must have an inspectable physical source, not a pseudo module path")
    packages = {}
    for name in ("torch-geometric", "torch-scatter", "torch-sparse"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    hardware = {"type": device.type, "machine": platform.machine(), "processor": platform.processor()}
    if device.type == "cuda":
        visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
        if not re.fullmatch(r"GPU-[0-9a-fA-F-]{16,64}", visible) or torch.cuda.device_count() != 1:
            raise ValueError("H0 CUDA runtime must bind one measured full GPU UUID")
        query = subprocess.run(["nvidia-smi", "--id="+visible,
            "--query-gpu=uuid,name,driver_version", "--format=csv,noheader,nounits"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15, check=False)
        rows = list(csv.reader(query.stdout.splitlines()))
        if query.returncode or len(rows) != 1 or len(rows[0]) != 3 or rows[0][0].strip() != visible:
            raise ValueError("Physical GPU UUID and driver binding could not be verified")
        props = torch.cuda.get_device_properties(device)
        hardware.update(uuid=visible, name=rows[0][1].strip(), driver=rows[0][2].strip(),
                        compute_capability=[props.major, props.minor], total_memory=int(props.total_memory))
    implementation_sources, physical_sources = {}, {}
    for module in encoder.modules():
        cls = type(module)
        if cls.__module__ == "torch" or cls.__module__.startswith("torch."):
            continue
        class_name = cls.__module__+"."+cls.__qualname__
        if class_name in implementation_sources:
            continue
        try:
            module_source = inspect.getsourcefile(cls)
        except (OSError, TypeError):
            module_source = None
        if module_source is None:
            raise ValueError("Every custom encoder module must have a physical implementation source")
        if module_source not in physical_sources:
            physical_sources[module_source] = physical_source_binding(module_source)
        implementation_sources[class_name] = physical_sources[module_source]
    return {"schema": "model_v3_h0_effective_runtime_v1", "torch": str(torch.__version__),
        "torch_cuda_runtime": torch.version.cuda, "packages": packages,
        "python": platform.python_version(), "platform": platform.platform(), "device": hardware,
        "default_dtype": str(torch.get_default_dtype()), "H0_output_dtype": "torch.float32",
        "H0_autocast": "locally_disabled_without_changing_global_policy",
        "matmul_precision": torch.get_float32_matmul_precision(),
        "cuda_matmul_allow_tf32": bool(torch.backends.cuda.matmul.allow_tf32),
        "cudnn_allow_tf32": bool(torch.backends.cudnn.allow_tf32),
        "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "deterministic_warn_only": torch.is_deterministic_algorithms_warn_only_enabled(),
        "num_threads": torch.get_num_threads(), "num_interop_threads": torch.get_num_interop_threads(),
        "encoder_class": type(encoder).__module__+"."+type(encoder).__qualname__,
        "encoder_class_source": physical_source_binding(source),
        "encoder_module_sources": implementation_sources,
        "cache_exporter_source": physical_source_binding(Path(__file__).with_name("v3_dev_panel.py")),
        "packing_source": physical_source_binding(Path(__file__).with_name("v3_h0_packing.py")),
        "runtime_binding_source": physical_source_binding(__file__)}
